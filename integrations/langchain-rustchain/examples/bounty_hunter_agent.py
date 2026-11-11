#!/usr/bin/env python3
"""
Example LangChain RustChain Bounty Hunter Agent (`Bounty #3074`).
Checks node health, current epoch, wallet balance, and selects the highest-reward open RTC bounty.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from langchain_rustchain import RustChainTool  # noqa: E402


def run_bounty_discovery_workflow(
    wallet_id: str = "RTCfe0ac752b80e543048c0d91e7dddd1277678b8a5",
    limit: int = 5,
    tool: RustChainTool | None = None,
) -> dict:
    rc = tool or RustChainTool()
    health = rc.get_node_health()
    epoch = rc.get_current_epoch()
    balance = rc.check_balance(wallet_id)
    bounties = rc.list_bounties(limit=limit)
    ranked = sorted(bounties, key=lambda b: (b.get("reward_rtc", 0.0), -b.get("comments", 0)), reverse=True)
    recommended = ranked[0] if ranked else None
    return {
        "wallet_id": wallet_id,
        "balance_rtc": balance,
        "node_ok": bool(health.get("ok")),
        "node_version": health.get("version"),
        "epoch": epoch.get("epoch"),
        "open_bounties_checked": len(bounties),
        "recommended_bounty": recommended,
    }


if __name__ == "__main__":
    report = run_bounty_discovery_workflow()
    print(json.dumps(report, indent=2))
