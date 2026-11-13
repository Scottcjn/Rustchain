"""
Tests for tools/node_health_monitor.py
Covers: normal responses, timeouts, HTTP errors, split-brain detection,
        consensus logic, and network health aggregation.
"""

import json
import sys
import time
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

# Make sure the tools directory is importable
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from node_health_monitor import (
    NodeHealthMonitor,
    NodeStatus,
    DEFAULT_NODES,
    DIM,
    GREEN,
    RESET,
    SLOW_THRESHOLD_MS,
    YELLOW,
    _color_ms,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_response(data: dict, status: int = 200) -> MagicMock:
    """Build a mock urllib response that returns JSON."""
    body   = json.dumps(data).encode()
    mock_r = MagicMock()
    mock_r.__enter__ = lambda s: s
    mock_r.__exit__  = MagicMock(return_value=False)
    mock_r.read      = MagicMock(return_value=body)
    mock_r.status    = status
    return mock_r


def _make_raw_response(raw: str, status: int = 200) -> MagicMock:
    """Build a mock urllib response that returns raw response text."""
    mock_r = MagicMock()
    mock_r.__enter__ = lambda s: s
    mock_r.__exit__ = MagicMock(return_value=False)
    mock_r.read = MagicMock(return_value=raw.encode())
    mock_r.status = status
    return mock_r


# A genuine /health body, as served by node api_health (ok/version/uptime_s).
HEALTH_OK = b'{"ok": true, "version": "2.2.1", "uptime_s": 3600, "db_rw": true, "tip_age_slots": 1}'


def _make_raw_response_bytes(raw: bytes, content_type: str = "application/json") -> MagicMock:
    mock_r = MagicMock()
    mock_r.__enter__ = lambda s: s
    mock_r.__exit__ = MagicMock(return_value=False)
    mock_r.read = MagicMock(return_value=raw)
    mock_r.status = 200
    headers = MagicMock()
    headers.get = lambda name, default=None: content_type if name == "Content-Type" else default
    mock_r.headers = headers
    return mock_r


def make_dispatch_urlopen(status_body, health_body=HEALTH_OK, health_ct="application/json"):
    """URL-aware urlopen fake: /health gets the health body, anything else the
    status body. The monitor probes /health through the shared probe first,
    then reads epoch/miners from the status endpoints."""
    def fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if url.rstrip("/").endswith("/health"):
            if isinstance(health_body, Exception):
                raise health_body
            return _make_raw_response_bytes(health_body, health_ct)
        if isinstance(status_body, Exception):
            raise status_body
        return _make_raw_response_bytes(status_body)
    return fake_urlopen


def _online_status(url: str, epoch: int = 10, miners: int = 5,
                   rt_ms: float = 100.0) -> NodeStatus:
    return NodeStatus(url=url, status="online", response_time_ms=rt_ms,
                      epoch=epoch, miners=miners, error=None)


def _offline_status(url: str) -> NodeStatus:
    return NodeStatus(url=url, status="offline", response_time_ms=None,
                      epoch=None, miners=None, error="Connection refused")


# ── Test class ─────────────────────────────────────────────────────────────────

class TestCheckNode(unittest.TestCase):

    def setUp(self):
        self.monitor = NodeHealthMonitor(nodes=DEFAULT_NODES, timeout=3)
        self.url     = "http://50.28.86.131:8088"

    @patch("urllib.request.urlopen")
    def test_healthy_node(self, mock_open):
        """A fast, valid JSON response → status=online."""
        mock_open.side_effect = make_dispatch_urlopen(b'{"epoch": 42, "miners": 8}')
        result = self.monitor.check_node(self.url)
        self.assertEqual(result.status, "online")
        self.assertEqual(result.epoch,  42)
        self.assertEqual(result.miners, 8)
        self.assertIsNone(result.error)
        self.assertEqual(result.probe_state, "up")
        self.assertGreaterEqual(result.response_time_ms, 0)

    @patch("urllib.request.urlopen")
    def test_slow_node(self, mock_open):
        """A node whose response time exceeds the threshold → status=slow."""
        mock_open.side_effect = make_dispatch_urlopen(b'{"epoch": 5, "miners": 2}')
        result = self.monitor.check_node(self.url)
        # Manually force slow classification
        result.response_time_ms = SLOW_THRESHOLD_MS + 1
        result.status = "slow" if result.response_time_ms > SLOW_THRESHOLD_MS else "online"
        self.assertEqual(result.status, "slow")

    @patch("urllib.request.urlopen")
    def test_timeout_marks_offline(self, mock_open):
        """A timeout exception → status=offline with error message."""
        mock_open.side_effect = TimeoutError("timed out")
        result = self.monitor.check_node(self.url)
        self.assertEqual(result.status, "offline")
        self.assertEqual(result.probe_state, "unreachable")
        self.assertIsNone(result.response_time_ms)
        self.assertIsNotNone(result.error)

    @patch("urllib.request.urlopen")
    def test_connection_refused_marks_offline(self, mock_open):
        """Connection refused → status=offline."""
        import socket
        mock_open.side_effect = socket.error("Connection refused")
        result = self.monitor.check_node(self.url)
        self.assertEqual(result.status, "offline")
        self.assertIsNone(result.epoch)

    @patch("urllib.request.urlopen")
    def test_http_error_marks_slow(self, mock_open):
        """HTTP 503 → status=slow (node is up but degraded)."""
        mock_open.side_effect = urllib.error.HTTPError(
            url=self.url, code=503, msg="Service Unavailable",
            hdrs=MagicMock(), fp=None
        )
        result = self.monitor.check_node(self.url)
        self.assertEqual(result.status, "slow")
        self.assertEqual(result.probe_state, "down")
        self.assertIn("503", result.error)

    @patch("urllib.request.urlopen")
    def test_alternate_epoch_key(self, mock_open):
        """Nodes may use 'current_epoch' instead of 'epoch'."""
        mock_open.side_effect = make_dispatch_urlopen(b'{"current_epoch": 99, "active_miners": 3}')
        result = self.monitor.check_node(self.url)
        self.assertEqual(result.epoch,  99)
        self.assertEqual(result.miners,  3)

    @patch("urllib.request.urlopen")
    def test_impostor_html_200_is_offline(self, mock_open):
        """Issue #17180: an SPA answering 200 on /health is an impostor."""
        spa = (b'<!doctype html><html><head><title>New API</title></head>'
               b'<body><div id="root"></div></body></html>')
        mock_open.side_effect = make_dispatch_urlopen(
            b'{"epoch": 1}', health_body=spa, health_ct="text/html")
        result = self.monitor.check_node(self.url)
        self.assertEqual(result.status, "offline")
        self.assertEqual(result.probe_state, "impostor")
        self.assertIn("IMPOSTOR", result.error)
        self.assertIsNone(result.epoch)

    @patch("urllib.request.urlopen")
    def test_json_without_node_state_is_not_online(self, mock_open):
        """Empty JSON is a reply, not a node.

        This previously asserted "online". The reasoning was that a reply
        proves reachability, which is true and is still reported: the response
        time is kept and `error` says exactly what came back. What changed is
        that it no longer counts toward nodes_online.

        The cost of the old behaviour was concrete. Node 4 stopped being a node
        and the host was reused for a single-page app, which answers 200 on
        every path. It was reported online for months and the fleet was
        believed to be four nodes when it was two.
        """
        mock_open.side_effect = make_dispatch_urlopen(b'{}', health_body=b'{}')
        result = self.monitor.check_node(self.url)
        self.assertIsNone(result.epoch)
        self.assertIsNone(result.miners)
        self.assertEqual(result.status, "offline")
        self.assertEqual(result.probe_state, "impostor")
        self.assertIsNotNone(result.error)
        self.assertIsNotNone(result.response_time_ms,
                             "reachability information must not be lost")

    @patch("urllib.request.urlopen")
    def test_non_object_json_is_reachable_but_not_online(self, mock_open):
        """Wrong-shaped JSON still reports reachability, but is not a node.

        Also previously "online". A JSON array is something else answering on
        this address; the probe should say so rather than count it as a healthy
        node.
        """
        mock_open.side_effect = make_dispatch_urlopen(b'[]', health_body=b'[]')
        result = self.monitor.check_node(self.url)
        self.assertEqual(result.status, "offline")
        self.assertEqual(result.probe_state, "impostor")
        self.assertIsNone(result.epoch)
        self.assertIsNone(result.miners)
        self.assertIsNotNone(result.error, "the operator needs to know WHY")
        self.assertIsNotNone(result.response_time_ms)


class TestCheckAll(unittest.TestCase):

    def test_returns_one_status_per_node(self):
        monitor = NodeHealthMonitor(nodes=DEFAULT_NODES)
        with patch.object(monitor, "check_node", return_value=_online_status("http://x")):
            results = monitor.check_all()
        self.assertEqual(len(results), len(DEFAULT_NODES))


class TestDetectSplitBrain(unittest.TestCase):

    def setUp(self):
        self.monitor = NodeHealthMonitor()

    def test_no_split_brain_same_epoch(self):
        statuses = [
            _online_status("http://a:8088", epoch=10),
            _online_status("http://b:8088", epoch=10),
            _online_status("http://c:8099", epoch=10),
        ]
        self.assertFalse(self.monitor.detect_split_brain(statuses))

    def test_split_brain_different_epochs(self):
        statuses = [
            _online_status("http://a:8088", epoch=10),
            _online_status("http://b:8088", epoch=11),  # diverged!
            _online_status("http://c:8099", epoch=10),
        ]
        self.assertTrue(self.monitor.detect_split_brain(statuses))

    def test_offline_node_excluded_from_split_brain(self):
        """An offline node with no epoch should not trigger split brain."""
        statuses = [
            _online_status("http://a:8088", epoch=10),
            _offline_status("http://b:8088"),
            _online_status("http://c:8099", epoch=10),
        ]
        self.assertFalse(self.monitor.detect_split_brain(statuses))

    def test_single_online_node_no_split(self):
        statuses = [
            _online_status("http://a:8088", epoch=7),
            _offline_status("http://b:8088"),
            _offline_status("http://c:8099"),
        ]
        self.assertFalse(self.monitor.detect_split_brain(statuses))

    def test_no_epoch_data_no_split(self):
        """Nodes with epoch=None should not produce false split brain."""
        statuses = [
            NodeStatus("http://a", "online", 50.0, None, 3, None),
            NodeStatus("http://b", "online", 60.0, None, 2, None),
        ]
        self.assertFalse(self.monitor.detect_split_brain(statuses))


class TestGetNetworkHealth(unittest.TestCase):

    def setUp(self):
        self.monitor = NodeHealthMonitor()

    def test_all_healthy(self):
        statuses = [
            _online_status("http://a:8088", epoch=5, miners=4),
            _online_status("http://b:8088", epoch=5, miners=3),
            _online_status("http://c:8099", epoch=5, miners=6),
        ]
        health = self.monitor.get_network_health(statuses)
        self.assertEqual(health.nodes_online, 3)
        # Nodes are replicas of one shared ledger (#8008): total_miners is the
        # agreed network-wide count (max, robust to a mid-sync node reporting
        # fewer), not the sum of per-replica reports.
        self.assertEqual(health.total_miners, 6)
        self.assertTrue(health.consensus_ok)
        self.assertFalse(health.split_brain)
        self.assertEqual(health.alerts, [])

    def test_one_offline_node(self):
        statuses = [
            _online_status("http://a:8088", epoch=5),
            _online_status("http://b:8088", epoch=5),
            _offline_status("http://c:8099"),
        ]
        health = self.monitor.get_network_health(statuses)
        self.assertEqual(health.nodes_online, 2)
        self.assertTrue(health.consensus_ok)
        self.assertGreater(len(health.alerts), 0)
        self.assertTrue(any("offline" in a.lower() for a in health.alerts))

    def test_split_brain_triggers_alert(self):
        statuses = [
            _online_status("http://a:8088", epoch=5),
            _online_status("http://b:8088", epoch=6),
            _online_status("http://c:8099", epoch=5),
        ]
        health = self.monitor.get_network_health(statuses)
        self.assertFalse(health.consensus_ok)
        self.assertTrue(health.split_brain)
        self.assertTrue(any("SPLIT BRAIN" in a for a in health.alerts))

    def test_all_offline(self):
        statuses = [
            _offline_status("http://a:8088"),
            _offline_status("http://b:8088"),
            _offline_status("http://c:8099"),
        ]
        health = self.monitor.get_network_health(statuses)
        self.assertEqual(health.nodes_online, 0)
        self.assertEqual(health.total_miners, 0)
        self.assertTrue(health.consensus_ok)  # vacuously true — no epochs to compare
        self.assertTrue(any("ALL NODES OFFLINE" in a for a in health.alerts))


class TestColorMs(unittest.TestCase):
    def test_none_renders_dim_placeholder(self):
        self.assertEqual(_color_ms(None), f"{DIM}     —{RESET}")

    def test_threshold_boundary_stays_green(self):
        self.assertEqual(
            _color_ms(SLOW_THRESHOLD_MS),
            f"{GREEN}{SLOW_THRESHOLD_MS:>7.1f}ms{RESET}",
        )

    def test_above_threshold_renders_yellow(self):
        slow_ms = SLOW_THRESHOLD_MS + 0.1
        self.assertEqual(_color_ms(slow_ms), f"{YELLOW}{slow_ms:>7.1f}ms{RESET}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
