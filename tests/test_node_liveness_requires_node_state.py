#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""A 200 is not evidence of a node.

RustChain node 4 stopped being a node. The operator took it down and the host
was reused for a single-page app, which answers **200 on every unknown path**.
So `/status` returned 200 with HTML, `json.loads` raised, the body was quietly
replaced with `{}`, and the node was reported `online` — because status was
decided purely on response time:

    status = "slow" if elapsed_ms > SLOW_THRESHOLD_MS else "online"

The loss went unnoticed for months, and the fleet was believed to be four nodes
when it was two. Node 3 was only spotted because it had the decency to stop
answering at all.

A node is online only if it answered with JSON carrying node state. These tests
pin the three ways something can pretend: HTML, valid JSON from an unrelated
service, and an empty body.
"""

import importlib.util
import io
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
sys.path.insert(0, TOOLS)

_spec = importlib.util.spec_from_file_location(
    "node_health_monitor", os.path.join(TOOLS, "node_health_monitor.py")
)
MOD = importlib.util.module_from_spec(_spec)
sys.modules["node_health_monitor"] = MOD
_spec.loader.exec_module(MOD)


class _Resp(io.BytesIO):
    """Minimal stand-in for the urlopen context manager."""

    def __init__(self, payload: bytes):
        super().__init__(payload)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _probe(payload: bytes):
    mon = MOD.NodeHealthMonitor(nodes=["http://example.invalid"])
    with mock.patch.object(MOD.urllib.request, "urlopen",
                           return_value=_Resp(payload)):
        return mon.check_node("http://example.invalid")


REAL_STATUS = b'{"epoch": 254, "miners": 19, "ok": true}'

# what an SPA actually returns on every path
SPA_HTML = (b'<!doctype html><html lang="en"><head><title>New API</title>'
            b'</head><body><div id="root"></div></body></html>')


class ImpersonationTest(unittest.TestCase):

    def test_a_real_node_is_online(self):
        st = _probe(REAL_STATUS)
        self.assertEqual(st.status, "online")
        self.assertEqual(st.epoch, 254)
        self.assertEqual(st.miners, 19)
        self.assertIsNone(st.error)

    def test_an_spa_serving_html_is_offline(self):
        """The exact failure: 200 + HTML was reported online for months."""
        st = _probe(SPA_HTML)
        self.assertEqual(st.status, "offline",
                         "a website answering 200 must not count as a node")
        self.assertIsNone(st.epoch)
        self.assertIn("non-JSON", st.error)

    def test_valid_json_from_an_unrelated_service_is_offline(self):
        """Some other API on the address speaks JSON but is not a node."""
        st = _probe(b'{"error":{"message":"Invalid URL (GET /status)"}}')
        self.assertEqual(st.status, "offline")
        self.assertIn("no epoch", st.error)

    def test_an_empty_body_is_offline(self):
        st = _probe(b"")
        self.assertEqual(st.status, "offline")

    def test_a_json_array_is_offline(self):
        """json.loads succeeds but it is not an object."""
        st = _probe(b"[1, 2, 3]")
        self.assertEqual(st.status, "offline")


class ToleranceTest(unittest.TestCase):
    """Hardening must not make a healthy node look broken."""

    def test_alternate_field_names_still_resolve(self):
        st = _probe(b'{"current_epoch": 7, "active_miners": 3}')
        self.assertEqual(st.status, "online")
        self.assertEqual(st.epoch, 7)
        self.assertEqual(st.miners, 3)

    def test_a_node_reporting_zero_miners_is_still_online(self):
        """Node 2 legitimately had 0 enrolled miners; that is not death."""
        st = _probe(b'{"epoch": 254, "miners": 0}')
        self.assertEqual(st.status, "online")

    def test_a_malformed_miner_count_does_not_kill_the_probe(self):
        st = _probe(b'{"epoch": 254, "miners": "lots"}')
        self.assertEqual(st.status, "online")
        self.assertIsNone(st.miners)

    def test_a_malformed_epoch_is_treated_as_missing_state(self):
        st = _probe(b'{"epoch": "soon", "miners": 4}')
        self.assertEqual(st.status, "offline")

    def test_response_time_is_still_reported_when_impersonating(self):
        """Operators need the timing even when the body is rejected."""
        st = _probe(SPA_HTML)
        self.assertIsNotNone(st.response_time_ms)


if __name__ == "__main__":
    unittest.main(verbosity=2)
