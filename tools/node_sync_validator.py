#!/usr/bin/env python3
"""RustChain cross-node consistency validator.

Compares health/epoch/miner list (and optional sampled balances) across nodes.
Outputs JSON report + human-readable summary.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

DEFAULT_NODES = [
    "https://50.28.86.131",
    "https://50.28.86.153",
    "http://76.8.228.245:8099",
]


@dataclass
class NodeSnapshot:
    node: str
    ok: bool
    error: str
    health: Dict[str, Any]
    epoch: Dict[str, Any]
    miners: List[str]
    balances: Dict[str, float]


def get_json(base: str, endpoint: str, timeout: float, verify_ssl: bool) -> Any:
    url = f"{base.rstrip('/')}{endpoint}"
    resp = requests.get(url, timeout=timeout, verify=verify_ssl)
    resp.raise_for_status()
    return resp.json()


def snapshot_node(node: str, timeout: float, verify_ssl: bool, sample_balances: int) -> NodeSnapshot:
    try:
        health = get_json(node, "/health", timeout, verify_ssl)
        epoch = get_json(node, "/epoch", timeout, verify_ssl)
        miners_raw = get_json(node, "/api/miners", timeout, verify_ssl)

        miners: List[str] = []
        if isinstance(miners_raw, list):
            miners = [str(m.get("miner") or m.get("miner_id") or "") for m in miners_raw]
            miners = [m for m in miners if m]

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
        )


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
