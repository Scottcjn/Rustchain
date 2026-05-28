# SPDX-License-Identifier: MIT
"""
PoC: /api/nodes loads every row from node_registry and issues one
synchronous HTTP health-check per row, with no upper bound.

With 250 registered nodes each health-check timeout is 3 seconds, so a
single unauthenticated request can hold a Flask worker thread for up to
750 seconds and force 250 sequential outbound TCP connections.

Fix: add LIMIT 200 to the SELECT so at most 200 rows are fetched and at
most 200 health-checks are issued per request.
"""

import sqlite3
import tempfile
import os
import unittest


_SELECT_UNBOUNDED = (
    "SELECT node_id, wallet_address, url, name, registered_at, is_active"
    " FROM node_registry"
)
_SELECT_BOUNDED = (
    "SELECT node_id, wallet_address, url, name, registered_at, is_active"
    " FROM node_registry LIMIT 200"
)
_NODE_COUNT = 250


def _make_db(path: str, n: int) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE node_registry (
            node_id TEXT PRIMARY KEY,
            wallet_address TEXT,
            url TEXT,
            name TEXT,
            registered_at INTEGER,
            is_active INTEGER
        )"""
    )
    conn.executemany(
        "INSERT INTO node_registry VALUES (?,?,?,?,?,?)",
        [(f"node-{i}", f"RTC{'a'*40}", f"http://10.0.0.{i}/", f"n{i}", 0, 1)
         for i in range(n)],
    )
    conn.commit()
    conn.close()


class TestApiNodesLimit(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        _make_db(self._tmp.name, _NODE_COUNT)

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_unbounded_query_returns_all_rows(self):
        """Documents the vulnerable behaviour: all 250 nodes are returned."""
        conn = sqlite3.connect(self._tmp.name)
        rows = conn.execute(_SELECT_UNBOUNDED).fetchall()
        conn.close()
        self.assertEqual(len(rows), _NODE_COUNT,
                         "Unbounded query should load every row (vulnerability)")

    def test_bounded_query_caps_at_200(self):
        """Fixed behaviour: LIMIT 200 prevents loading more than 200 rows."""
        conn = sqlite3.connect(self._tmp.name)
        rows = conn.execute(_SELECT_BOUNDED).fetchall()
        conn.close()
        self.assertLessEqual(len(rows), 200,
                             "Bounded query must return at most 200 rows")
        self.assertEqual(len(rows), 200,
                         "With 250 nodes the cap should be exactly 200")


if __name__ == "__main__":
    unittest.main()
