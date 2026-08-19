# SPDX-License-Identifier: MIT
"""Unit tests for the standalone RustChain health CLI."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "rustchain-health.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rustchain_health_cli", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module._COLOR = False
    return module


def test_format_helpers_handle_empty_and_long_values():
    module = load_module()

    assert module._fmt_uptime(None) == "n/a"
    assert module._fmt_uptime(59) == "0m"
    assert module._fmt_uptime(90061) == "1d 1h 1m"
    assert module._trunc_hash(None) == "n/a"
    assert module._trunc_hash("abcdef", n=8) == "abcdef"
    assert module._trunc_hash("a" * 20, n=8) == "aaaaaaaa..."


def test_check_helpers_normalize_successful_payloads():
    module = load_module()

    with patch.object(module, "fetch", side_effect=[
        (True, True, {"ok": True, "version": "1.2", "uptime_s": 61, "db_rw": True}, 12.34),
        (True, True, {"epoch": 7, "slot": 99, "epoch_pot": 1.5, "enrolled_miners": 3}, 2.0),
        (True, True, [{"miner_id": "m1"}, {"miner": "m2"}], 3.0),
        (True, True, {"block_height": 55, "block_hash": "abc", "timestamp": "now"}, 4.0),
    ]):
        assert module.check_health("https://node", 5) == {
            "reachable": True,
            "parsed": True,
            "latency_ms": 12.3,
            "ok": True,
            "version": "1.2",
            "uptime_s": 61,
            "db_rw": True,
            "tip_age_slots": None,
        }
        assert module.check_epoch("https://node", 5)["epoch"] == 7
        assert module.check_miners("https://node", 5)["miner_count"] == 2
        assert module.check_tip("https://node", 5)["height"] == 55


def test_check_helpers_handle_errors_and_non_dict_payloads():
    module = load_module()

    # Second and fourth responses are 200s carrying non-JSON. They are
    # reachable but unparsed, and must come back ok=False — never as a healthy
    # endpoint with a "raw" field.
    with patch.object(module, "fetch", side_effect=[
        (False, False, "offline", 1.0),
        (True, False, "200 response was not JSON: ok text", 2.0),
        (False, False, "miners down", 3.0),
        (True, False, "200 response was not JSON: tip text", 4.0),
    ]):
        health = module.check_health("https://node", 5)
        epoch = module.check_epoch("https://node", 5)
        miners = module.check_miners("https://node", 5)
        tip = module.check_tip("https://node", 5)

    assert health == {
        "reachable": False, "parsed": False, "latency_ms": 1.0,
        "ok": False, "error": "offline",
    }
    assert epoch["ok"] is False
    assert epoch["reachable"] is True
    assert "not JSON" in epoch["error"]
    assert miners["miner_count"] == 0
    assert miners["ok"] is False
    assert miners["error"] == "miners down"
    assert tip["ok"] is False
    assert tip["reachable"] is True
    assert "not JSON" in tip["error"]


def test_collect_strips_trailing_slash_and_calls_all_checks():
    module = load_module()

    with (
        patch.object(module.time, "strftime", return_value="2026-05-14T04:59:00Z"),
        patch.object(module, "check_health", return_value={"reachable": True, "ok": True}) as health,
        patch.object(module, "check_epoch", return_value={"reachable": True, "ok": True}) as epoch,
        patch.object(module, "check_miners", return_value={"reachable": True, "ok": True}) as miners,
        patch.object(module, "check_tip", return_value={"reachable": True, "ok": True}) as tip,
    ):
        snapshot = module.collect("https://node/", timeout=4)

    assert snapshot["node"] == "https://node"
    assert snapshot["checked_at"] == "2026-05-14T04:59:00Z"
    health.assert_called_once_with("https://node", 4)
    epoch.assert_called_once_with("https://node", 4)
    miners.assert_called_once_with("https://node", 4)
    tip.assert_called_once_with("https://node", 4)


def test_render_reports_operational_and_issue_states():
    module = load_module()
    snapshot = {
        "node": "https://node",
        "checked_at": "2026-05-14T04:59:00Z",
        "health": {"reachable": True, "parsed": True, "ok": True, "latency_ms": 1.2, "version": "1.0", "uptime_s": 3661},
        "epoch": {"reachable": True, "parsed": True, "ok": True, "latency_ms": 2.0, "epoch": 3, "slot": 9},
        "miners": {"reachable": True, "parsed": True, "ok": True, "latency_ms": 3.0, "miner_count": 1, "miners": [{"miner_id": "m1"}]},
        "tip": {"reachable": True, "parsed": True, "ok": True, "latency_ms": 4.0, "height": 10, "hash": "a" * 20},
    }

    rendered = module.render(snapshot)
    assert "RustChain Node Health Monitor" in rendered
    assert "STATUS: ALL SYSTEMS OPERATIONAL" in rendered
    assert "Hash           : aaaaaaaaaaaaaaaa..." in rendered
    assert "- m1" in rendered

    snapshot["health"] = {"reachable": False, "parsed": False, "ok": False,
                          "latency_ms": 1.0, "error": "offline"}
    assert "STATUS: ISSUES DETECTED" in module.render(snapshot)
