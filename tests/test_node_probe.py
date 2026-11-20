#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recorded-fixture tests for the shared node probe (issue #17180).

A 200 on /health is not evidence of a RustChain node — the BODY decides. The
fixtures here are the exact shapes seen in production and in the bounty text:
a genuine /health body, an HTML SPA answering 200, JSON without node keys,
ok:false, a 500, and a timeout. The HTML-200 case must come out "impostor",
never "up".
"""

import importlib.util
import json
import socket
import sys
import urllib.error
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(
        name, str(REPO_ROOT / rel_path)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


probe = _load("node_probe", "monitoring/node_probe.py")

# ── Recorded fixtures ─────────────────────────────────────────────────────────
# Genuine /health body as a real attestation node answers it.
REAL_HEALTH_BODY = {
    "ok": True,
    "version": "2.2.1",
    "uptime_s": 86400,
    "db_rw": True,
    "backup_age_hours": 1.5,
    "tip_age_slots": 3,
    "active_miners": 21,
    "epoch": 174,
}

# What the repurposed attestation-node IP actually served: an SPA shell that
# answers 200 on EVERY path.
SPA_HTML_BODY = (
    '<!doctype html><html lang="en"><head><title>New API</title></head>'
    '<body><div id="root"></div><script src="/static/js/main.js"></script>'
    "</body></html>"
)

# Some other service speaking JSON on the node's address — valid JSON, none of
# the ok/version/uptime_s identity keys.
JSON_MISSING_KEYS_BODY = {"app": "some-dashboard", "status": "ready", "user": "guest"}


class _FakeUrlResp:
    """Stand-in for the urlopen context manager."""

    def __init__(self, body: bytes, content_type: str = "application/json", status: int = 200):
        self._body = body
        self.headers = {"Content-Type": content_type}
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n: int = -1) -> bytes:
        return self._body if n is None or n < 0 else self._body[:n]


# ── classify_response: body decides, never the status code alone ─────────────

def test_genuine_health_body_is_up():
    res = probe.classify_response(200, "application/json", body=json.dumps(REAL_HEALTH_BODY))
    assert res.state == "up"
    assert res.is_node and res.error is None


def test_html_200_is_impostor_never_up():
    res = probe.classify_response(200, "text/html; charset=utf-8", body=SPA_HTML_BODY)
    assert res.state == "impostor"
    assert not res.is_node


def test_html_body_claiming_json_content_type_is_still_impostor():
    """Content-type is a hint, not proof: parse failure demotes the 200 too."""
    res = probe.classify_response(200, "application/json", body=SPA_HTML_BODY)
    assert res.state == "impostor"


def test_xhtml_content_type_is_impostor():
    res = probe.classify_response(200, "application/xhtml+xml", body=SPA_HTML_BODY)
    assert res.state == "impostor"


def test_json_without_identity_keys_is_impostor():
    res = probe.classify_response(200, "application/json", body=json.dumps(JSON_MISSING_KEYS_BODY))
    assert res.state == "impostor"
    assert "ok, version, uptime_s" in (res.error or "")


def test_json_array_body_is_impostor():
    res = probe.classify_response(200, "application/json", body="[1, 2, 3]")
    assert res.state == "impostor"


def test_empty_body_is_impostor():
    res = probe.classify_response(200, "application/json", body="")
    assert res.state == "impostor"


def test_ok_false_is_degraded():
    body = dict(REAL_HEALTH_BODY, ok=False)
    res = probe.classify_response(200, "application/json", body=json.dumps(body))
    assert res.state == "degraded"


def test_db_rw_false_is_degraded():
    body = dict(REAL_HEALTH_BODY, db_rw=False)
    res = probe.classify_response(200, "application/json", body=json.dumps(body))
    assert res.state == "degraded"


def test_stale_tip_age_slots_is_degraded_but_fresh_is_up():
    stale = dict(REAL_HEALTH_BODY, tip_age_slots=probe.TIP_AGE_SLOTS_THRESHOLD + 1)
    fresh = dict(REAL_HEALTH_BODY, tip_age_slots=probe.TIP_AGE_SLOTS_THRESHOLD)
    assert probe.classify_response(200, "application/json", body=json.dumps(stale)).state == "degraded"
    assert probe.classify_response(200, "application/json", body=json.dumps(fresh)).state == "up"


def test_http_500_is_down():
    res = probe.classify_response(500, "text/html", body="Internal Server Error")
    assert res.state == "down"
    assert res.status_code == 500


# ── probe_health: transport outcomes ─────────────────────────────────────────

def test_probe_up_on_genuine_body():
    with mock.patch.object(probe.urllib.request, "urlopen",
                           return_value=_FakeUrlResp(json.dumps(REAL_HEALTH_BODY).encode())):
        res = probe.probe_health("http://example.invalid/health", timeout=5)
    assert res.state == "up"
    assert res.data["version"] == "2.2.1"
    assert res.response_ms >= 0


def test_probe_impostor_on_spa_html():
    with mock.patch.object(probe.urllib.request, "urlopen",
                           return_value=_FakeUrlResp(SPA_HTML_BODY.encode(), content_type="text/html")):
        res = probe.probe_health("http://example.invalid/health", timeout=5)
    assert res.state == "impostor"


def test_probe_http_500_is_down():
    def boom(*a, **kw):
        raise urllib.error.HTTPError("http://example.invalid/health", 500, "SERVER ERROR", {}, None)

    with mock.patch.object(probe.urllib.request, "urlopen", side_effect=boom):
        res = probe.probe_health("http://example.invalid/health", timeout=5)
    assert res.state == "down"


def test_probe_timeout_is_unreachable():
    def boom(*a, **kw):
        raise socket.timeout("timed out")

    with mock.patch.object(probe.urllib.request, "urlopen", side_effect=boom):
        res = probe.probe_health("http://example.invalid/health", timeout=0.1)
    assert res.state == "unreachable"


def test_probe_refused_is_unreachable():
    def boom(*a, **kw):
        raise urllib.error.URLError("Connection refused")

    with mock.patch.object(probe.urllib.request, "urlopen", side_effect=boom):
        res = probe.probe_health("http://example.invalid/health", timeout=5)
    assert res.state == "unreachable"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
