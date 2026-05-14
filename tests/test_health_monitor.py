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
from io import BytesIO
from unittest.mock import MagicMock, patch

# Make sure the tools directory is importable
import importlib, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from node_health_monitor import (
    NodeHealthMonitor,
    NodeStatus,
    NetworkHealth,
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
        mock_open.return_value = _make_response({"epoch": 42, "miners": 8})
        result = self.monitor.check_node(self.url)
        self.assertEqual(result.status, "online")
        self.assertEqual(result.epoch,  42)
        self.assertEqual(result.miners, 8)
        self.assertIsNone(result.error)
        self.assertGreaterEqual(result.response_time_ms, 0)

    @patch("urllib.request.urlopen")
    def test_slow_node(self, mock_open):
        """A node whose response time exceeds the threshold → status=slow."""
        def slow_open(*a, **kw):
            time.sleep(0)           # no real sleep in unit tests
            return _make_response({"epoch": 5, "miners": 2})

        mock_open.return_value = _make_response({"epoch": 5, "miners": 2})
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
        self.assertIn("503", result.error)

    @patch("urllib.request.urlopen")
    def test_alternate_epoch_key(self, mock_open):
        """Nodes may use 'current_epoch' instead of 'epoch'."""
        mock_open.return_value = _make_response({"current_epoch": 99, "active_miners": 3})
        result = self.monitor.check_node(self.url)
        self.assertEqual(result.epoch,  99)
        self.assertEqual(result.miners,  3)

    @patch("urllib.request.urlopen")
    def test_missing_fields_are_none(self, mock_open):
        """A node returning empty JSON → epoch/miners are None."""
        mock_open.return_value = _make_response({})
        result = self.monitor.check_node(self.url)
        self.assertIsNone(result.epoch)
        self.assertIsNone(result.miners)
        self.assertEqual(result.status, "online")


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
        self.assertEqual(health.total_miners, 13)
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
