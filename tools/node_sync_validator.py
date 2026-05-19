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
    miner_pages: List[Dict[str, Optional[int]]] = field(default_factory=list)
    miner_set_complete: bool = True
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


def normalize_miners_page(raw: Any) -> Tuple[List[str], Optional[int], Dict[str, Optional[int]]]:
    rows: List[Any] = []
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    count: Optional[int] = None

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
            limit = coerce_int(pagination.get("limit"))
            offset = coerce_int(pagination.get("offset"))
            count = coerce_int(pagination.get("count"))

        if total is None:
            for key in ("total", "total_miners", "count"):
                total = coerce_int(raw.get(key))
                if total is not None:
                    break
        if limit is None:
            limit = coerce_int(raw.get("limit"))
        if offset is None:
            offset = coerce_int(raw.get("offset"))
        if count is None:
            count = coerce_int(raw.get("count"))

    miners = [miner_id(row) for row in rows]
    miners = [miner for miner in miners if miner]
    if total is None:
        total = len(miners)
    metadata = {
        "total": total,
        "limit": limit,
        "offset": offset,
        "count": count if count is not None else len(rows),
        "row_count": len(rows),
    }

    return miners, total, metadata


def normalize_miners_response(raw: Any) -> Tuple[List[str], Optional[int], str]:
    miners, total, _metadata = normalize_miners_page(raw)
    return miners, total, stable_miner_set_hash(miners)


def fetch_miners(
    node: str,
    timeout: float,
    verify_ssl: bool,
) -> Tuple[List[str], Optional[int], str, List[Dict[str, Optional[int]]], bool]:
    raw = get_json(node, "/api/miners", timeout, verify_ssl)
    miners, total, first_page = normalize_miners_page(raw)
    pages = [first_page]

    current_offset = first_page.get("offset") or 0
    page_limit = first_page.get("limit") or max(first_page.get("row_count") or len(miners), 1)
    rows_seen = (first_page.get("row_count") or 0)
    next_offset = current_offset + rows_seen
    complete = True

    while total is not None and next_offset < total:
        if rows_seen <= 0:
            complete = False
            break

        page_raw = get_json(node, f"/api/miners?limit={page_limit}&offset={next_offset}", timeout, verify_ssl)
        page_miners, page_total, page_metadata = normalize_miners_page(page_raw)
        pages.append(page_metadata)
        miners.extend(page_miners)

        if page_total is not None:
            total = page_total

        row_count = page_metadata.get("row_count") or 0
        if row_count <= 0:
            complete = False
            break
        current_offset = page_metadata.get("offset")
        next_offset = (current_offset if current_offset is not None else next_offset) + row_count

    return miners, total, stable_miner_set_hash(miners), pages, complete


def snapshot_node(node: str, timeout: float, verify_ssl: bool, sample_balances: int) -> NodeSnapshot:
    try:
        health = get_json(node, "/health", timeout, verify_ssl)
        epoch = get_json(node, "/epoch", timeout, verify_ssl)
        stats = get_json(node, "/api/stats", timeout, verify_ssl)
        miners, miner_total, miner_set_hash, miner_pages, miner_set_complete = fetch_miners(node, timeout, verify_ssl)

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
            miner_pages=miner_pages,
            miner_set_complete=miner_set_complete,
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
            miner_pages=[],
            miner_set_complete=False,
            stats={},
        )


def values_differ(values: Dict[str, Any]) -> bool:
    comparable = [value for value in values.values() if value is not None]
    return bool(comparable) and len(set(comparable)) > 1


def epoch_slot_key(snapshot: NodeSnapshot) -> Tuple[Optional[int], Optional[int]]:
    return (
        coerce_int(snapshot.epoch.get("epoch")),
        coerce_int(snapshot.epoch.get("slot")),
    )


def snapshot_metadata(snapshot: NodeSnapshot) -> Dict[str, Any]:
    return {
        "node": snapshot.node,
        "ok": snapshot.ok,
        "epoch": coerce_int(snapshot.epoch.get("epoch")),
        "slot": coerce_int(snapshot.epoch.get("slot")),
        "miner_count": len(snapshot.miners),
        "miner_total": snapshot.miner_total,
        "miner_set_hash": snapshot.miner_set_hash,
        "miner_set_complete": snapshot.miner_set_complete,
        "miner_pages": snapshot.miner_pages,
        "stats_epoch": coerce_int(snapshot.stats.get("epoch")),
        "stats_total_miners": coerce_int(snapshot.stats.get("total_miners")),
        "stats_total_balance": coerce_float(snapshot.stats.get("total_balance")),
    }


def compare_snapshots(snaps: List[NodeSnapshot], tip_drift_threshold: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "generated_at": int(time.time()),
        "nodes": [s.node for s in snaps],
        "snapshots": [snapshot_metadata(s) for s in snaps],
        "same_epoch_slot_groups": [],
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

    # Tip age drift
    tip_values = {s.node: int(s.health.get("tip_age_slots", -1)) for s in ok_snaps}
    valid_tip = [v for v in tip_values.values() if v >= 0]
    if valid_tip:
        drift = max(valid_tip) - min(valid_tip)
        if drift > tip_drift_threshold:
            out["discrepancies"]["tip_age_drift"].append({"values": tip_values, "drift": drift})

    grouped: Dict[Tuple[Optional[int], Optional[int]], List[NodeSnapshot]] = {}
    for snap in ok_snaps:
        grouped.setdefault(epoch_slot_key(snap), []).append(snap)

    def group_sort_key(item: Tuple[Tuple[Optional[int], Optional[int]], List[NodeSnapshot]]) -> Tuple[bool, int, bool, int]:
        (epoch, slot), _snaps = item
        return (epoch is None, epoch or -1, slot is None, slot or -1)

    for (epoch, slot), group in sorted(grouped.items(), key=group_sort_key):
        if len(group) < 2:
            continue

        out["same_epoch_slot_groups"].append({
            "epoch": epoch,
            "slot": slot,
            "nodes": [s.node for s in group],
        })

        enrolled_values = {s.node: coerce_int(s.epoch.get("enrolled_miners")) for s in group}
        if values_differ(enrolled_values):
            out["discrepancies"]["enrolled_miners_mismatch"].append(enrolled_values)

        miner_total_values = {s.node: s.miner_total for s in group}
        if values_differ(miner_total_values):
            out["discrepancies"]["miner_count_mismatch"].append(miner_total_values)

        miner_hash_values = {s.node: s.miner_set_hash or stable_miner_set_hash(s.miners) for s in group}
        if values_differ(miner_hash_values):
            out["discrepancies"]["miner_set_hash_mismatch"].append(miner_hash_values)

        stats_epoch_values = {s.node: coerce_int(s.stats.get("epoch")) for s in group}
        if values_differ(stats_epoch_values):
            out["discrepancies"]["stats_epoch_mismatch"].append(stats_epoch_values)

        stats_total_miners_values = {s.node: coerce_int(s.stats.get("total_miners")) for s in group}
        if values_differ(stats_total_miners_values):
            out["discrepancies"]["stats_total_miners_mismatch"].append(stats_total_miners_values)

        stats_total_balance_values = {s.node: coerce_float(s.stats.get("total_balance")) for s in group}
        if values_differ(stats_total_balance_values):
            out["discrepancies"]["stats_total_balance_mismatch"].append(stats_total_balance_values)

        # Miners present on one same-epoch/same-slot node but not another
        all_miners = sorted(set(m for s in group for m in s.miners))
        for miner in all_miners:
            present = [s.node for s in group if miner in s.miners]
            if len(present) != len(group):
                out["discrepancies"]["miner_presence_diff"].append(
                    {"miner": miner, "present_on": present, "missing_on": [s.node for s in group if s.node not in present]}
                )

        # Balance mismatch for sampled miners present on all same-epoch/same-slot nodes
        common_miners = set(group[0].balances.keys())
        for s in group[1:]:
            common_miners &= set(s.balances.keys())
        for miner in sorted(common_miners):
            vals = {s.node: s.balances.get(miner, -1.0) for s in group}
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
