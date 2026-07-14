"""
Regression test for /api/network/stats active_miners count.

Bug: get_network_stats counted miners with m.get('status') == 'online', but the
raw node payload from /api/miners never carries a 'status' field — that field is
derived from last_seen only inside get_miners(). So active_miners was always 0,
regardless of how many miners were actually online.
"""
import os
import sys
from datetime import datetime
from unittest.mock import patch

# Add parent dir to path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app as explorer_app  # noqa: E402


class _FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _client():
    explorer_app.app.config["TESTING"] = True
    return explorer_app.app.test_client()


def test_active_miners_counts_recently_seen_miners():
    now = datetime.now().timestamp()
    # Raw node payload: no 'status' key, only last_seen (as the real node sends).
    payload = {
        "miners": [
            {"id": "a", "last_seen": now - 10},     # online  (<5m)
            {"id": "b", "last_seen": now - 120},    # online  (<5m)
            {"id": "c", "last_seen": now - 1800},   # idle    (30m)
            {"id": "d", "last_seen": now - 7200},   # offline (2h)
        ]
    }
    with patch.object(explorer_app.requests, "get", return_value=_FakeResponse(payload)):
        resp = _client().get("/api/network/stats")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_miners"] == 4
    # Two miners seen within 5 minutes -> active. On the buggy code this was 0.
    assert data["active_miners"] == 2


def test_active_miners_ignores_missing_or_bad_last_seen():
    now = datetime.now().timestamp()
    payload = {
        "miners": [
            {"id": "a", "last_seen": now - 5},   # online
            {"id": "b"},                          # no last_seen -> not online
            {"id": "c", "last_seen": "nope"},    # unparsable  -> not online
        ]
    }
    with patch.object(explorer_app.requests, "get", return_value=_FakeResponse(payload)):
        resp = _client().get("/api/network/stats")
    data = resp.get_json()
    assert data["active_miners"] == 1
