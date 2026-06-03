# SPDX-License-Identifier: MIT
"""Track RustChain sync committee rotation state.

The tracker derives a deterministic committee from the current epoch and active
miner set, stores epoch snapshots in SQLite, and can expose a tiny dashboard plus
Prometheus-compatible metrics. It intentionally uses only the standard library
so operators can run it beside an existing node without extra setup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

DEFAULT_NODE_URL = os.getenv("RUSTCHAIN_NODE_URL", "https://rustchain.org").rstrip("/")
DEFAULT_DB_PATH = Path(os.getenv("SYNC_COMMITTEE_DB", "sync_committee_history.db"))
DEFAULT_COMMITTEE_SIZE = int(os.getenv("SYNC_COMMITTEE_SIZE", "8"))
DEFAULT_ROTATION_EPOCHS = int(os.getenv("SYNC_COMMITTEE_ROTATION_EPOCHS", "1"))


@dataclass(frozen=True)
class Miner:
    """Normalized miner identity used for committee ordering."""

    miner_id: str
    arch: str = "unknown"
    weight: float = 1.0


def fetch_json(base_url: str, endpoint: str, timeout: int = 8) -> Any:
    """Fetch JSON from a RustChain node endpoint."""

    request = Request(
        f"{base_url.rstrip('/')}{endpoint}",
        headers={
            "Accept": "application/json",
            "User-Agent": "rustchain-sync-committee-tracker/1.0",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 1.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_miners(payload: Any) -> list[Miner]:
    """Return stable miner records from common RustChain miner payload shapes."""

    if isinstance(payload, dict):
        raw_miners = payload.get("miners", payload.get("data", []))
    elif isinstance(payload, list):
        raw_miners = payload
    else:
        raw_miners = []
    if not isinstance(raw_miners, list):
        raw_miners = []

    miners: dict[str, Miner] = {}
    for item in raw_miners:
        if not isinstance(item, dict):
            continue
        miner_id = (
            item.get("miner_id")
            or item.get("miner_pk")
            or item.get("miner")
            or item.get("wallet")
            or item.get("address")
            or item.get("public_key")
        )
        if not miner_id:
            continue
        miner_id = str(miner_id)
        arch = str(item.get("device_arch") or item.get("arch") or "unknown")
        weight = _as_float(
            item.get("weight", item.get("multiplier", item.get("rust_score", 1.0)))
        )
        miners[miner_id] = Miner(miner_id=miner_id, arch=arch, weight=max(weight, 0.0))

    return [miners[key] for key in sorted(miners)]


def committee_sort_key(epoch: int, miner: Miner) -> tuple[str, str]:
    """Return deterministic per-epoch ordering key for a miner."""

    digest = hashlib.sha256(f"{epoch}:{miner.miner_id}".encode("utf-8")).hexdigest()
    return digest, miner.miner_id


def select_committee(miners: list[Miner], epoch: int, committee_size: int) -> list[Miner]:
    """Select the current sync committee for an epoch."""

    if committee_size <= 0:
        return []
    ordered = sorted(miners, key=lambda miner: committee_sort_key(epoch, miner))
    return ordered[: min(committee_size, len(ordered))]


def build_snapshot(
    epoch_payload: dict[str, Any],
    miners_payload: Any,
    *,
    committee_size: int = DEFAULT_COMMITTEE_SIZE,
    rotation_epochs: int = DEFAULT_ROTATION_EPOCHS,
    observed_at: int | None = None,
) -> dict[str, Any]:
    """Build a dashboard-ready sync committee snapshot."""

    epoch = _as_int(epoch_payload.get("epoch", epoch_payload.get("current_epoch", 0)))
    slot = _as_int(epoch_payload.get("slot", epoch_payload.get("current_slot", 0)))
    slots_per_epoch = _as_int(
        epoch_payload.get("slots_per_epoch", epoch_payload.get("blocks_per_epoch", 0))
    )
    miners = normalize_miners(miners_payload)
    committee = select_committee(miners, epoch, committee_size)
    next_rotation_epoch = epoch + max(rotation_epochs, 1)
    slots_until_rotation = max(slots_per_epoch - (slot % slots_per_epoch), 0) if slots_per_epoch else 0

    return {
        "observed_at": observed_at or int(time.time()),
        "epoch": epoch,
        "slot": slot,
        "slots_per_epoch": slots_per_epoch,
        "rotation_interval_epochs": max(rotation_epochs, 1),
        "next_rotation_epoch": next_rotation_epoch,
        "slots_until_rotation": slots_until_rotation,
        "active_miners": len(miners),
        "committee_size": len(committee),
        "configured_committee_size": committee_size,
        "committee": [
            {
                "position": index + 1,
                "miner_id": miner.miner_id,
                "arch": miner.arch,
                "weight": miner.weight,
                "order_hash": committee_sort_key(epoch, miner)[0][:16],
            }
            for index, miner in enumerate(committee)
        ],
    }


class CommitteeHistory:
    """SQLite-backed committee snapshot history."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_committee_history (
                    epoch INTEGER PRIMARY KEY,
                    observed_at INTEGER NOT NULL,
                    slot INTEGER NOT NULL,
                    active_miners INTEGER NOT NULL,
                    committee_size INTEGER NOT NULL,
                    committee_json TEXT NOT NULL
                )
                """
            )

    def record(self, snapshot: dict[str, Any]) -> bool:
        """Store a snapshot. Returns True when the committee changed."""

        previous = self.latest()
        committee_json = json.dumps(snapshot["committee"], sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sync_committee_history
                    (epoch, observed_at, slot, active_miners, committee_size, committee_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot["epoch"],
                    snapshot["observed_at"],
                    snapshot["slot"],
                    snapshot["active_miners"],
                    snapshot["committee_size"],
                    committee_json,
                ),
            )
        if not previous:
            return True
        return previous.get("committee") != snapshot["committee"]

    def latest(self) -> dict[str, Any] | None:
        rows = self.history(limit=1)
        return rows[0] if rows else None

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT epoch, observed_at, slot, active_miners, committee_size, committee_json
                FROM sync_committee_history
                ORDER BY epoch DESC
                LIMIT ?
                """,
                (max(limit, 1),),
            ).fetchall()
        return [
            {
                "epoch": row[0],
                "observed_at": row[1],
                "slot": row[2],
                "active_miners": row[3],
                "committee_size": row[4],
                "committee": json.loads(row[5]),
            }
            for row in rows
        ]


class SyncCommitteeTracker:
    """Collect, persist, and render sync committee rotation state."""

    def __init__(
        self,
        node_url: str = DEFAULT_NODE_URL,
        db_path: Path | str = DEFAULT_DB_PATH,
        committee_size: int = DEFAULT_COMMITTEE_SIZE,
        rotation_epochs: int = DEFAULT_ROTATION_EPOCHS,
    ):
        self.node_url = node_url.rstrip("/")
        self.history = CommitteeHistory(db_path)
        self.committee_size = committee_size
        self.rotation_epochs = rotation_epochs

    def collect(self) -> dict[str, Any]:
        epoch_payload = fetch_json(self.node_url, "/epoch")
        miners_payload = fetch_json(self.node_url, "/api/miners")
        if not isinstance(epoch_payload, dict):
            raise ValueError("/epoch did not return a JSON object")
        snapshot = build_snapshot(
            epoch_payload,
            miners_payload,
            committee_size=self.committee_size,
            rotation_epochs=self.rotation_epochs,
        )
        snapshot["rotation_changed"] = self.history.record(snapshot)
        snapshot["history"] = self.history.history()
        return snapshot


def render_metrics(snapshot: dict[str, Any]) -> str:
    """Render Prometheus text metrics for a snapshot."""

    lines = [
        "# HELP rustchain_sync_committee_epoch Current sync committee epoch.",
        "# TYPE rustchain_sync_committee_epoch gauge",
        f"rustchain_sync_committee_epoch {snapshot['epoch']}",
        "# HELP rustchain_sync_committee_members Current sync committee member count.",
        "# TYPE rustchain_sync_committee_members gauge",
        f"rustchain_sync_committee_members {snapshot['committee_size']}",
        "# HELP rustchain_sync_committee_active_miners Active miners considered for committee selection.",
        "# TYPE rustchain_sync_committee_active_miners gauge",
        f"rustchain_sync_committee_active_miners {snapshot['active_miners']}",
        "# HELP rustchain_sync_committee_slots_until_rotation Slots until the next expected committee rotation.",
        "# TYPE rustchain_sync_committee_slots_until_rotation gauge",
        f"rustchain_sync_committee_slots_until_rotation {snapshot['slots_until_rotation']}",
    ]
    for member in snapshot["committee"]:
        miner = str(member["miner_id"]).replace("\\", "\\\\").replace('"', '\\"')
        arch = str(member["arch"]).replace("\\", "\\\\").replace('"', '\\"')
        lines.append(
            "rustchain_sync_committee_position"
            f'{{miner="{miner}",arch="{arch}"}} {member["position"]}'
        )
    return "\n".join(lines) + "\n"


def render_dashboard(snapshot: dict[str, Any]) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td>{member['position']}</td>"
        f"<td><code>{member['miner_id']}</code></td>"
        f"<td>{member['arch']}</td>"
        f"<td>{member['weight']}</td>"
        f"<td><code>{member['order_hash']}</code></td>"
        "</tr>"
        for member in snapshot["committee"]
    )
    history_rows = "\n".join(
        "<tr>"
        f"<td>{item['epoch']}</td>"
        f"<td>{time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime(item['observed_at']))}</td>"
        f"<td>{item['committee_size']}</td>"
        f"<td>{item['active_miners']}</td>"
        "</tr>"
        for item in snapshot.get("history", [])
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>RustChain Sync Committee Rotation</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #172033; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; }}
    th, td {{ border: 1px solid #ccd3df; padding: .55rem .7rem; text-align: left; }}
    th {{ background: #eef2f7; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: .75rem; }}
    .stat {{ border: 1px solid #ccd3df; padding: .75rem; }}
    .label {{ color: #5b6575; font-size: .85rem; }}
    .value {{ font-size: 1.35rem; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>RustChain Sync Committee Rotation</h1>
  <section class="stats">
    <div class="stat"><div class="label">Epoch</div><div class="value">{snapshot['epoch']}</div></div>
    <div class="stat"><div class="label">Slot</div><div class="value">{snapshot['slot']}</div></div>
    <div class="stat"><div class="label">Committee</div><div class="value">{snapshot['committee_size']} / {snapshot['configured_committee_size']}</div></div>
    <div class="stat"><div class="label">Next rotation epoch</div><div class="value">{snapshot['next_rotation_epoch']}</div></div>
    <div class="stat"><div class="label">Slots until rotation</div><div class="value">{snapshot['slots_until_rotation']}</div></div>
    <div class="stat"><div class="label">Active miners</div><div class="value">{snapshot['active_miners']}</div></div>
  </section>
  <h2>Current Committee</h2>
  <table>
    <thead><tr><th>Position</th><th>Miner</th><th>Arch</th><th>Weight</th><th>Order hash</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <h2>Rotation History</h2>
  <table>
    <thead><tr><th>Epoch</th><th>Observed</th><th>Committee size</th><th>Active miners</th></tr></thead>
    <tbody>{history_rows}</tbody>
  </table>
</body>
</html>"""


def serve(tracker: SyncCommitteeTracker, host: str, port: int) -> None:
    """Serve dashboard, JSON, and metrics endpoints."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            try:
                snapshot = tracker.collect()
            except (URLError, TimeoutError, ValueError, OSError) as exc:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
                return

            if self.path == "/metrics":
                body = render_metrics(snapshot)
                content_type = "text/plain; version=0.0.4"
            elif self.path == "/api/sync-committee":
                body = json.dumps(snapshot, indent=2, sort_keys=True)
                content_type = "application/json"
            else:
                body = render_dashboard(snapshot)
                content_type = "text/html; charset=utf-8"

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    ThreadingHTTPServer((host, port), Handler).serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-url", default=DEFAULT_NODE_URL)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--committee-size", type=int, default=DEFAULT_COMMITTEE_SIZE)
    parser.add_argument("--rotation-epochs", type=int, default=DEFAULT_ROTATION_EPOCHS)
    parser.add_argument("--serve", action="store_true", help="serve dashboard and metrics")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8096)
    parser.add_argument("--metrics", action="store_true", help="print Prometheus metrics once")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tracker = SyncCommitteeTracker(
        node_url=args.node_url,
        db_path=args.db,
        committee_size=args.committee_size,
        rotation_epochs=args.rotation_epochs,
    )
    if args.serve:
        serve(tracker, args.host, args.port)
        return 0

    snapshot = tracker.collect()
    if args.metrics:
        print(render_metrics(snapshot), end="")
    else:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
