"""Focused tests for the RustChain CrewAI tool.

These tests do NOT require crewai to be installed; they exercise the four
public methods (``check_balance``, ``list_bounties``, ``get_node_health``,
``get_current_epoch``) against a stub HTTP layer so they can run in CI
without network access or the crewai package.

Live integration is verified separately by running
``python integrations/rustchain_crewai/rustchain_crewai_tool.py``
which actually hits the RustChain HTTP API.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from unittest import mock

import pytest

from integrations.rustchain_crewai.rustchain_crewai_tool import CREWAI_AVAILABLE, RustChainCrewAITool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, status: int, body: Any):
        self.status_code = status
        self._body = body
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self) -> Any:
        if isinstance(self._body, (dict, list)):
            return self._body
        return json.loads(self._body)


@pytest.fixture
def tool() -> RustChainCrewAITool:
    return RustChainCrewAITool(base_url="https://example.test")


def _ok(balance_rtc: float = 100.0) -> Dict[str, Any]:
    return {
        "amount_i64": int(balance_rtc * 1_000_000),
        "amount_rtc": balance_rtc,
        "miner_id": "jdjioe5-cpu",
    }


# ---------------------------------------------------------------------------
# check_balance
# ---------------------------------------------------------------------------

def test_check_balance_happy_path(tool: RustChainCrewAITool) -> None:
    with mock.patch.object(
        tool, "_get_json", return_value={"ok": True, "status": 200, "data": _ok(42.5)}
    ) as m:
        result = tool.check_balance("jdjioe5-cpu")
    assert result["ok"] is True
    assert result["wallet_id"] == "jdjioe5-cpu"
    assert result["balance_rtc"] == 42.5
    assert m.call_args.args[0] == "/api/wallet/jdjioe5-cpu"


def test_check_balance_strips_whitespace(tool: RustChainCrewAITool) -> None:
    with mock.patch.object(
        tool, "_get_json", return_value={"ok": True, "status": 200, "data": _ok(1.0)}
    ):
        result = tool.check_balance("  jdjioe5-cpu  ")
    assert result["ok"] is True
    assert result["wallet_id"] == "jdjioe5-cpu"


def test_check_balance_rejects_empty(tool: RustChainCrewAITool) -> None:
    result = tool.check_balance("")
    assert result["ok"] is False
    assert "wallet_id is required" in result["error"]


def test_check_balance_handles_http_error(tool: RustChainCrewAITool) -> None:
    with mock.patch.object(
        tool, "_get_json", return_value={"ok": False, "status": 404, "error": "HTTP 404"}
    ):
        result = tool.check_balance("nobody")
    assert result["ok"] is False
    assert result["balance_rtc"] == 0.0
    assert result["status"] == 404


def test_check_balance_handles_network_error(tool: RustChainCrewAITool) -> None:
    with mock.patch.object(
        tool,
        "_get_json",
        return_value={"ok": False, "status": None, "error": "network error: ConnectError: x"},
    ):
        result = tool.check_balance("jdjioe5-cpu")
    assert result["ok"] is False
    assert "network error" in result["error"]


# ---------------------------------------------------------------------------
# get_node_health
# ---------------------------------------------------------------------------

def test_get_node_health_happy_path(tool: RustChainCrewAITool) -> None:
    stats = {
        "chain_id": "rustchain-mainnet-v2",
        "epoch": 191,
        "block_time": 600,
        "features": ["RIP-PoA"],
    }
    with mock.patch.object(
        tool, "_get_json", return_value={"ok": True, "status": 200, "data": stats}
    ):
        result = tool.get_node_health()
    assert result["ok"] is True
    assert result["healthy"] is True
    assert result["chain_id"] == "rustchain-mainnet-v2"
    assert result["epoch"] == 191
    assert result["block_time"] == 600


def test_get_node_health_falls_back_to_health(tool: RustChainCrewAITool) -> None:
    def fake_get(path: str, params: Optional[dict] = None) -> Dict[str, Any]:
        if path == "/api/stats":
            return {"ok": False, "status": 503, "error": "HTTP 503"}
        if path == "/health":
            return {"ok": True, "status": 200, "data": {"ok": True, "tip_age_slots": 0}}
        raise AssertionError(f"unexpected path: {path}")

    with mock.patch.object(tool, "_get_json", side_effect=fake_get):
        result = tool.get_node_health()
    assert result["ok"] is True
    assert result["source"] == "/health"
    assert result["healthy"] is True


# ---------------------------------------------------------------------------
# get_current_epoch
# ---------------------------------------------------------------------------

def test_get_current_epoch_happy_path(tool: RustChainCrewAITool) -> None:
    with mock.patch.object(
        tool,
        "_get_json",
        return_value={
            "ok": True,
            "status": 200,
            "data": {"chain_id": "rustchain-mainnet-v2", "epoch": 191, "block_time": 600},
        },
    ):
        result = tool.get_current_epoch()
    assert result["ok"] is True
    assert result["epoch"] == 191
    assert result["chain_id"] == "rustchain-mainnet-v2"


def test_get_current_epoch_handles_missing(tool: RustChainCrewAITool) -> None:
    with mock.patch.object(
        tool, "_get_json", return_value={"ok": False, "error": "HTTP 500"}
    ):
        result = tool.get_current_epoch()
    assert result["ok"] is False
    assert result["epoch"] is None


# ---------------------------------------------------------------------------
# list_bounties
# ---------------------------------------------------------------------------

def test_list_bounties_clamps_limit(tool: RustChainCrewAITool) -> None:
    captured: Dict[str, Any] = {}

    def fake_get(url: str, params: Optional[dict] = None, **kw: Any) -> _FakeResp:
        captured["url"] = url
        captured["params"] = params
        return _FakeResp(200, [])

    with mock.patch("integrations.rustchain_crewai.rustchain_crewai_tool.requests.get", side_effect=fake_get):
        tool.list_bounties(999)
    # 999 should be clamped to <= 50, so the GitHub per_page param is at most 50.
    assert captured["params"]["per_page"] == 50


def test_list_bounties_returns_normalized_list(tool: RustChainCrewAITool) -> None:
    issues = [
        {
            "number": 1,
            "title": "[BOUNTY: 5 RTC] foo",
            "html_url": "https://github.com/Scottcjn/rustchain-bounties/issues/1",
            "labels": [{"name": "bounty"}, {"name": "good first issue"}],
            "updated_at": "2026-06-12T00:00:00Z",
        },
        {
            "number": 2,
            "title": "[BOUNTY: 10 RTC] bar",
            "html_url": "https://github.com/Scottcjn/rustchain-bounties/issues/2",
            "labels": [{"name": "bounty"}],
            "updated_at": "2026-06-12T00:00:00Z",
        },
    ]

    def fake_get(url: str, params: Optional[dict] = None, **kw: Any) -> _FakeResp:
        return _FakeResp(200, issues)

    with mock.patch("integrations.rustchain_crewai.rustchain_crewai_tool.requests.get", side_effect=fake_get):
        result = tool.list_bounties(5)

    assert result["ok"] is True
    assert result["count"] == 2
    assert result["bounties"][0]["number"] == 1
    assert "bounty" in result["bounties"][0]["labels"]


def test_list_bounties_handles_github_error(tool: RustChainCrewAITool) -> None:
    def fake_get(url: str, params: Optional[dict] = None, **kw: Any) -> _FakeResp:
        return _FakeResp(403, {"message": "rate limit"})

    with mock.patch("integrations.rustchain_crewai.rustchain_crewai_tool.requests.get", side_effect=fake_get):
        result = tool.list_bounties(5)
    assert result["ok"] is False
    assert result["bounties"] == []
    assert "HTTP 403" in result["error"]


def test_list_bounties_handles_network_error(tool: RustChainCrewAITool) -> None:
    import requests

    def fake_get(url: str, params: Optional[dict] = None, **kw: Any) -> None:
        raise requests.ConnectionError("boom")

    with mock.patch("integrations.rustchain_crewai.rustchain_crewai_tool.requests.get", side_effect=fake_get):
        result = tool.list_bounties(5)
    assert result["ok"] is False
    assert "github network error" in result["error"]


# ---------------------------------------------------------------------------
# _run dispatch
# ---------------------------------------------------------------------------

def test_dispatch_unknown_action(tool: RustChainCrewAITool) -> None:
    result = tool._run(action="nope")
    assert result["ok"] is False
    assert "unknown action" in result["error"]


def test_dispatch_routes_to_check_balance(tool: RustChainCrewAITool) -> None:
    with mock.patch.object(
        tool, "_get_json", return_value={"ok": True, "status": 200, "data": _ok(7.0)}
    ):
        result = tool._run(action="check_balance", wallet_id="jdjioe5-cpu")
    assert result["ok"] is True
    assert result["balance_rtc"] == 7.0


def test_dispatch_routes_to_list_bounties(tool: RustChainCrewAITool) -> None:
    def fake_get(url: str, params: Optional[dict] = None, **kw: Any) -> _FakeResp:
        return _FakeResp(200, [])

    with mock.patch("integrations.rustchain_crewai.rustchain_crewai_tool.requests.get", side_effect=fake_get):
        result = tool._run(action="list_bounties", limit=3)
    assert result["ok"] is True


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------

def test_module_exports() -> None:
    from integrations.rustchain_crewai.rustchain_crewai_tool import RustChainCrewAITool as T
    assert hasattr(T, "check_balance")
    assert hasattr(T, "list_bounties")
    assert hasattr(T, "get_node_health")
    assert hasattr(T, "get_current_epoch")


def test_crewai_optional_flag_is_bool() -> None:
    # Either True (crewai installed) or False (graceful stub). Never raise.
    assert isinstance(CREWAI_AVAILABLE, bool)


# ---------------------------------------------------------------------------
# Dispatch shape: README + review-claim coverage
# ---------------------------------------------------------------------------

def test_dispatch_accepts_kwarg_action(tool: RustChainCrewAITool) -> None:
    """``tool.run(action="get_current_epoch")`` must work end-to-end.

    This is the form the README documents and the one the reviewer
    (``justtup`` on PR #7394) recommended. The v0.1.0 PR shipped a
    single-dict form, but ``_run(action: str)`` was the implementation,
    so ``tool.run(action=...)`` should also succeed.
    """
    with mock.patch.object(
        tool,
        "_get_json",
        return_value={
            "ok": True,
            "status": 200,
            "data": {"chain_id": "rustchain-mainnet-v2", "epoch": 191, "block_time": 600},
        },
    ):
        result = tool.run(action="get_current_epoch")
    assert result["ok"] is True
    assert result["epoch"] == 191


def test_dispatch_accepts_dict_payload(tool: RustChainCrewAITool) -> None:
    """The single-dict payload form must also work (back-compat)."""
    with mock.patch.object(
        tool,
        "_get_json",
        return_value={
            "ok": True,
            "status": 200,
            "data": {"chain_id": "rustchain-mainnet-v2", "epoch": 191, "block_time": 600},
        },
    ):
        result = tool.run({"action": "get_current_epoch"})
    assert result["ok"] is True
    assert result["epoch"] == 191


def test_dispatch_dict_payload_with_wallet_id(tool: RustChainCrewAITool) -> None:
    """Dict form must forward ``wallet_id`` to ``check_balance``."""
    with mock.patch.object(
        tool, "_get_json", return_value={"ok": True, "status": 200, "data": _ok(12.5)}
    ):
        result = tool.run({"action": "check_balance", "wallet_id": "jdjioe5-cpu"})
    assert result["ok"] is True
    assert result["wallet_id"] == "jdjioe5-cpu"
    assert result["balance_rtc"] == 12.5


def test_dispatch_dict_payload_with_string_limit(tool: RustChainCrewAITool) -> None:
    """Dict form must coerce a string ``limit`` to int."""
    captured: Dict[str, Any] = {}

    def fake_get(url: str, params: Optional[dict] = None, **kw: Any) -> _FakeResp:
        captured["params"] = params
        return _FakeResp(200, [])

    with mock.patch(
        "integrations.rustchain_crewai.rustchain_crewai_tool.requests.get",
        side_effect=fake_get,
    ):
        result = tool.run({"action": "list_bounties", "limit": "5"})
    assert result["ok"] is True
    assert captured["params"]["per_page"] == 5


def test_dispatch_dict_payload_rejects_bad_limit(tool: RustChainCrewAITool) -> None:
    result = tool._run({"action": "list_bounties", "limit": "not-a-number"})
    assert result["ok"] is False
    assert "limit must be int" in result["error"]


def test_dispatch_rejects_missing_action(tool: RustChainCrewAITool) -> None:
    result = tool.run()
    assert result["ok"] is False
    assert "action is required" in result["error"]


# ---------------------------------------------------------------------------
# Real BaseTool construction (only runs when crewai is installed)
# ---------------------------------------------------------------------------

def test_real_basetool_construction_routes_through_pydantic() -> None:
    """Constructing the tool with real ``crewai.tools.BaseTool`` must work.

    This exercises the pydantic-BaseModel path and was the second
    reviewer concern on PR #7394: the v0.1.0 explicit ``__init__``
    assigned ``self.base_url`` *before* ``super().__init__()``, which
    raises ``AttributeError: ... has no attribute
    '__pydantic_fields_set__'`` on pydantic v2.
    """
    pytest.importorskip("crewai")
    from integrations.rustchain_crewai.rustchain_crewai_tool import (
        RustChainCrewAITool as RealTool,
    )

    tool = RealTool(base_url="https://example.test", timeout=4, bounties_repo="o/r")
    assert tool.base_url == "https://example.test"
    assert tool.timeout == 4.0
    assert tool.bounties_repo == "o/r"


def test_real_basetool_default_construction() -> None:
    """Default construction with real ``BaseTool`` must also work."""
    pytest.importorskip("crewai")
    from integrations.rustchain_crewai.rustchain_crewai_tool import (
        RustChainCrewAITool as RealTool,
    )

    tool = RealTool()
    assert tool.base_url == "https://explorer.rustchain.org"
    assert tool.timeout == 10
    assert tool.bounties_repo == "Scottcjn/rustchain-bounties"
