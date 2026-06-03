# SPDX-License-Identifier: MIT
"""
Round-robin proposer duty calendar helpers.

RustChain's P2P epoch proposer is selected deterministically from the sorted
node set with ``nodes[epoch % len(nodes)]``. These helpers expose that schedule
for dashboards without importing the full P2P node runtime.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse


DEFAULT_LOOKAHEAD = 12
DEFAULT_HISTORY_LIMIT = 8


def parse_peer_config(raw_peers: str) -> Dict[str, str]:
    """Parse RC_P2P_PEERS entries formatted as node_id=url."""
    peers: Dict[str, str] = {}
    for item in (raw_peers or "").split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            continue
        node_id, peer_url = (part.strip() for part in item.split("=", 1))
        if not node_id or not peer_url:
            continue
        parsed = urlparse(peer_url)
        if parsed.scheme and parsed.netloc:
            peers[node_id] = peer_url.rstrip("/")
    return peers


def normalize_nodes(node_id: str, peers: Optional[Dict[str, str]] = None) -> List[str]:
    """Return the sorted node IDs used by round-robin proposer selection."""
    node_ids = set((peers or {}).keys())
    if node_id:
        node_ids.add(node_id)
    return sorted(node_ids)


def build_proposer_schedule(
    current_epoch: int,
    nodes: Iterable[str],
    lookahead: int = DEFAULT_LOOKAHEAD,
) -> List[Dict[str, object]]:
    """Build proposer duties from current_epoch through the lookahead window."""
    node_list = sorted(set(nodes))
    if not node_list:
        return []

    start_epoch = max(int(current_epoch), 0)
    window = max(int(lookahead), 0)
    schedule = []
    for offset in range(window + 1):
        epoch = start_epoch + offset
        proposer = node_list[epoch % len(node_list)]
        schedule.append(
            {
                "epoch": epoch,
                "proposer": proposer,
                "offset": offset,
                "is_current": offset == 0,
            }
        )
    return schedule


def load_vote_history(
    db_path: str,
    current_epoch: int,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
) -> List[Dict[str, object]]:
    """Load recent proposer vote history from p2p_epoch_votes when available."""
    if not db_path:
        return []

    lower_bound = max(int(current_epoch) - max(int(history_limit), 0), 0)
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT epoch, proposal_hash, voter, vote, ts
                FROM p2p_epoch_votes
                WHERE epoch >= ? AND epoch <= ?
                ORDER BY epoch DESC, ts DESC
                """,
                (lower_bound, int(current_epoch)),
            ).fetchall()
    except sqlite3.Error:
        return []

    grouped: Dict[tuple, Dict[str, object]] = {}
    vote_counts: Dict[tuple, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for epoch, proposal_hash, voter, vote, ts in rows:
        key = (int(epoch), str(proposal_hash))
        grouped.setdefault(
            key,
            {
                "epoch": int(epoch),
                "proposal_hash": str(proposal_hash),
                "latest_ts": int(ts or 0),
                "voters": [],
            },
        )
        grouped[key]["latest_ts"] = max(int(grouped[key]["latest_ts"]), int(ts or 0))
        grouped[key]["voters"].append(str(voter))
        vote_counts[key][str(vote)] += 1

    history = []
    for key, item in grouped.items():
        item["votes"] = dict(sorted(vote_counts[key].items()))
        item["vote_count"] = sum(vote_counts[key].values())
        item["voters"] = sorted(set(item["voters"]))
        history.append(item)

    history.sort(key=lambda item: (item["epoch"], item["latest_ts"]), reverse=True)
    return history


def build_proposer_duty_calendar(
    current_epoch: int,
    node_id: str,
    peers: Optional[Dict[str, str]] = None,
    db_path: str = "",
    lookahead: int = DEFAULT_LOOKAHEAD,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
) -> Dict[str, object]:
    """Return dashboard-ready proposer duty calendar, metrics, and history."""
    nodes = normalize_nodes(node_id, peers)
    schedule = build_proposer_schedule(current_epoch, nodes, lookahead)
    current_duty = schedule[0] if schedule else None

    return {
        "current_epoch": max(int(current_epoch), 0),
        "node_id": node_id,
        "nodes": nodes,
        "node_count": len(nodes),
        "lookahead": max(int(lookahead), 0),
        "current_proposer": current_duty["proposer"] if current_duty else None,
        "current_node_is_proposer": (
            bool(current_duty) and current_duty["proposer"] == node_id
        ),
        "schedule": schedule,
        "history": load_vote_history(db_path, current_epoch, history_limit),
        "metrics": {
            "scheduled_epochs": len(schedule),
            "history_limit": max(int(history_limit), 0),
            "history_available": bool(db_path),
        },
    }
