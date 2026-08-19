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

    reachable, parsed, data, latency = rustchain_health_module.fetch(
        "https://node.example/health",
        timeout=3,
    )

    assert reachable is True
    assert parsed is True
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

    reachable, parsed, data, latency = rustchain_health_module.fetch(
        "https://node.example/plain")

    # A 200 carrying non-JSON is reachable but NOT parsed. It used to come back
    # as ok=True, which is the whole bug.
    assert reachable is True
    assert parsed is False
    assert "not JSON" in data
    assert latency == pytest.approx(50.0)

    def fake_error_urlopen(_request, timeout, context):
        raise URLError("node offline")

    monkeypatch.setattr(rustchain_health_module, "urlopen", fake_error_urlopen)

    reachable, parsed, data, latency = rustchain_health_module.fetch(
        "https://node.example/down")

    assert reachable is False
    assert parsed is False
    assert "node offline" in data
    assert latency == pytest.approx(75.0)


def test_spa_answering_200_on_every_path_is_not_healthy(
    rustchain_health_module,
    monkeypatch,
):
    """Regression: the CognetCloud / Node-4 failure mode.

    After that node was taken down the host began serving an unrelated
    single-page app that answers 200 on every unknown path. /health and /epoch
    both returned 200 with HTML. The old CLI reported four green dots,
    "ALL SYSTEMS OPERATIONAL", and exit 0 — indefinitely.
    """
    spa_body = b"<!doctype html><title>New API</title><div id=app></div>"

    monkeypatch.setattr(rustchain_health_module, "_ssl_ctx", lambda: "ssl-context")
    monkeypatch.setattr(
        rustchain_health_module,
        "urlopen",
        lambda _request, timeout, context: FakeHTTPResponse(spa_body),
    )

    snapshot = rustchain_health_module.collect("https://spa.example", timeout=5)

    for name in ("health", "epoch", "miners", "tip"):
        assert snapshot[name]["reachable"] is True, name
        assert snapshot[name]["parsed"] is False, name
        assert snapshot[name]["ok"] is False, name

    assert snapshot["overall_ok"] is False
    assert rustchain_health_module.overall_ok(snapshot) is False

    rendered = rustchain_health_module.render(snapshot)
    assert "STATUS: ISSUES DETECTED" in rendered
    assert "ALL SYSTEMS OPERATIONAL" not in rendered
    assert "Answered 200 but not with JSON" in rendered


def test_health_endpoint_reporting_ok_false_is_not_healthy(
    rustchain_health_module,
    monkeypatch,
):
    """A node that answers JSON saying ok=false is unhealthy, not merely reachable."""
    monkeypatch.setattr(
        rustchain_health_module,
        "fetch",
        lambda _url, _timeout: (True, True, {"ok": False, "version": "2.2.1"}, 5.0),
    )

    result = rustchain_health_module.check_health("https://node.example", 5)

    assert result["reachable"] is True
    assert result["parsed"] is True
    assert result["ok"] is False
    assert "did not report ok=true" in result["error"]


def test_check_helpers_shape_endpoint_responses(rustchain_health_module, monkeypatch):
    miner_rows = [{"miner_id": f"miner-{idx}"} for idx in range(12)]
    responses = {
        "https://node.example/health": (
            True,
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
        "https://node.example/api/miners": (True, True, miner_rows, 33.33),
        "https://node.example/headers/tip": (
            True,
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
        "parsed": True,
        "latency_ms": 12.3,
        "ok": True,
        "version": "2.2.1",
        "uptime_s": 7200,
        "db_rw": True,
        "tip_age_slots": 2,
    }
    assert rustchain_health_module.check_epoch("https://node.example", 5) == {
        "reachable": True,
        "parsed": True,
        "latency_ms": 22.2,
        "epoch": 7,
        "slot": 99,
        "epoch_pot": 1.5,
        "enrolled_miners": 4,
        "blocks_per_epoch": 100,
        "total_supply_rtc": 8300000,
        "ok": True,
    }
    miners = rustchain_health_module.check_miners("https://node.example", 5)
    assert miners["miner_count"] == 12
    assert miners["miners"] == miner_rows[:10]
    assert miners["ok"] is True
    assert rustchain_health_module.check_tip("https://node.example", 5) == {
        "reachable": True,
        "parsed": True,
        "latency_ms": 44.4,
        "height": 123,
        "hash": "0123456789abcdefXYZ",
        "timestamp": "2026-05-13T00:00:00Z",
        "ok": True,
    }
    assert calls == [
        ("https://node.example/health", 5),
        ("https://node.example/epoch", 5),
        ("https://node.example/api/miners", 5),
        ("https://node.example/headers/tip", 5),
    ]


def test_check_miners_accepts_items_envelope(rustchain_health_module, monkeypatch):
    miner_rows = [{"miner_id": "alice"}, {"miner_id": "bob"}]

    monkeypatch.setattr(
        rustchain_health_module,
        "fetch",
        lambda _url, _timeout: (True, True, {"items": miner_rows}, 7.0),
    )

    result = rustchain_health_module.check_miners("https://node.example", 5)

    assert result["reachable"] is True
    assert result["parsed"] is True
    assert result["ok"] is True
    assert result["latency_ms"] == 7.0
    assert result["miner_count"] == 2
    assert result["miners"] == miner_rows


def test_check_helpers_handle_raw_dict_and_error_edges(
    rustchain_health_module,
    monkeypatch,
):
    # /health and /epoch answer 200 with a non-JSON body: reachable, unparsed,
    # and therefore NOT ok. /headers/tip is outright unreachable.
    responses = {
        "https://node.example/health": (True, False, "200 response was not JSON", 10.0),
        "https://node.example/epoch": (True, False, "200 response was not JSON", 20.0),
        "https://node.example/api/miners": (
            True,
            True,
            {"miners": [{"id": "alice"}, {"id": "bob"}]},
            30.0,
        ),
        "https://node.example/headers/tip": (False, False, "tip timeout", 40.0),
    }

    def fake_fetch(url, _timeout):
        return responses[url]

    monkeypatch.setattr(rustchain_health_module, "fetch", fake_fetch)

    assert rustchain_health_module.check_health("https://node.example", 5) == {
        "reachable": True,
        "parsed": False,
        "latency_ms": 10.0,
        "ok": False,
        "error": "200 response was not JSON",
    }
    assert rustchain_health_module.check_epoch("https://node.example", 5) == {
        "reachable": True,
        "parsed": False,
        "latency_ms": 20.0,
        "ok": False,
        "error": "200 response was not JSON",
    }
    assert rustchain_health_module.check_miners("https://node.example", 5) == {
        "reachable": True,
        "parsed": True,
        "latency_ms": 30.0,
        "miner_count": 2,
        "miners": [{"id": "alice"}, {"id": "bob"}],
        "ok": True,
    }
    assert rustchain_health_module.check_tip("https://node.example", 5) == {
        "reachable": False,
        "parsed": False,
        "latency_ms": 40.0,
        "ok": False,
        "error": "tip timeout",
    }


def test_collect_strips_base_url_and_uses_checks(rustchain_health_module, monkeypatch):
    calls = []

    def fake_check(name):
        def _check(base, timeout):
            calls.append((name, base, timeout))
            return {"name": name, "ok": True}

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
        "health": {"name": "health", "ok": True},
        "epoch": {"name": "epoch", "ok": True},
        "miners": {"name": "miners", "ok": True},
        "tip": {"name": "tip", "ok": True},
        "overall_ok": True,
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
            "parsed": True,
            "latency_ms": 12.2,
            "ok": True,
            "version": "2.2.1",
            "uptime_s": 90061,
            "db_rw": True,
        },
        "epoch": {
            "reachable": True,
            "parsed": True,
            "ok": True,
            "latency_ms": 23.4,
            "epoch": 7,
            "slot": 42,
            "epoch_pot": 1.5,
            "enrolled_miners": 4,
            "total_supply_rtc": 8300000,
        },
        "tip": {
            "reachable": True,
            "parsed": True,
            "ok": True,
            "latency_ms": 34.5,
            "height": 123,
            "hash": "0123456789abcdefXYZ",
            "timestamp": "2026-05-13T00:00:00Z",
        },
        "miners": {
            "reachable": True,
            "parsed": True,
            "ok": True,
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
