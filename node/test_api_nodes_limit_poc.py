# SPDX-License-Identifier: MIT
"""
Real-route regression for the /api/nodes LIMIT 200 fix.

Seeds 250 rows into the app's actual SQLite DB, monkeypatches requests.get so
no outbound connections are made, calls GET /api/nodes through the real Flask
test client, and asserts both the returned node count and the number of
health-check attempts are at most 200.
"""

import gc
import importlib
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

_NODE_FILE = os.path.join(os.path.dirname(__file__),
                          "rustchain_v2_integrated_v2.2.1_rip200.py")
_MODULE_NAME = "rustchain_node"
_NODE_COUNT = 250
_LIMIT = 200


def _load_app(db_path: str):
    """Import the node module with RUSTCHAIN_DB_PATH pointed at db_path."""
    node_dir = os.path.dirname(_NODE_FILE)
    if node_dir not in sys.path:
        sys.path.insert(0, node_dir)
    os.environ["RUSTCHAIN_DB_PATH"] = db_path
    os.environ.setdefault("RC_ADMIN_KEY", "test-admin-key-not-real-padded-to-32ch")
    # Remove a cached import so the module re-evaluates DB_PATH.
    sys.modules.pop(_MODULE_NAME, None)
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _NODE_FILE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = mod
    spec.loader.exec_module(mod)
    return mod.app


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
                (f"node-{i}", f"RTC{'a' * 40}",
                 f"http://203.0.113.{i % 254 + 1}/",
                 f"n{i}", 0, 1)
                for i in range(n)
            ],
        )
        conn.commit()


class TestApiNodesRealRoute(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._tmp.close()
        _seed_db(cls._tmp.name, _NODE_COUNT)
        cls.flask_app = _load_app(cls._tmp.name)
        cls.flask_app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls):
        # Release module and app references first so Windows releases the SQLite
        # file handle before we attempt to unlink.
        sys.modules.pop(_MODULE_NAME, None)
        cls.flask_app = None
        gc.collect()
        try:
            os.unlink(cls._tmp.name)
        except OSError:
            pass

    def _fake_get(self, url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        return resp

    def test_node_count_capped_at_200(self):
        """Real handler must return at most 200 nodes when registry has 250."""
        mock_get = MagicMock(side_effect=self._fake_get)
        with patch("requests.get", mock_get):
            with self.flask_app.test_client() as client:
                rv = client.get("/api/nodes")

        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        nodes = data.get("nodes", [])
        self.assertLessEqual(
            len(nodes), _LIMIT,
            f"Handler returned {len(nodes)} nodes; expected at most {_LIMIT}",
        )
        self.assertEqual(
            len(nodes), _LIMIT,
            f"With {_NODE_COUNT} rows the cap should be exactly {_LIMIT}",
        )

    def test_health_check_calls_capped_at_200(self):
        """Handler must issue at most 200 health-check requests when registry has 250."""
        mock_get = MagicMock(side_effect=self._fake_get)
        with patch("requests.get", mock_get):
            with self.flask_app.test_client() as client:
                client.get("/api/nodes")

        self.assertLessEqual(
            mock_get.call_count, _LIMIT,
            f"Handler made {mock_get.call_count} health-check calls; "
            f"expected at most {_LIMIT}",
        )


if __name__ == "__main__":
    unittest.main()
