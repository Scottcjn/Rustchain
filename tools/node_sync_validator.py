#!/usr/bin/env python3
"""RustChain cross-node consistency validator.

Compares health/epoch/miner list (and optional sampled balances) across nodes.
Outputs JSON report + human-readable summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import requests

DEFAULT_NODES = [
    "https://50.28.86.131",
    "https://50.28.86.153",
    "http://76.8.228.245:8099",
]

MINER_LIST_KEYS = ("miners", "data", "items", "results")
MINER_ID_KEYS = ("miner", "miner_id", "id", "wallet", "address", "pubkey", "public_key")


@dataclass
class NodeSnapshot:
    node: str
    ok: bool
    error: str
    health: Dict[str, Any]
    epoch: Dict[str, Any]
    miners: List[str]
    balances: Dict[str, float]
    miner_total: Optional[int] = None
    miner_set_hash: str = ""
    stats: Dict[str, Any] = field(default_factory=dict)


def get_json(base: str, endpoint: str, timeout: float, verify_ssl: bool) -> Any:
    url = f"{base.rstrip('/')}{endpoint}"
    resp = requests.get(url, timeout=timeout, verify=verify_ssl)
    resp.raise_for_status()
    return resp.json()


def coerce_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def miner_id(row: Any) -> str:
    if isinstance(row, str):
        return row.strip()
    if isinstance(row, dict):
        for key in MINER_ID_KEYS:
            value = row.get(key)
            if value:
                return str(value).strip()
    return ""


def stable_miner_set_hash(miners: List[str]) -> str:
    payload = "\n".join(sorted(set(miners))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalize_miners_response(raw: Any) -> Tuple[List[str], Optional[int], str]:
    rows: List[Any] = []
    total: Optional[int] = None

    if isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict):
        for key in MINER_LIST_KEYS:
            value = raw.get(key)
            if isinstance(value, list):
                rows = value
                break

        pagination = raw.get("pagination")
        if isinstance(pagination, dict):
            total = coerce_int(pagination.get("total"))

        if total is None:
            for key in ("total", "total_miners", "count"):
                total = coerce_int(raw.get(key))
                if total is not None:
                    break

    miners = [miner_id(row) for row in rows]
    miners = [miner for miner in miners if miner]
    if total is None:
        total = len(miners)

    return miners, total, stable_miner_set_hash(miners)


def snapshot_node(node: str, timeout: float, verify_ssl: bool, sample_balances: int) -> NodeSnapshot:
    try:
        health = get_json(node, "/health", timeout, verify_ssl)
        epoch = get_json(node, "/epoch", timeout, verify_ssl)
        miners_raw = get_json(node, "/api/miners", timeout, verify_ssl)
        stats = get_json(node, "/api/stats", timeout, verify_ssl)
        miners, miner_total, miner_set_hash = normalize_miners_response(miners_raw)

        balances: Dict[str, float] = {}
        for miner in miners[:sample_balances]:
            try:
                bal = get_json(node, f"/wallet/balance?miner_id={miner}", timeout, verify_ssl)
                balances[miner] = float(bal.get("amount_rtc", 0.0)) if isinstance(bal, dict) else 0.0
            except Exception:
                balances[miner] = -1.0

        return NodeSnapshot(
            node=node,
            ok=True,
            error="",
            health=health if isinstance(health, dict) else {},
            epoch=epoch if isinstance(epoch, dict) else {},
            miners=miners,
            balances=balances,
            miner_total=miner_total,
            miner_set_hash=miner_set_hash,
            stats=stats if isinstance(stats, dict) else {},
        )
    except Exception as e:
        return NodeSnapshot(
            node=node,
            ok=False,
            error=str(e),
            health={},
            epoch={},
            miners=[],
            balances={},
            miner_total=0,
            miner_set_hash=stable_miner_set_hash([]),
            stats={},
        )


def values_differ(values: Dict[str, Any]) -> bool:
    comparable = [value for value in values.values() if value is not None]
    return bool(comparable) and len(set(values.values())) > 1


def compare_snapshots(snaps: List[NodeSnapshot], tip_drift_threshold: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "generated_at": int(time.time()),
        "nodes": [s.node for s in snaps],
        "down_nodes": [],
        "discrepancies": {
            "epoch_mismatch": [],
            "slot_mismatch": [],
            "tip_age_drift": [],
            "miner_presence_diff": [],
            "enrolled_miners_mismatch": [],
            "miner_count_mismatch": [],
            "miner_set_hash_mismatch": [],
            "stats_epoch_mismatch": [],
            "stats_total_miners_mismatch": [],
            "stats_total_balance_mismatch": [],
            "balance_mismatch": [],
        },
    }

    ok_snaps = [s for s in snaps if s.ok]
    for s in snaps:
        if not s.ok:
            out["down_nodes"].append({"node": s.node, "error": s.error})

    if len(ok_snaps) < 2:
        return out

    # Epoch and slot mismatch
    epoch_values = {s.node: int(s.epoch.get("epoch", -1)) for s in ok_snaps}
    slot_values = {s.node: int(s.epoch.get("slot", -1)) for s in ok_snaps}
    if len(set(epoch_values.values())) > 1:
        out["discrepancies"]["epoch_mismatch"].append(epoch_values)
    if len(set(slot_values.values())) > 1:
        out["discrepancies"]["slot_mismatch"].append(slot_values)

    enrolled_values = {s.node: coerce_int(s.epoch.get("enrolled_miners")) for s in ok_snaps}
    if values_differ(enrolled_values):
        out["discrepancies"]["enrolled_miners_mismatch"].append(enrolled_values)

    # Tip age drift
    tip_values = {s.node: int(s.health.get("tip_age_slots", -1)) for s in ok_snaps}
    valid_tip = [v for v in tip_values.values() if v >= 0]
    if valid_tip:
        drift = max(valid_tip) - min(valid_tip)
        if drift > tip_drift_threshold:
            out["discrepancies"]["tip_age_drift"].append({"values": tip_values, "drift": drift})

    miner_total_values = {s.node: s.miner_total for s in ok_snaps}
    if values_differ(miner_total_values):
        out["discrepancies"]["miner_count_mismatch"].append(miner_total_values)

    miner_hash_values = {s.node: s.miner_set_hash or stable_miner_set_hash(s.miners) for s in ok_snaps}
    if values_differ(miner_hash_values):
        out["discrepancies"]["miner_set_hash_mismatch"].append(miner_hash_values)

    stats_epoch_values = {s.node: coerce_int(s.stats.get("epoch")) for s in ok_snaps}
    if values_differ(stats_epoch_values):
        out["discrepancies"]["stats_epoch_mismatch"].append(stats_epoch_values)

    stats_total_miners_values = {s.node: coerce_int(s.stats.get("total_miners")) for s in ok_snaps}
    if values_differ(stats_total_miners_values):
        out["discrepancies"]["stats_total_miners_mismatch"].append(stats_total_miners_values)

    stats_total_balance_values = {s.node: coerce_float(s.stats.get("total_balance")) for s in ok_snaps}
    if values_differ(stats_total_balance_values):
        out["discrepancies"]["stats_total_balance_mismatch"].append(stats_total_balance_values)

    # Miners present on one node but not another
    all_miners = sorted(set(m for s in ok_snaps for m in s.miners))
    for miner in all_miners:
        present = [s.node for s in ok_snaps if miner in s.miners]
        if len(present) != len(ok_snaps):
            out["discrepancies"]["miner_presence_diff"].append(
                {"miner": miner, "present_on": present, "missing_on": [s.node for s in ok_snaps if s.node not in present]}
            )

    # Balance mismatch for sampled miners present on all nodes
    common_miners = set(ok_snaps[0].balances.keys())
    for s in ok_snaps[1:]:
        common_miners &= set(s.balances.keys())
    for miner in sorted(common_miners):
        vals = {s.node: s.balances.get(miner, -1.0) for s in ok_snaps}
        good = [v for v in vals.values() if v >= 0]
        if good and (max(good) - min(good) > 1e-9):
            out["discrepancies"]["balance_mismatch"].append({"miner": miner, "balances": vals})

    return out


def build_summary(report: Dict[str, Any]) -> str:
    d = report.get("discrepancies", {})
    lines = []
    lines.append(f"Generated at: {report.get('generated_at')}")
    lines.append(f"Nodes checked: {', '.join(report.get('nodes', []))}")
    if report.get("down_nodes"):
        lines.append("Down/unreachable nodes:")
        for item in report["down_nodes"]:
            lines.append(f"- {item['node']}: {item['error']}")

    counts = {
        "epoch_mismatch": len(d.get("epoch_mismatch", [])),
        "slot_mismatch": len(d.get("slot_mismatch", [])),
        "tip_age_drift": len(d.get("tip_age_drift", [])),
        "miner_presence_diff": len(d.get("miner_presence_diff", [])),
        "enrolled_miners_mismatch": len(d.get("enrolled_miners_mismatch", [])),
        "miner_count_mismatch": len(d.get("miner_count_mismatch", [])),
        "miner_set_hash_mismatch": len(d.get("miner_set_hash_mismatch", [])),
        "stats_epoch_mismatch": len(d.get("stats_epoch_mismatch", [])),
        "stats_total_miners_mismatch": len(d.get("stats_total_miners_mismatch", [])),
        "stats_total_balance_mismatch": len(d.get("stats_total_balance_mismatch", [])),
        "balance_mismatch": len(d.get("balance_mismatch", [])),
    }
    lines.append("Discrepancy counts:")
    for k, v in counts.items():
        lines.append(f"- {k}: {v}")

    if sum(counts.values()) == 0 and not report.get("down_nodes"):
        lines.append("Status: OK (no discrepancies detected)")
    else:
        lines.append("Status: ATTENTION (review discrepancy details in JSON)")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="RustChain cross-node DB/API sync validator")
    parser.add_argument("--nodes", nargs="+", default=DEFAULT_NODES)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--verify-ssl", action="store_true", help="enable TLS verification")
    parser.add_argument("--tip-drift-threshold", type=int, default=5)
    parser.add_argument("--sample-balances", type=int, default=5)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-text", default="")
    args = parser.parse_args()

    verify_ssl = bool(args.verify_ssl)
    if not verify_ssl:
        requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
    snaps = [snapshot_node(node, args.timeout, verify_ssl, args.sample_balances) for node in args.nodes]
    report = compare_snapshots(snaps, args.tip_drift_threshold)
    summary = build_summary(report)

    print(summary)
    print("\nJSON report:")
    print(json.dumps(report, indent=2))

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    if args.output_text:
        with open(args.output_text, "w", encoding="utf-8") as f:
            f.write(summary + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
