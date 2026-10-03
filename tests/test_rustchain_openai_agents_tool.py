"""
tests/test_rustchain_openai_agents_tool.py

Unit and mock regression tests for the OpenAI Agents SDK RustChain tool wrapper (Bounty #13952).
"""

import json
from unittest.mock import MagicMock, patch
import pytest
from integrations.rustchain_openai_agents import RustChainOpenAIAgentsTools


@pytest.fixture
def tools():
    return RustChainOpenAIAgentsTools(base_url="https://mock.rustchain.org")


def test_init_defaults():
    t = RustChainOpenAIAgentsTools()
    assert t.base_url == "https://rustchain.org"
    assert t.bounty_repo == "Scottcjn/rustchain-bounties"
    assert t.timeout == 10.0


def test_check_balance_empty_wallet(tools):
    res = tools.check_balance("")
    assert res["ok"] is False
    assert "wallet_id must not be empty" in res["error"]


@patch.object(RustChainOpenAIAgentsTools, "_get_json")
def test_check_balance_success(mock_get, tools):
    mock_get.return_value = {"balance_rtc": 450.85, "miner_id": "RTC_test_wallet"}
    res = tools.check_balance("RTC_test_wallet")
    assert res["ok"] is True
    assert res["wallet_id"] == "RTC_test_wallet"
    assert res["balance"]["balance_rtc"] == 450.85
    mock_get.assert_called_once_with("https://mock.rustchain.org/wallet/balance", {"miner_id": "RTC_test_wallet"})


@patch.object(RustChainOpenAIAgentsTools, "_get_json")
def test_list_bounties_success(mock_get, tools):
    mock_get.return_value = [
        {"number": 2890, "title": "Dual-Layer Trust", "html_url": "https://github.com/...", "updated_at": "2026-04-10"},
        {"number": 13952, "title": "Native Agent Tool", "html_url": "https://github.com/...", "updated_at": "2026-04-10"},
        {"number": 9999, "title": "Ignored PR", "pull_request": {}, "updated_at": "2026-04-10"}
    ]
    res = tools.list_bounties(limit=5)
    assert res["ok"] is True
    assert res["count"] == 2
    assert res["bounties"][0]["number"] == 2890
    assert res["bounties"][1]["number"] == 13952


@patch.object(RustChainOpenAIAgentsTools, "_get_json")
def test_get_node_health_fallback(mock_get, tools):
    def side_effect(url, params=None):
        if "health" in url:
            return {"ok": False, "error": "HTTP 500"}
        return {"miners": 12, "tip_height": 94820}

    mock_get.side_effect = side_effect
    res = tools.get_node_health()
    assert res["ok"] is True
    assert res["source"] == "https://explorer.rustchain.org/api/stats"
    assert res["health"]["miners"] == 12


@patch.object(RustChainOpenAIAgentsTools, "_get_json")
def test_get_current_epoch_success(mock_get, tools):
    mock_get.return_value = {"epoch": 144, "slots_remaining": 32}
    res = tools.get_current_epoch()
    assert res["ok"] is True
    assert res["epoch"] == 144


def test_as_openai_agent_tools_instantiation(tools):
    agent_tools = tools.as_openai_agent_tools()
    assert len(agent_tools) == 4
    tool_names = [fn.__name__ for fn in agent_tools]
    assert "check_balance_tool" in tool_names
    assert "list_bounties_tool" in tool_names
    assert "get_node_health_tool" in tool_names
    assert "get_current_epoch_tool" in tool_names
