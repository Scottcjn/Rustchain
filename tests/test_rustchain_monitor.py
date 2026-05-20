# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture()
def rustchain_monitor_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "rustchain-monitor"
        / "rustchain_monitor.py"
    )
    spec = importlib.util.spec_from_file_location("rustchain_monitor", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


def test_request_helpers_call_expected_endpoints(rustchain_monitor_module, monkeypatch):
    calls = []
    responses = {
        "https://node.example/health": {"ok": True},
        "https://node.example/api/miners": {
            "items": [{"miner": "alice"}],
            "pagination": {"total": 1},
        },
        "https://node.example/epoch": {"epoch": 7},
    }

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return FakeResponse(responses[url])

    monkeypatch.setattr(rustchain_monitor_module, "NODE_URL", "https://node.example")
    monkeypatch.setattr(rustchain_monitor_module.requests, "get", fake_get)

    assert rustchain_monitor_module.check_health() == {"ok": True}
    assert rustchain_monitor_module.get_miners() == [{"miner": "alice"}]
    assert rustchain_monitor_module.get_epoch() == {"epoch": 7}
    assert calls == [
        ("https://node.example/health", 10),
        ("https://node.example/api/miners", 10),
        ("https://node.example/epoch", 10),
    ]


def test_normalize_miners_payload_preserves_unexpected_shapes(rustchain_monitor_module):
    assert rustchain_monitor_module.normalize_miners_payload([{"miner": "alice"}]) == [
        {"miner": "alice"}
    ]
    assert rustchain_monitor_module.normalize_miners_payload(
        [{"miner": "alice"}, None, "bad"]
    ) == [{"miner": "alice"}]
    assert rustchain_monitor_module.normalize_miners_payload(
        {"miners": [{"miner": "bob"}, None]}
    ) == [{"miner": "bob"}]
    assert rustchain_monitor_module.normalize_miners_payload(
        {"pagination": {"total": 0}}
    ) == {"pagination": {"total": 0}}


def test_object_payload_helpers_reject_non_object_health_and_epoch(
    rustchain_monitor_module,
    monkeypatch,
):
    monkeypatch.setattr(
        rustchain_monitor_module.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse(["not", "object"]),
    )

    assert rustchain_monitor_module.check_health() == {
        "error": "unexpected health response shape"
    }
    assert rustchain_monitor_module.get_epoch() == {
        "error": "unexpected epoch response shape"
    }


def test_request_helpers_return_error_dict_on_failure(rustchain_monitor_module, monkeypatch):
    def fake_get(_url, timeout):
        assert timeout == 10
        return FakeResponse({}, error=RuntimeError("node offline"))

    monkeypatch.setattr(rustchain_monitor_module.requests, "get", fake_get)

    assert rustchain_monitor_module.check_health() == {"error": "node offline"}
    assert rustchain_monitor_module.get_miners() == {"error": "node offline"}
    assert rustchain_monitor_module.get_epoch() == {"error": "node offline"}


def test_print_health_formats_success_and_error(rustchain_monitor_module, capsys):
    rustchain_monitor_module.print_health(
        {
            "version": "2.2.1",
            "uptime_s": 7200,
            "backup_age_hours": 1.25,
            "db_rw": True,
        }
    )
    rustchain_monitor_module.print_health({"error": "offline"})
    rustchain_monitor_module.print_health(["not", "object"])

    output = capsys.readouterr().out
    assert "Node is healthy" in output
    assert "Version: 2.2.1" in output
    assert "Uptime: 7200s (2.0 hours)" in output
    assert "Backup age: 1.25 hours" in output
    assert "DB RW: True" in output
    assert "Health check failed: offline" in output
    assert "Health check failed: unexpected response" in output


def test_print_miners_limits_rows_and_formats_last_attest(
    rustchain_monitor_module, monkeypatch, capsys
):
    class FixedDatetime(datetime):
        @classmethod
        def fromtimestamp(cls, timestamp):
            assert timestamp == 1_700_000_000
            return datetime(2026, 5, 13, 6, 30)

    miners = [
        {
            "miner": "miner-0",
            "hardware_type": "PowerPC",
            "antiquity_multiplier": 2.5,
            "last_attest": 1_700_000_000,
        }
    ] + [{"miner": f"miner-{i}"} for i in range(1, 12)]
    monkeypatch.setattr(rustchain_monitor_module, "datetime", FixedDatetime)

    rustchain_monitor_module.print_miners(miners)
    rustchain_monitor_module.print_miners([{"miner": "valid"}, None])
    rustchain_monitor_module.print_miners({"unexpected": True})
    rustchain_monitor_module.print_miners({"error": "bad gateway"})

    output = capsys.readouterr().out
    assert "Active miners: 12" in output
    assert "miner-0" in output
    assert "HW: PowerPC" in output
    assert "Multiplier: 2.5" in output
    assert "Last: 06:30" in output
    assert "... and 2 more" in output
    assert "valid" in output
    assert "Unexpected response" in output
    assert "Failed to fetch miners: bad gateway" in output


def test_print_epoch_formats_success_and_error(rustchain_monitor_module, capsys):
    rustchain_monitor_module.print_epoch(
        {
            "epoch": 12,
            "slot": 34,
            "height": 56,
            "blocks_per_epoch": 100,
            "epoch_pot": 7.5,
            "enrolled_miners": 9,
        }
    )
    rustchain_monitor_module.print_epoch({"error": "timeout"})
    rustchain_monitor_module.print_epoch(["not", "object"])

    output = capsys.readouterr().out
    assert "Epoch: 12" in output
    assert "Slot: 34" in output
    assert "Height: 56" in output
    assert "Blocks per epoch: 100" in output
    assert "Epoch pot: 7.5 RTC" in output
    assert "Enrolled miners: 9" in output
    assert "Failed to fetch epoch: timeout" in output
    assert "Failed to fetch epoch: unexpected response" in output
