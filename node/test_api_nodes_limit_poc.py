# SPDX-License-Identifier: MIT
"""
Real-route regression for the /api/nodes pagination + decoupled health-probe fix.

Seeds 250 rows into the app's actual SQLite DB, monkeypatches requests.get so
no outbound connections are made, calls GET /api/nodes through the real Flask
test client, and verifies:
  - default page size is capped at 20 (not 200+)
  - limit/offset pagination works correctly
  - at most _MAX_INLINE_PROBES outbound health probes are issued per request
  - response includes pagination metadata (total, offset, limit)
"""

import gc
import importlib
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

_NODE_FILE = os.path.join(os.path.dirname(__file__),
                          "rustchain_v2_integrated_v2.2.1_rip200.py")
_MODULE_NAME = "rustchain_node"
_NODE_COUNT = 250
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 50
_MAX_INLINE_PROBES = 3


def _load_app(db_path: str):
    """Import the node module with RUSTCHAIN_DB_PATH pointed at db_path."""
    node_dir = os.path.dirname(_NODE_FILE)
    if node_dir not in sys.path:
        sys.path.insert(0, node_dir)
    os.environ["RUSTCHAIN_DB_PATH"] = db_path
    os.environ.setdefault("RC_ADMIN_KEY", "test-admin-key-not-real-padded-to-32ch")
    sys.modules.pop(_MODULE_NAME, None)
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _NODE_FILE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = mod
    spec.loader.exec_module(mod)
    return mod.app, mod


def _seed_db(path: str, n: int) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS node_registry (
                node_id TEXT PRIMARY KEY,
                wallet_address TEXT,
                url TEXT,
                name TEXT,
                registered_at INTEGER,
                is_active INTEGER
            )"""
        )
        conn.executemany(
            "INSERT OR IGNORE INTO node_registry VALUES (?,?,?,?,?,?)",
            [
                # Use hostname URLs so _should_redact_url returns False (non-IP hosts
                # are assumed public) and probe/cache logic is exercised in tests.
                (f"node-{i}", f"RTC{'a' * 40}",
                 f"http://node{i}.test.example.com:{9000 + i}/",
                 f"n{i}", 0, 1)
                for i in range(n)
            ],
        )
        conn.commit()


def _fake_get(url, **kwargs):
    resp = MagicMock()
    resp.status_code = 200
    return resp


class TestApiNodesPaginationAndProbeCap(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._tmp.close()
        _seed_db(cls._tmp.name, _NODE_COUNT)
        cls.flask_app, cls.mod = _load_app(cls._tmp.name)
        cls.flask_app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop(_MODULE_NAME, None)
        cls.flask_app = None
        cls.mod = None
        gc.collect()
        gc.collect()
        try:
            os.unlink(cls._tmp.name)
        except OSError:
            pass

    def _clear_health_cache(self):
        """Reset the module-level health cache between tests."""
        self.mod._NODE_HEALTH_CACHE.clear()

    def test_default_page_size_is_bounded(self):
        """Default /api/nodes must return at most _DEFAULT_LIMIT nodes."""
        self._clear_health_cache()
        with patch("requests.get", side_effect=_fake_get):
            with self.flask_app.test_client() as client:
                rv = client.get("/api/nodes")
        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        self.assertLessEqual(len(data["nodes"]), _DEFAULT_LIMIT)
        self.assertEqual(len(data["nodes"]), _DEFAULT_LIMIT,
                         "Default page should be exactly _DEFAULT_LIMIT rows")

    def test_pagination_metadata_present(self):
        """Response must include total, offset and limit fields."""
        self._clear_health_cache()
        with patch("requests.get", side_effect=_fake_get):
            with self.flask_app.test_client() as client:
                rv = client.get("/api/nodes?limit=10&offset=0")
        data = rv.get_json()
        self.assertIn("total", data)
        self.assertIn("offset", data)
        self.assertIn("limit", data)
        self.assertEqual(data["total"], _NODE_COUNT)
        self.assertEqual(data["offset"], 0)
        self.assertEqual(data["limit"], 10)

    def test_offset_advances_page(self):
        """Consecutive pages must return non-overlapping node sets."""
        self._clear_health_cache()
        with patch("requests.get", side_effect=_fake_get):
            with self.flask_app.test_client() as client:
                rv1 = client.get("/api/nodes?limit=10&offset=0")
                rv2 = client.get("/api/nodes?limit=10&offset=10")
        ids1 = {n["node_id"] for n in rv1.get_json()["nodes"]}
        ids2 = {n["node_id"] for n in rv2.get_json()["nodes"]}
        self.assertEqual(len(ids1), 10)
        self.assertEqual(len(ids2), 10)
        self.assertTrue(ids1.isdisjoint(ids2), "Pages must not overlap")

    def test_limit_capped_at_max(self):
        """Requesting more than _MAX_LIMIT nodes must be silently capped."""
        self._clear_health_cache()
        with patch("requests.get", side_effect=_fake_get):
            with self.flask_app.test_client() as client:
                rv = client.get(f"/api/nodes?limit=1000")
        data = rv.get_json()
        self.assertLessEqual(len(data["nodes"]), _MAX_LIMIT)

    def test_health_probe_calls_capped_per_request(self):
        """A single /api/nodes call must issue at most _MAX_INLINE_PROBES outbound requests."""
        self._clear_health_cache()
        mock_get = MagicMock(side_effect=_fake_get)
        with patch("requests.get", mock_get):
            with self.flask_app.test_client() as client:
                client.get("/api/nodes?limit=50&offset=0")
        self.assertLessEqual(
            mock_get.call_count, _MAX_INLINE_PROBES,
            f"Handler made {mock_get.call_count} probes; expected at most {_MAX_INLINE_PROBES}",
        )

    def test_cached_health_status_reused(self):
        """Second request for the same page must not issue any new probes."""
        self._clear_health_cache()
        # Use a page size <= _MAX_INLINE_PROBES so the first request fully
        # populates the cache for every node on the page.
        page_size = _MAX_INLINE_PROBES
        mock_get = MagicMock(side_effect=_fake_get)
        with patch("requests.get", mock_get):
            with self.flask_app.test_client() as client:
                client.get(f"/api/nodes?limit={page_size}&offset=0")
        self.assertLessEqual(mock_get.call_count, page_size,
                             "First request probed more nodes than the page size")

        # Second identical request must serve every node from cache.
        mock_get2 = MagicMock(side_effect=_fake_get)
        with patch("requests.get", mock_get2):
            with self.flask_app.test_client() as client:
                client.get(f"/api/nodes?limit={page_size}&offset=0")
        self.assertEqual(mock_get2.call_count, 0,
                         "Second identical request must use cache and issue zero probes")

    def test_stale_cache_probes_again(self):
        """After TTL expires, the next request should re-probe up to the cap."""
        self._clear_health_cache()
        # Pre-populate cache with an expired timestamp.
        expired_ts = time.time() - self.mod._NODE_HEALTH_CACHE_TTL - 1
        with self.flask_app.test_client() as client:
            # Fetch to get node URLs from the first page.
            mock_get = MagicMock(side_effect=_fake_get)
            with patch("requests.get", mock_get):
                rv = client.get("/api/nodes?limit=5&offset=0")
            for node in rv.get_json()["nodes"]:
                url = node.get("url")
                if url:
                    self.mod._NODE_HEALTH_CACHE[url] = (True, expired_ts)

        mock_get2 = MagicMock(side_effect=_fake_get)
        with patch("requests.get", mock_get2):
            with self.flask_app.test_client() as client:
                client.get("/api/nodes?limit=5&offset=0")
        self.assertGreater(mock_get2.call_count, 0,
                           "Should re-probe at least one stale cache entry")
        self.assertLessEqual(mock_get2.call_count, _MAX_INLINE_PROBES,
                             "Re-probe count must still be bounded by the cap")

    def test_invalid_limit_returns_400(self):
        """Non-integer limit must return HTTP 400."""
        with self.flask_app.test_client() as client:
            rv = client.get("/api/nodes?limit=abc")
        self.assertEqual(rv.status_code, 400)

    def test_invalid_offset_returns_400(self):
        """Non-integer offset must return HTTP 400."""
        with self.flask_app.test_client() as client:
            rv = client.get("/api/nodes?offset=xyz")
        self.assertEqual(rv.status_code, 400)


if __name__ == "__main__":
    unittest.main()
