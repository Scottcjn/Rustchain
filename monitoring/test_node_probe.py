#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fixture Unit Test Suite for Bounty #17180 (`monitoring/node_probe.py`)."""
import socket
import unittest
from node_probe import PrometheusNodeExporterState, probe_health


class TestNodeProbeFixtures(unittest.TestCase):
    def test_01_genuine_health_body_is_up(self):
        body = b'{"ok": true, "version": "2.2.1-rip200", "uptime_s": 86400, "db_rw": true, "tip_age_slots": 2}'
        res = probe_health(
            "https://node1.rustchain.org/health",
            fetcher=lambda u, t: (200, {"content-type": "application/json"}, body),
        )
        self.assertEqual(res.state, "up")
        self.assertTrue(res.is_up)
        self.assertEqual(res.version, "2.2.1-rip200")

    def test_02_html_spa_with_200_is_impostor_never_up(self):
        html_body = b"<!DOCTYPE html><html><head><title>Parked Domain SPA</title></head><body>Hello</body></html>"
        res = probe_health(
            "https://repurposed-ip.example/health",
            fetcher=lambda u, t: (200, {"content-type": "text/html; charset=utf-8"}, html_body),
        )
        self.assertEqual(res.state, "impostor")
        self.assertFalse(res.is_up)
        self.assertTrue(res.is_impostor)
        self.assertFalse(res.to_dict()["up"])

    def test_03_json_missing_keys_with_200_is_impostor(self):
        body = b'{"status": "alive", "hello": "world"}'
        res = probe_health(
            "https://impostor-json.example/health",
            fetcher=lambda u, t: (200, {"content-type": "application/json"}, body),
        )
        self.assertEqual(res.state, "impostor")
        self.assertIn("missing required keys", res.reason)

    def test_04_ok_false_or_db_rw_false_is_degraded(self):
        body = b'{"ok": false, "version": "2.2.1", "uptime_s": 120, "db_rw": false}'
        res = probe_health(
            "https://degraded.rustchain.org/health",
            fetcher=lambda u, t: (200, {"content-type": "application/json"}, body),
        )
        self.assertEqual(res.state, "degraded")
        self.assertFalse(res.is_up)

    def test_05_http_500_is_down(self):
        res = probe_health(
            "https://broken.rustchain.org/health",
            fetcher=lambda u, t: (500, {"content-type": "text/plain"}, b"Internal Server Error"),
        )
        self.assertEqual(res.state, "down")
        self.assertEqual(res.http_status, 500)

    def test_06_timeout_is_unreachable_and_exporter_zeroes_gauge(self):
        def _timeout_fetcher(u, t):
            raise socket.timeout("timed out")

        exporter = PrometheusNodeExporterState()
        up_res = probe_health(
            "https://node1.rustchain.org/health",
            fetcher=lambda u, t: (200, {"content-type": "application/json"}, b'{"ok":true,"version":"2.2.1","uptime_s":10}'),
        )
        m1 = exporter.record_probe("node1", up_res)
        self.assertEqual(m1["rustchain_node_health"], 1)
        last_ts = m1["rustchain_last_successful_scrape_timestamp"]
        self.assertGreater(last_ts, 0)

        timeout_res = probe_health("https://node1.rustchain.org/health", fetcher=_timeout_fetcher)
        self.assertEqual(timeout_res.state, "unreachable")
        m2 = exporter.record_probe("node1", timeout_res)
        self.assertEqual(m2["rustchain_node_health"], 0)
        self.assertEqual(m2["rustchain_last_successful_scrape_timestamp"], last_ts)


if __name__ == "__main__":
    unittest.main()
