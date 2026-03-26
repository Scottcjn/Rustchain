#!/usr/bin/env python3
"""
Beacon Dashboard Helpers — Data parsing, aggregation, and export logic.

Pure functions for querying beacon_envelopes, computing transport health,
agent rankings, and exporting snapshots.  No curses dependency so these
can be unit-tested headlessly.
"""

import csv
import io
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Constants ────────────────────────────────────────────────────────

VALID_KINDS = {"hello", "heartbeat", "want", "bounty", "mayday", "accord", "pushback"}

DEFAULT_DB_PATH = os.environ.get(
    "RUSTCHAIN_DB",
    os.path.join(os.path.dirname(__file__), "..", "..", "rustchain_v2.db"),
)

# Transports we recognise (others filed under "other")
KNOWN_TRANSPORTS = {"discord", "telegram", "irc", "websocket", "http", "beacon"}

# High-value tip threshold (RTC) that triggers a sound alert
HIGH_VALUE_TIP_THRESHOLD = 50.0

# ── Database helpers ─────────────────────────────────────────────────


def open_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a read-only connection (WAL mode safe for concurrent reads)."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_open_db(db_path: str) -> Optional[sqlite3.Connection]:
    """Open DB or return None if the file doesn't exist yet."""
    if not Path(db_path).exists():
        return None
    try:
        return open_db(db_path)
    except sqlite3.OperationalError:
        return None


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Check if a table exists in the database."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


# ── Envelope queries ─────────────────────────────────────────────────


def fetch_recent_envelopes(
    conn: sqlite3.Connection,
    limit: int = 200,
    since_ts: Optional[int] = None,
    kind_filter: Optional[str] = None,
    agent_filter: Optional[str] = None,
    transport_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch recent beacon envelopes with optional filters.

    Returns list of dicts with keys:
        id, agent_id, kind, transport, nonce, payload_hash, received_at, amount
    """
    if not _table_exists(conn, "beacon_envelopes"):
        return []

    clauses: list[str] = []
    params: list[Any] = []

    if since_ts is not None:
        clauses.append("received_at > ?")
        params.append(since_ts)
    if kind_filter:
        clauses.append("kind = ?")
        params.append(kind_filter.lower())
    if agent_filter:
        clauses.append("agent_id LIKE ?")
        params.append(f"%{agent_filter}%")

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM beacon_envelopes{where} ORDER BY received_at DESC LIMIT ?"
    params.append(limit)

    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []

    envelopes = []
    for row in rows:
        env = dict(row)
        # Extract transport from envelope data if available
        transport = _extract_transport(env)
        if transport_filter and transport != transport_filter.lower():
            continue
        env["transport"] = transport
        env["amount"] = _extract_amount(env)
        envelopes.append(env)

    return envelopes


def _extract_transport(env: Dict[str, Any]) -> str:
    """Best-effort transport extraction from envelope metadata."""
    # Check if there's a transport field directly
    if "transport" in env and env["transport"]:
        t = str(env["transport"]).lower()
        return t if t in KNOWN_TRANSPORTS else "other"

    # Heuristic: look at agent_id prefix or nonce patterns
    agent_id = env.get("agent_id", "")
    if "discord" in agent_id.lower():
        return "discord"
    if "tg_" in agent_id.lower() or "telegram" in agent_id.lower():
        return "telegram"
    if "irc" in agent_id.lower():
        return "irc"
    if "ws_" in agent_id.lower():
        return "websocket"

    return "beacon"


def _extract_amount(env: Dict[str, Any]) -> float:
    """Extract RTC amount from envelope if it's a tip or bounty."""
    for key in ("amount", "reward_rtc", "rtc_amount", "tip_amount"):
        val = env.get(key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return 0.0


def count_envelopes_by_kind(envelopes: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count envelopes grouped by kind."""
    return dict(Counter(e.get("kind", "unknown") for e in envelopes))


def count_envelopes_by_transport(envelopes: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count envelopes grouped by transport."""
    return dict(Counter(e.get("transport", "unknown") for e in envelopes))


# ── Transport health ─────────────────────────────────────────────────


class TransportHealth:
    """Health snapshot for a single transport."""

    __slots__ = (
        "name",
        "total",
        "last_seen",
        "kinds",
        "top_agents",
        "throughput_per_min",
        "mayday_count",
        "high_value_tips",
    )

    def __init__(self, name: str):
        self.name = name
        self.total = 0
        self.last_seen: Optional[int] = None
        self.kinds: Dict[str, int] = {}
        self.top_agents: List[Tuple[str, int]] = []
        self.throughput_per_min = 0.0
        self.mayday_count = 0
        self.high_value_tips: List[Dict[str, Any]] = []

    @property
    def status(self) -> str:
        """Derive health status from last-seen timestamp."""
        if self.last_seen is None:
            return "unknown"
        age = time.time() - self.last_seen
        if age < 120:
            return "healthy"
        if age < 600:
            return "degraded"
        return "offline"

    @property
    def status_icon(self) -> str:
        return {"healthy": "●", "degraded": "◐", "offline": "○", "unknown": "?"}[
            self.status
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "total": self.total,
            "last_seen": self.last_seen,
            "kinds": self.kinds,
            "top_agents": self.top_agents,
            "throughput_per_min": round(self.throughput_per_min, 2),
            "mayday_count": self.mayday_count,
        }


def compute_transport_health(
    envelopes: List[Dict[str, Any]],
) -> Dict[str, TransportHealth]:
    """Compute per-transport health metrics from envelopes."""

    by_transport: Dict[str, list] = defaultdict(list)
    for env in envelopes:
        transport = env.get("transport", "beacon")
        by_transport[transport].append(env)

    result: Dict[str, TransportHealth] = {}
    now = time.time()

    for transport_name, envs in by_transport.items():
        h = TransportHealth(transport_name)
        h.total = len(envs)

        # Last seen
        timestamps = [e.get("received_at", 0) for e in envs if e.get("received_at")]
        if timestamps:
            h.last_seen = max(timestamps)
            oldest = min(timestamps)
            window_min = max((now - oldest) / 60.0, 1.0)
            h.throughput_per_min = h.total / window_min

        # Kind breakdown
        h.kinds = dict(Counter(e.get("kind", "unknown") for e in envs))

        # Top agents
        agent_counts = Counter(e.get("agent_id", "unknown") for e in envs)
        h.top_agents = agent_counts.most_common(5)

        # Mayday count
        h.mayday_count = sum(1 for e in envs if e.get("kind") == "mayday")

        # High-value tips
        h.high_value_tips = [
            e for e in envs if e.get("amount", 0) >= HIGH_VALUE_TIP_THRESHOLD
        ]

        result[transport_name] = h

    return result


# ── Top agents ───────────────────────────────────────────────────────


def compute_top_agents(
    envelopes: List[Dict[str, Any]], limit: int = 10
) -> List[Dict[str, Any]]:
    """Rank agents by envelope volume with kind breakdown."""

    agent_data: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "kinds": Counter(), "last_seen": 0}
    )

    for env in envelopes:
        agent_id = env.get("agent_id", "unknown")
        agent_data[agent_id]["total"] += 1
        agent_data[agent_id]["kinds"][env.get("kind", "unknown")] += 1
        ts = env.get("received_at", 0)
        if ts > agent_data[agent_id]["last_seen"]:
            agent_data[agent_id]["last_seen"] = ts

    ranked = sorted(agent_data.items(), key=lambda x: x[1]["total"], reverse=True)

    return [
        {
            "agent_id": agent_id,
            "total": data["total"],
            "kinds": dict(data["kinds"]),
            "last_seen": data["last_seen"],
        }
        for agent_id, data in ranked[:limit]
    ]


# ── Alerts ───────────────────────────────────────────────────────────


def check_alerts(
    envelopes: List[Dict[str, Any]], last_alert_ts: int = 0
) -> List[Dict[str, Any]]:
    """Check for envelopes that should trigger sound alerts.

    Returns list of alert dicts with keys: type, envelope, message
    """
    alerts: list = []
    for env in envelopes:
        ts = env.get("received_at", 0)
        if ts <= last_alert_ts:
            continue

        if env.get("kind") == "mayday":
            alerts.append(
                {
                    "type": "mayday",
                    "envelope": env,
                    "message": f"MAYDAY from {env.get('agent_id', '?')}",
                }
            )

        amount = env.get("amount", 0)
        if amount >= HIGH_VALUE_TIP_THRESHOLD:
            alerts.append(
                {
                    "type": "high_value",
                    "envelope": env,
                    "message": f"High-value tip: {amount} RTC from {env.get('agent_id', '?')}",
                }
            )

    return alerts


# ── Filter / Search ──────────────────────────────────────────────────


def parse_filter(query: str) -> Dict[str, Optional[str]]:
    """Parse filter query into structured filters.

    Supports:
        kind:mayday
        agent:bcn_abc123
        transport:discord
        free text (fuzzy match)
    """
    result: Dict[str, Optional[str]] = {
        "kind": None,
        "agent": None,
        "transport": None,
        "text": None,
    }

    if not query or not query.strip():
        return result

    parts = query.strip().split()
    free_parts: list[str] = []

    for part in parts:
        if ":" in part:
            key, _, value = part.partition(":")
            key = key.lower()
            if key == "kind" and value.lower() in VALID_KINDS:
                result["kind"] = value.lower()
            elif key == "agent":
                result["agent"] = value
            elif key == "transport":
                result["transport"] = value.lower()
            else:
                free_parts.append(part)
        else:
            free_parts.append(part)

    if free_parts:
        result["text"] = " ".join(free_parts)

    return result


def apply_filter(
    envelopes: List[Dict[str, Any]], query: str
) -> List[Dict[str, Any]]:
    """Apply a filter query to a list of envelopes."""
    if not query or not query.strip():
        return envelopes

    filters = parse_filter(query)
    result = envelopes

    if filters["kind"]:
        result = [e for e in result if e.get("kind") == filters["kind"]]

    if filters["agent"]:
        agent_q = filters["agent"].lower()
        result = [e for e in result if agent_q in e.get("agent_id", "").lower()]

    if filters["transport"]:
        result = [
            e for e in result if e.get("transport", "").lower() == filters["transport"]
        ]

    if filters["text"]:
        text_q = filters["text"].lower()
        result = [
            e
            for e in result
            if any(
                text_q in str(v).lower()
                for v in (
                    e.get("agent_id", ""),
                    e.get("kind", ""),
                    e.get("transport", ""),
                    e.get("nonce", ""),
                )
            )
        ]

    return result


# ── Export ────────────────────────────────────────────────────────────


def export_csv(
    envelopes: List[Dict[str, Any]],
    transport_health: Dict[str, TransportHealth],
    output_dir: str = ".",
) -> str:
    """Export current dashboard view to CSV. Returns filename."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"beacon_snapshot_{ts}.csv"
    filepath = os.path.join(output_dir, filename)

    fields = [
        "agent_id",
        "kind",
        "transport",
        "received_at",
        "amount",
        "nonce",
        "payload_hash",
    ]

    with open(filepath, "w", newline="") as f:
        # Write transport health summary first
        f.write("# Transport Health Summary\n")
        summary_writer = csv.writer(f)
        summary_writer.writerow(
            ["transport", "status", "total", "throughput/min", "mayday_count"]
        )
        for h in transport_health.values():
            summary_writer.writerow(
                [h.name, h.status, h.total, f"{h.throughput_per_min:.2f}", h.mayday_count]
            )
        f.write("\n# Envelope Log\n")

        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for env in envelopes:
            writer.writerow(env)

    return filepath


def export_json(
    envelopes: List[Dict[str, Any]],
    transport_health: Dict[str, TransportHealth],
    top_agents: List[Dict[str, Any]],
    output_dir: str = ".",
) -> str:
    """Export current dashboard view to JSON. Returns filename."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"beacon_snapshot_{ts}.json"
    filepath = os.path.join(output_dir, filename)

    snapshot = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "transport_health": {
            name: h.to_dict() for name, h in transport_health.items()
        },
        "top_agents": top_agents,
        "envelopes": envelopes,
        "summary": {
            "total_envelopes": len(envelopes),
            "kinds": dict(Counter(e.get("kind", "unknown") for e in envelopes)),
            "transports": dict(
                Counter(e.get("transport", "unknown") for e in envelopes)
            ),
        },
    }

    with open(filepath, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)

    return filepath


# ── Formatting helpers ───────────────────────────────────────────────


def format_timestamp(ts: Optional[int]) -> str:
    """Format a Unix timestamp to human-readable string."""
    if ts is None or ts == 0:
        return "never"
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%H:%M:%S")
    except (ValueError, OSError):
        return "invalid"


def format_age(ts: Optional[int]) -> str:
    """Format a timestamp as a relative age string."""
    if ts is None or ts == 0:
        return "—"
    age = time.time() - ts
    if age < 0:
        return "future"
    if age < 60:
        return f"{int(age)}s ago"
    if age < 3600:
        return f"{int(age / 60)}m ago"
    if age < 86400:
        return f"{int(age / 3600)}h ago"
    return f"{int(age / 86400)}d ago"


def truncate(s: str, max_len: int) -> str:
    """Truncate string with ellipsis."""
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"
