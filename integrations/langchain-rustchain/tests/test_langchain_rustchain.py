#!/usr/bin/env python3
"""
Unit tests for `langchain-rustchain` (`Scottcjn/rustchain-bounties#3074`).
"""

from __future__ import annotations

from pathlib import Path
import sys

PKG_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG_ROOT))

from examples.bounty_hunter_agent import run_bounty_discovery_workflow  # noqa: E402
from langchain_rustchain import RustChainTool, RustChainToolkit  # noqa: E402


def test_rustchain_tool_methods_and_dispatch(monkeypatch):
    tool = RustChainTool(node_url="https://50.28.86.131")

    def fake_http_get(url, headers=None):
        if "/wallet/balance" in url:
            return {"miner_id": "RTCfe0ac752b80e543048c0d91e7dddd1277678b8a5", "amount_rtc": 42.5, "amount_i64": 42500000}
        if "/health" in url:
            return {"ok": True, "version": "2.2.1-rip200", "db_rw": True, "uptime_s": 1250000}
        if "/epoch" in url:
            return {"epoch": 343, "slot": 49520, "enrolled_miners": 15, "epoch_pot": 1.5}
        if "rustchain-bounties/issues" in url:
            return [
                {
                    "number": 3074,
                    "title": "[AGENT-BOUNTY: 17 RTC] Integrate RustChain as a native LangChain tool",
                    "body": "17 RTC on delivery.",
                    "html_url": "https://github.com/Scottcjn/rustchain-bounties/issues/3074",
                    "labels": [{"name": "bounty"}],
                    "comments": 12,
                },
                {
                    "number": 16271,
                    "title": "[BOUNTY: 35 RTC] Harden x86 vintage-arch reward validation",
                    "body": "35 RTC reward.",
                    "html_url": "https://github.com/Scottcjn/rustchain-bounties/issues/16271",
                    "labels": [{"name": "bounty"}, {"name": "open"}],
                    "comments": 5,
                },
            ]
        return {}

    monkeypatch.setattr(tool, "_http_get_json", fake_http_get)

    bal = tool.check_balance("RTCfe0ac752b80e543048c0d91e7dddd1277678b8a5")
    assert bal == 42.5
    assert tool._run(action="balance", wallet_id="RTCfe0ac752b80e543048c0d91e7dddd1277678b8a5") == 42.5

    health = tool.get_node_health()
    assert health["ok"] is True
    assert health["version"] == "2.2.1-rip200"

    epoch = tool.get_current_epoch()
    assert epoch["epoch"] == 343

    bounties = tool.list_bounties(limit=2)
    assert len(bounties) == 2
    assert bounties[0]["issue_number"] == 3074
    assert bounties[0]["reward_rtc"] == 17.0
    assert bounties[1]["reward_rtc"] == 35.0

    # Test toolkit and example agent workflow
    tk = RustChainToolkit()
    tools = tk.get_tools()
    assert len(tools) == 4
    assert {t.name for t in tools} == {
        "rustchain_check_balance",
        "rustchain_list_bounties",
        "rustchain_node_health",
        "rustchain_current_epoch",
    }

    report = run_bounty_discovery_workflow(tool=tool)
    assert report["balance_rtc"] == 42.5
    assert report["node_ok"] is True
    assert report["recommended_bounty"]["issue_number"] == 16271
    assert report["recommended_bounty"]["reward_rtc"] == 35.0
