#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Cross-monitor tests for bounty #17180.

One shared probe, five monitors. The HTML-200 fixture (an SPA answering 200
on every path) must come out ``impostor`` in *every* monitor's output — that
is the acceptance criterion, so it is asserted per monitor here, against the
monitor's own code path with its own HTTP client mocked, not against the
probe in isolation.

Also covered: the exporter gauge goes to 0 on any failed scrape, the
last-success timestamp is exported and only moves on a genuine body, and the
vendored copies of the classifier (health dashboard, node_health_monitor,
node-health CLI fallback) return identical verdicts to the canonical
``monitoring/node_probe.py`` on every fixture.
"""

import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "monitoring"))
sys.path.insert(0, str(ROOT / "status"))
sys.path.insert(0, str(ROOT / "health-dashboard"))
sys.path.insert(0, str(ROOT / "tools" / "node-health-cli"))

from monitoring.node_probe import classify_health as canonical_classify  # noqa: E402

from test_node_probe import (  # noqa: E402
    GENUINE_BODY,
    GENUINE_BYTES,
    MISSING_KEYS_BYTES,
    NOT_OK_BYTES,
    SPA_HTML,
)

JSON_CT = "application/json"
HTML_CT = "text/html; charset=utf-8"

# (status_code, content_type, body) -> expected state. The parity check runs
# every classifier (canonical + each monitor's) over this matrix.
PARITY_MATRIX = [
    ((200, JSON_CT, GENUINE_BYTES), "up"),
    ((200, HTML_CT, SPA_HTML), "impostor"),
    ((200, "", SPA_HTML), "impostor"),
    ((200, "text/plain", b"OK"), "impostor"),
    ((200, JSON_CT, MISSING_KEYS_BYTES), "impostor"),
    ((200, JSON_CT, b"[1, 2, 3]"), "impostor"),
    ((200, JSON_CT, b""), "impostor"),
    ((503, JSON_CT, NOT_OK_BYTES), "degraded"),
    ((200, JSON_CT, json.dumps(dict(GENUINE_BODY, db_rw=False)).encode()),
     "degraded"),
    ((200, JSON_CT,
      json.dumps(dict(GENUINE_BODY, tip_age_slots=9999)).encode()),
     "degraded"),
    ((500, JSON_CT, b'{"error": "boom"}'), "down"),
    ((500, HTML_CT, SPA_HTML), "down"),
]


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _RequestsResponse:
    """Fake requests.Response with the attributes monitors actually read."""

    def __init__(self, status_code, content_type, body: bytes):
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.content = body

    def json(self):
        return json.loads(self.content.decode("utf-8"))

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError("HTTP %s" % self.status_code)


class _UrllibResponse(io.BytesIO):
    """Fake urllib response."""

    def __init__(self, payload: bytes, status: int = 200,
                 content_type: str = JSON_CT):
        super().__init__(payload)
        self.status = status
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# ── Per-monitor HTML-200 → impostor ───────────────────────────────────────────

class TestStatusPage(unittest.TestCase):
    """status/status_server.py — the status page must show impostor, not up."""

    def test_html_200_is_impostor(self):
        import status_server
        fake = _RequestsResponse(200, HTML_CT, SPA_HTML)
        with mock.patch.object(status_server.requests, "get",
                               return_value=fake):
            result = status_server.check_node(status_server.NODES[0])
        self.assertEqual(result["state"], "impostor")
        self.assertIs(result["up"], False)

    def test_genuine_body_is_up(self):
        import status_server
        fake = _RequestsResponse(200, JSON_CT, GENUINE_BYTES)
        with mock.patch.object(status_server.requests, "get",
                               return_value=fake):
            result = status_server.check_node(status_server.NODES[0])
        self.assertEqual(result["state"], "up")
        self.assertIs(result["up"], True)
        self.assertEqual(result["version"], "2.2.1")
        self.assertEqual(result["uptime"], 3600)


class TestHealthDashboard(unittest.TestCase):
    """health-dashboard/server.py — the dashboard must show impostor."""

    def test_html_200_is_impostor(self):
        import server
        fake = _RequestsResponse(200, HTML_CT, SPA_HTML)
        with mock.patch.object(server.requests, "get", return_value=fake):
            status = server.check_node_health(server.NODES[0])
        self.assertEqual(status.status, "impostor")
        self.assertIn("text/html", status.error)

    def test_genuine_body_is_up(self):
        import server
        fake = _RequestsResponse(200, JSON_CT, GENUINE_BYTES)
        with mock.patch.object(server.requests, "get", return_value=fake):
            status = server.check_node_health(server.NODES[0])
        self.assertEqual(status.status, "up")
        self.assertEqual(status.version, "2.2.1")
        self.assertEqual(status.uptime_s, 3600)
        self.assertIsNone(status.error)

    def test_ok_false_body_is_degraded(self):
        import server
        fake = _RequestsResponse(503, JSON_CT, NOT_OK_BYTES)
        with mock.patch.object(server.requests, "get", return_value=fake):
            status = server.check_node_health(server.NODES[0])
        self.assertEqual(status.status, "degraded")


class TestExporter(unittest.TestCase):
    """monitoring/rustchain-exporter.py — gauge to 0, timestamp exported."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "monitoring"))
        cls.mod = _load_module(
            "rustchain_exporter_under_test",
            ROOT / "monitoring" / "rustchain-exporter.py")

    def _collect_with_health(self, health_response):
        mod = self.mod

        def fake_get(url, **kwargs):
            if url.endswith("/health"):
                return health_response
            # /epoch and /api/miners fail: the health gauge must not depend
            # on them, and must still go to 0 on a bad /health.
            return _RequestsResponse(500, JSON_CT, b'{"error": "boom"}')

        with mock.patch.object(mod.requests, "get", side_effect=fake_get):
            mod.collect_metrics()

    def test_html_200_sets_health_zero_and_keeps_timestamp(self):
        from prometheus_client import generate_latest
        mod = self.mod
        # First a genuine scrape: gauge 1, timestamp set.
        self._collect_with_health(_RequestsResponse(200, JSON_CT,
                                                    GENUINE_BYTES))
        text = generate_latest().decode()
        self.assertIn("rustchain_node_health 1.0", text)
        self.assertIn('rustchain_node_health_state_info{state="up"}', text)
        before = mod.last_successful_scrape._value.get()
        self.assertGreater(before, 0)
        # Then the SPA: gauge 0, timestamp untouched, state visible.
        self._collect_with_health(_RequestsResponse(200, HTML_CT, SPA_HTML))
        text = generate_latest().decode()
        self.assertIn("rustchain_node_health 0.0", text)
        self.assertIn('rustchain_node_health_state_info{state="impostor"}',
                      text)
        self.assertIn("rustchain_last_successful_scrape_timestamp", text)
        self.assertEqual(mod.last_successful_scrape._value.get(), before)

    def test_500_sets_health_zero(self):
        from prometheus_client import generate_latest
        self._collect_with_health(
            _RequestsResponse(500, JSON_CT, b'{"error": "boom"}'))
        text = generate_latest().decode()
        self.assertIn("rustchain_node_health 0.0", text)

    def test_degraded_sets_health_zero_but_updates_timestamp(self):
        from prometheus_client import generate_latest
        mod = self.mod
        self._collect_with_health(_RequestsResponse(503, JSON_CT,
                                                    NOT_OK_BYTES))
        text = generate_latest().decode()
        self.assertIn("rustchain_node_health 0.0", text)
        self.assertIn('rustchain_node_health_state_info{state="degraded"}',
                      text)
        # A real node answered with a valid body, so the scrape succeeded.
        self.assertGreater(mod.last_successful_scrape._value.get(), 0)


class TestNodeHealthMonitor(unittest.TestCase):
    """tools/node_health_monitor.py — impostor is surfaced, not "online"."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module(
            "node_health_monitor_under_test",
            ROOT / "tools" / "node_health_monitor.py")

    def _check(self, health_body, health_ct=JSON_CT, epoch_body=None):
        mod = self.mod
        if epoch_body is None:
            epoch_body = json.dumps({"epoch": 254, "miners": 19}).encode()

        def fake_urlopen(req, timeout=None):
            if req.full_url.endswith("/health"):
                return _UrllibResponse(health_body, 200, health_ct)
            return _UrllibResponse(epoch_body, 200, JSON_CT)

        mon = mod.NodeHealthMonitor(nodes=["http://example.invalid"])
        with mock.patch.object(mod.urllib.request, "urlopen", fake_urlopen):
            return mon.check_node("http://example.invalid")

    def test_html_200_is_impostor(self):
        # An SPA answers HTML on every path, so /epoch gets HTML too and
        # the epoch probe already says offline; the /health probe names it.
        result = self._check(SPA_HTML, HTML_CT, epoch_body=SPA_HTML)
        self.assertEqual(result.health_state, "impostor")
        # The pre-existing contract still holds: an impostor is not online.
        self.assertEqual(result.status, "offline")

    def test_genuine_body_is_up(self):
        result = self._check(GENUINE_BYTES)
        self.assertEqual(result.health_state, "up")
        self.assertEqual(result.status, "online")

    def test_ok_false_body_is_degraded(self):
        result = self._check(NOT_OK_BYTES)
        self.assertEqual(result.health_state, "degraded")


class TestNodeHealthCli(unittest.TestCase):
    """tools/node-health-cli/node_health.py — distinct impostor state."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "tools" / "node-health-cli"))
        import node_health
        cls.mod = node_health

    def test_html_200_is_impostor(self):
        mod = self.mod
        fake = mock.MagicMock()
        fake.read.return_value = SPA_HTML
        fake.__enter__.return_value = fake
        with mock.patch.object(mod, "urlopen", return_value=fake):
            result = mod.check_health("https://rustchain.org", timeout=10)
        self.assertEqual(result.state, "impostor")
        self.assertIs(result.ok, False)
        self.assertIsNotNone(result.error)

    def test_genuine_body_is_up(self):
        mod = self.mod
        fake = mock.MagicMock()
        fake.read.return_value = GENUINE_BYTES
        fake.__enter__.return_value = fake
        with mock.patch.object(mod, "urlopen", return_value=fake):
            result = mod.check_health("https://rustchain.org", timeout=10)
        self.assertEqual(result.state, "up")
        self.assertIs(result.ok, True)
        self.assertEqual(result.version, "2.2.1")
        self.assertIsNone(result.error)

    def test_impostor_fails_run_checks(self):
        mod = self.mod
        fake = mock.MagicMock()
        fake.read.return_value = SPA_HTML
        fake.__enter__.return_value = fake
        with mock.patch.object(mod, "urlopen", return_value=fake):
            result = mod.run_checks("https://rustchain.org", timeout=10)
        self.assertIs(result.overall_ok, False)
        self.assertNotEqual(result.exit_code, mod.EXIT_OK)


# ── Parity: vendored copies must agree with the canonical probe ─────────────

class _BlockImport:
    """Meta-path finder that refuses one top-level package.

    Used to force the import-first/vendored-fallback modules down their
    fallback path, so the parity check exercises the vendored copy itself
    rather than the canonical import it normally takes in a checkout.
    """

    def __init__(self, prefix):
        self.prefix = prefix

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.prefix or fullname.startswith(self.prefix + "."):
            raise ImportError("blocked for parity test: " + fullname)
        return None


class TestVendoredParity(unittest.TestCase):
    """Every classifier copy returns the canonical verdict on all fixtures."""

    def _classifiers(self):
        import server  # health-dashboard (vendored)
        # "monitoring" is already imported by this file, so the finder alone
        # would not fire: pop the cached modules first, restore afterwards.
        saved = {name: sys.modules.pop(name) for name in
                 ("monitoring", "monitoring.node_probe")
                 if name in sys.modules}
        blocker = _BlockImport("monitoring")
        sys.meta_path.insert(0, blocker)
        try:
            monitor = _load_module(
                "node_health_monitor_parity",
                ROOT / "tools" / "node_health_monitor.py")
            cli = _load_module(
                "node_health_parity",
                ROOT / "tools" / "node-health-cli" / "node_health.py")
        finally:
            sys.meta_path.remove(blocker)
            sys.modules.update(saved)
        return {
            "canonical": canonical_classify,
            "health-dashboard": server.classify_health,
            "node_health_monitor": monitor.classify_health,
            "node-health-cli": cli.classify_health,
        }

    def test_all_classifiers_agree(self):
        classifiers = self._classifiers()
        for (status_code, content_type, body), expected in PARITY_MATRIX:
            want = canonical_classify(status_code, content_type, body)
            self.assertEqual(want.state, expected)
            for name, fn in classifiers.items():
                got = fn(status_code, content_type, body)
                self.assertEqual(
                    got.state, expected,
                    "%s disagrees on (%s, %r, %r...): got %s, want %s"
                    % (name, status_code, content_type, body[:40],
                       got.state, expected))
                self.assertEqual(got.detail, want.detail,
                                 "%s detail differs on %s" % (name, expected))


if __name__ == "__main__":
    unittest.main(verbosity=2)
