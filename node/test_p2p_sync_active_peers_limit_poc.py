"""
PoC: PeerManager.get_active_peers() had no LIMIT on the SQL query.
fetchall() returned every active peer row in the 'peers' table.
This method is called on every sync cycle (every 30 s) and every
health-check loop (every 60 s). An attacker can flood /p2p/announce
with distinct valid public IPs to grow the peers table and cause OOM.

Before fix: SELECT peer_url FROM peers WHERE is_active=1 AND last_seen > ?
After fix:  ... LIMIT 500
"""
import sqlite3
import time
import unittest
import tempfile
import os

from rustchain_p2p_sync import PeerManager


def _make_peer_db(path: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS peers (
                peer_url TEXT PRIMARY KEY,
                is_active INTEGER DEFAULT 1,
                last_seen INTEGER,
                last_block_height INTEGER DEFAULT 0
            )
        """)
        conn.commit()


def _insert_peers(path: str, count: int, active: bool = True, ts_offset: int = 0):
    ts = int(time.time()) + ts_offset
    is_active = 1 if active else 0
    with sqlite3.connect(path) as conn:
        for i in range(count):
            conn.execute(
                "INSERT OR IGNORE INTO peers (peer_url, is_active, last_seen) VALUES (?, ?, ?)",
                (f"http://10.0.{i // 256}.{i % 256}:7333", is_active, ts)
            )
        conn.commit()


class TestGetActivePeersLimit(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        _make_peer_db(self.db_path)
        self.mgr = PeerManager(self.db_path, local_host="127.0.0.1", local_port=7333)

    def tearDown(self):
        os.unlink(self.db_path)

    def test_caps_at_max_active_peers(self):
        """With more peers than the cap, only _MAX_ACTIVE_PEERS are returned."""
        over_limit = PeerManager._MAX_ACTIVE_PEERS + 50
        _insert_peers(self.db_path, over_limit)
        result = self.mgr.get_active_peers()
        self.assertLessEqual(len(result), PeerManager._MAX_ACTIVE_PEERS,
                             f"Expected at most {PeerManager._MAX_ACTIVE_PEERS}, got {len(result)}")

    def test_returns_all_when_under_limit(self):
        """Fewer peers than the cap — all are returned."""
        count = 10
        _insert_peers(self.db_path, count)
        result = self.mgr.get_active_peers()
        self.assertEqual(len(result), count)

    def test_excludes_inactive_peers(self):
        """Inactive peers are not included."""
        _insert_peers(self.db_path, 5, active=True)
        _insert_peers(self.db_path, 3, active=False)
        result = self.mgr.get_active_peers()
        self.assertEqual(len(result), 5)

    def test_excludes_stale_peers(self):
        """Peers last seen more than 5 minutes ago are excluded."""
        _insert_peers(self.db_path, 5, ts_offset=0)       # fresh
        _insert_peers(self.db_path, 3, ts_offset=-400)    # stale (>300 s old)
        result = self.mgr.get_active_peers()
        self.assertEqual(len(result), 5)

    def test_empty_table(self):
        result = self.mgr.get_active_peers()
        self.assertEqual(result, [])

    def test_returns_list_of_strings(self):
        _insert_peers(self.db_path, 2)
        result = self.mgr.get_active_peers()
        self.assertEqual(len(result), 2)
        for url in result:
            self.assertIsInstance(url, str)


if __name__ == "__main__":
    unittest.main()
