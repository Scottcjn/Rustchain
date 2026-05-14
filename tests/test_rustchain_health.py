# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from urllib.error import URLError

import pytest


@pytest.fixture()
def rustchain_health_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "rustchain-health.py"
    spec = importlib.util.spec_from_file_location("rustchain_health", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module._COLOR = False
    return module


class FakeHTTPResponse:
    def __init__(self, body: bytes):
        self.body = body
        self.read_size = None

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def read(self, size=-1):
        self.read_size = size
        return self.body


def test_format_helpers_handle_boundaries(rustchain_health_module):
    assert rustchain_health_module._fmt_uptime(None) == "n/a"
    assert rustchain_health_module._fmt_uptime(0) == "0m"
    assert rustchain_health_module._fmt_uptime(59) == "0m"
    assert rustchain_health_module._fmt_uptime(90061) == "1d 1h 1m"

    assert rustchain_health_module._trunc_hash(None) == "n/a"
    assert rustchain_health_module._trunc_hash("") == "n/a"
    assert rustchain_health_module._trunc_hash("abc", 16) == "abc"
    assert (
        rustchain_health_module._trunc_hash("0123456789abcdefXYZ", 16)
        == "0123456789abcdef..."
    )
    assert rustchain_health_module.status_dot(True) == "\u25cf"
    assert rustchain_health_module.status_dot(False) == "\u25cf"


def test_fetch_parses_json_and_sets_headers(rustchain_health_module, monkeypatch):
    calls = []
    ssl_context = object()
    response = FakeHTTPResponse(b'{"ok": true, "version": "2.2.1"}')
    times = iter([10.0, 10.125])

    def fake_urlopen(request, timeout, context):
        calls.append((request, timeout, context))
        return response

    monkeypatch.setattr(rustchain_health_module, "_ssl_ctx", lambda: ssl_context)
    monkeypatch.setattr(rustchain_health_module, "urlopen", fake_urlopen)
    monkeypatch.setattr(rustchain_health_module.time, "time", lambda: next(times))

    ok, data, latency = rustchain_health_module.fetch(
        "https://node.example/health",
        timeout=3,
    )

    assert ok is True
    assert data == {"ok": True, "version": "2.2.1"}
    assert latency == pytest.approx(125.0)
    assert response.read_size == 2 * 1024 * 1024
    request, timeout, context = calls[0]
    assert request.full_url == "https://node.example/health"
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["accept"] == "application/json"
    assert headers["user-agent"] == "rustchain-health-cli/1.0"
    assert timeout == 3
    assert context is ssl_context


def test_fetch_returns_text_and_error_payloads(rustchain_health_module, monkeypatch):
    times = iter([20.0, 20.05, 30.0, 30.075])

    def fake_text_urlopen(_request, timeout, context):
        assert timeout == 8
        assert context == "ssl-context"
        return FakeHTTPResponse(b" node online \n")

    monkeypatch.setattr(rustchain_health_module, "_ssl_ctx", lambda: "ssl-context")
    monkeypatch.setattr(rustchain_health_module, "urlopen", fake_text_urlopen)
    monkeypatch.setattr(rustchain_health_module.time, "time", lambda: next(times))

    ok, data, latency = rustchain_health_module.fetch("https://node.example/plain")

    assert ok is True
    assert data == "node online"
    assert latency == pytest.approx(50.0)

    def fake_error_urlopen(_request, timeout, context):
        raise URLError("node offline")

    monkeypatch.setattr(rustchain_health_module, "urlopen", fake_error_urlopen)

    ok, data, latency = rustchain_health_module.fetch("https://node.example/down")

    assert ok is False
    assert "node offline" in data
    assert latency == pytest.approx(75.0)


def test_check_helpers_shape_endpoint_responses(rustchain_health_module, monkeypatch):
    miner_rows = [{"miner_id": f"miner-{idx}"} for idx in range(12)]
    responses = {
        "https://node.example/health": (
            True,
            {
                "ok": True,
                "version": "2.2.1",
                "uptime_s": 7200,
                "db_rw": True,
                "tip_age_slots": 2,
            },
            12.34,
        ),
        "https://node.example/epoch": (
            True,
            {
                "epoch": 7,
                "slot": 99,
                "epoch_pot": 1.5,
                "enrolled_miners": 4,
                "blocks_per_epoch": 100,
                "total_supply_rtc": 8300000,
            },
            22.22,
        ),
        "https://node.example/api/miners": (True, miner_rows, 33.33),
        "https://node.example/headers/tip": (
            True,
            {
                "block_height": 123,
                "block_hash": "0123456789abcdefXYZ",
                "timestamp": "2026-05-13T00:00:00Z",
            },
            44.44,
        ),
    }
    calls = []

    def fake_fetch(url, timeout):
        calls.append((url, timeout))
        return responses[url]

    monkeypatch.setattr(rustchain_health_module, "fetch", fake_fetch)

    assert rustchain_health_module.check_health("https://node.example", 5) == {
        "reachable": True,
        "latency_ms": 12.3,
        "ok": True,
        "version": "2.2.1",
        "uptime_s": 7200,
        "db_rw": True,
        "tip_age_slots": 2,
    }
    assert rustchain_health_module.check_epoch("https://node.example", 5) == {
        "reachable": True,
        "latency_ms": 22.2,
        "epoch": 7,
        "slot": 99,
        "epoch_pot": 1.5,
        "enrolled_miners": 4,
        "blocks_per_epoch": 100,
        "total_supply_rtc": 8300000,
    }
    miners = rustchain_health_module.check_miners("https://node.example", 5)
    assert miners["miner_count"] == 12
    assert miners["miners"] == miner_rows[:10]
    assert rustchain_health_module.check_tip("https://node.example", 5) == {
        "reachable": True,
        "latency_ms": 44.4,
        "height": 123,
        "hash": "0123456789abcdefXYZ",
        "timestamp": "2026-05-13T00:00:00Z",
    }
    assert calls == [
        ("https://node.example/health", 5),
        ("https://node.example/epoch", 5),
        ("https://node.example/api/miners", 5),
        ("https://node.example/headers/tip", 5),
    ]


def test_check_helpers_handle_raw_dict_and_error_edges(
    rustchain_health_module,
    monkeypatch,
):
    responses = {
        "https://node.example/health": (True, "plain health", 10.0),
        "https://node.example/epoch": (True, "plain epoch", 20.0),
        "https://node.example/api/miners": (
            True,
            {"miners": [{"id": "alice"}, {"id": "bob"}]},
            30.0,
        ),
        "https://node.example/headers/tip": (False, "tip timeout", 40.0),
    }

    def fake_fetch(url, _timeout):
        return responses[url]

    monkeypatch.setattr(rustchain_health_module, "fetch", fake_fetch)

    assert rustchain_health_module.check_health("https://node.example", 5) == {
        "reachable": True,
        "latency_ms": 10.0,
        "ok": True,
        "raw": "plain health",
    }
    assert rustchain_health_module.check_epoch("https://node.example", 5) == {
        "reachable": True,
        "latency_ms": 20.0,
        "raw": "plain epoch",
    }
    assert rustchain_health_module.check_miners("https://node.example", 5) == {
        "reachable": True,
        "latency_ms": 30.0,
        "miner_count": 2,
        "miners": [{"id": "alice"}, {"id": "bob"}],
    }
    assert rustchain_health_module.check_tip("https://node.example", 5) == {
        "reachable": False,
        "latency_ms": 40.0,
        "error": "tip timeout",
    }


def test_collect_strips_base_url_and_uses_checks(rustchain_health_module, monkeypatch):
    calls = []

    def fake_check(name):
        def _check(base, timeout):
            calls.append((name, base, timeout))
            return {"name": name}

        return _check

    monkeypatch.setattr(rustchain_health_module, "check_health", fake_check("health"))
    monkeypatch.setattr(rustchain_health_module, "check_epoch", fake_check("epoch"))
    monkeypatch.setattr(rustchain_health_module, "check_miners", fake_check("miners"))
    monkeypatch.setattr(rustchain_health_module, "check_tip", fake_check("tip"))
    monkeypatch.setattr(rustchain_health_module.time, "gmtime", lambda: "gmtime")
    monkeypatch.setattr(
        rustchain_health_module.time,
        "strftime",
        lambda fmt, value: "2026-05-13T00:00:00Z",
    )

    snapshot = rustchain_health_module.collect("https://node.example/", timeout=6)

    assert snapshot == {
        "node": "https://node.example",
        "checked_at": "2026-05-13T00:00:00Z",
        "health": {"name": "health"},
        "epoch": {"name": "epoch"},
        "miners": {"name": "miners"},
        "tip": {"name": "tip"},
    }
    assert calls == [
        ("health", "https://node.example", 6),
        ("epoch", "https://node.example", 6),
        ("miners", "https://node.example", 6),
        ("tip", "https://node.example", 6),
    ]


def test_render_reports_healthy_and_unhealthy_snapshots(rustchain_health_module):
    snapshot = {
        "node": "https://node.example",
        "checked_at": "2026-05-13T00:00:00Z",
        "health": {
            "reachable": True,
            "latency_ms": 12.2,
            "ok": True,
            "version": "2.2.1",
            "uptime_s": 90061,
            "db_rw": True,
        },
        "epoch": {
            "reachable": True,
            "latency_ms": 23.4,
            "epoch": 7,
            "slot": 42,
            "epoch_pot": 1.5,
            "enrolled_miners": 4,
            "total_supply_rtc": 8300000,
        },
        "tip": {
            "reachable": True,
            "latency_ms": 34.5,
            "height": 123,
            "hash": "0123456789abcdefXYZ",
            "timestamp": "2026-05-13T00:00:00Z",
        },
        "miners": {
            "reachable": True,
            "latency_ms": 45.6,
            "miner_count": 6,
            "miners": [
                {"miner_id": "miner-a"},
                {"id": "miner-b"},
                "miner-c",
                {"miner_id": "miner-d"},
                {"miner_id": "miner-e"},
                {"miner_id": "miner-f"},
            ],
        },
    }

    output = rustchain_health_module.render(snapshot)

    assert "RustChain Node Health Monitor" in output
    assert "STATUS: ALL SYSTEMS OPERATIONAL" in output
    assert "Uptime         : 1d 1h 1m" in output
    assert "Hash           : 0123456789abcdef..." in output
    assert "- miner-a" in output
    assert "- miner-b" in output
    assert "- miner-c" in output
    assert "... and 1 more" in output

    unhealthy = copy.deepcopy(snapshot)
    unhealthy["health"]["ok"] = False
    unhealthy["health"]["error"] = "node offline"

    output = rustchain_health_module.render(unhealthy)

    assert "UNHEALTHY" in output
    assert "Error: node offline" in output
    assert "STATUS: ISSUES DETECTED" in output
