# SPDX-License-Identifier: MIT
"""Unit tests for the RustChain network monitor CLI helper."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "rustchain-monitor" / "rustchain_monitor.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rustchain_monitor_cli", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def response(payload):
    resp = Mock()
    resp.json.return_value = payload
    return resp


def test_api_helpers_fetch_expected_endpoints_and_return_json():
    module = load_module()

    with patch.object(module.requests, "get", side_effect=[
        response({"ok": True}),
        response([{"miner": "m1"}]),
        response({"epoch": 3}),
    ]) as get:
        assert module.check_health() == {"ok": True}
        assert module.get_miners() == [{"miner": "m1"}]
        assert module.get_epoch() == {"epoch": 3}

    assert [call.args[0] for call in get.call_args_list] == [
        f"{module.NODE_URL}/health",
        f"{module.NODE_URL}/api/miners",
        f"{module.NODE_URL}/epoch",
    ]
    assert all(call.kwargs["timeout"] == 10 for call in get.call_args_list)


def test_api_helpers_return_error_dict_on_request_failure():
    module = load_module()

    with patch.object(module.requests, "get", side_effect=RuntimeError("offline")):
        assert module.check_health() == {"error": "offline"}
        assert module.get_miners() == {"error": "offline"}
        assert module.get_epoch() == {"error": "offline"}


def test_api_helpers_return_error_dict_on_http_error():
    module = load_module()
    failed = response({"error": "server exploded"})
    failed.raise_for_status.side_effect = module.requests.HTTPError("500 Server Error")

    with patch.object(module.requests, "get", return_value=failed):
        assert module.check_health() == {"error": "500 Server Error"}
        assert module.get_miners() == {"error": "500 Server Error"}
        assert module.get_epoch() == {"error": "500 Server Error"}


def test_print_health_renders_success_and_error(capsys):
    module = load_module()

    module.print_health({
        "version": "1.2",
        "uptime_s": 7200,
        "backup_age_hours": 1.25,
        "db_rw": True,
    })
    module.print_health({"error": "offline"})

    output = capsys.readouterr().out
    assert "Node is healthy" in output
    assert "Version: 1.2" in output
    assert "Uptime: 7200s (2.0 hours)" in output
    assert "Backup age: 1.25 hours" in output
    assert "Health check failed: offline" in output


def test_print_miners_renders_lists_unexpected_and_errors(capsys):
    module = load_module()

    module.print_miners([
        {"miner": "alice", "hardware_type": "PowerPC", "antiquity_multiplier": 1.5, "last_attest": 0},
        {"miner": "bob", "hardware_type": "x86", "antiquity_multiplier": 1.0, "last_attest": 60},
    ])
    module.print_miners({"unexpected": True})
    module.print_miners({"error": "down"})

    output = capsys.readouterr().out
    assert "Active miners: 2" in output
    assert "alice" in output
    assert "never" in output
    assert "Unexpected response" in output
    assert "Failed to fetch miners: down" in output


def test_print_epoch_renders_success_and_error(capsys):
    module = load_module()

    module.print_epoch({
        "epoch": 9,
        "slot": 12,
        "height": 100,
        "blocks_per_epoch": 144,
        "epoch_pot": 1.5,
        "enrolled_miners": 7,
    })
    module.print_epoch({"error": "unavailable"})

    output = capsys.readouterr().out
    assert "Epoch: 9" in output
    assert "Slot: 12" in output
    assert "Epoch pot: 1.5 RTC" in output
    assert "Failed to fetch epoch: unavailable" in output
