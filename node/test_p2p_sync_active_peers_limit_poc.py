"""
PoC tests for PeerManager eclipse-resistant peer selection and per-source
admission cap. get_active_peers() now uses a two-bucket strategy (75% freshest,
25% oldest-trusted) and add_peer() enforces _MAX_PEERS_PER_HOST per host.
"""
import sqlite3
import time
import unittest
import tempfile
import os
import gc

from rustchain_p2p_sync import PeerManager

_peer_counter = 0


def _insert_peers(path, count, host_prefix="peer", active=True,
                  ts_offset=0, added_offset=0):
    global _peer_counter
    ts = int(time.time()) + ts_offset
    added = int(time.time()) + added_offset
    is_active = 1 if active else 0
    with sqlite3.connect(path) as conn:
        for _ in range(count):
            host = f"{host_prefix}-{_peer_counter}.example.com"
            conn.execute(
                "INSERT OR IGNORE INTO peers "
                "(peer_url, peer_host, peer_port, last_seen, is_active, added_at) "
                "VALUES (?, ?, 7333, ?, ?, ?)",
                (f"http://{host}:7333", host, ts, is_active, added)
            )
            _peer_counter += 1
        conn.commit()


class TestGetActivePeersEclipseResistant(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.mgr = PeerManager(self.db_path, local_host="127.0.0.1", local_port=7333)

    def tearDown(self):
        self.mgr = None
        gc.collect()
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_caps_at_max_active_peers(self):
        _insert_peers(self.db_path, PeerManager._MAX_ACTIVE_PEERS + 50)
        self.assertLessEqual(len(self.mgr.get_active_peers()), PeerManager._MAX_ACTIVE_PEERS)

    def test_returns_all_when_under_limit(self):
        _insert_peers(self.db_path, 10)
        self.assertEqual(len(self.mgr.get_active_peers()), 10)

    def test_excludes_inactive_peers(self):
        _insert_peers(self.db_path, 5, active=True)
        _insert_peers(self.db_path, 3, active=False)
        self.assertEqual(len(self.mgr.get_active_peers()), 5)

    def test_excludes_stale_peers(self):
        _insert_peers(self.db_path, 4, ts_offset=0)
        _insert_peers(self.db_path, 3, ts_offset=-400)
        self.assertEqual(len(self.mgr.get_active_peers()), 4)

    def test_empty_table(self):
        self.assertEqual(self.mgr.get_active_peers(), [])

    def test_returns_list_of_strings(self):
        _insert_peers(self.db_path, 3)
        self.assertTrue(all(isinstance(u, str) for u in self.mgr.get_active_peers()))

    def test_trust_tier_survives_flood(self):
        """Oldest-trusted peers appear in results even when flooded with fresh ones."""
        _insert_peers(self.db_path, 5, host_prefix="honest", added_offset=-10000)
        _insert_peers(self.db_path, PeerManager._MAX_ACTIVE_PEERS,
                      host_prefix="flood", ts_offset=10)
        result = self.mgr.get_active_peers()
        trust_cap = PeerManager._MAX_ACTIVE_PEERS - int(
            PeerManager._MAX_ACTIVE_PEERS * PeerManager._FRESH_FRACTION
        )
        honest = [u for u in result if "honest" in u]
        self.assertGreaterEqual(len(honest), min(5, trust_cap))

    def test_per_host_admission_cap(self):
        """A single host cannot exceed _MAX_PEERS_PER_HOST entries."""
        cap = PeerManager._MAX_PEERS_PER_HOST
        for i in range(cap + 3):
            self.mgr.add_peer(f"http://attacker.evil.com:{9000 + i}")
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM peers WHERE peer_host=?",
                ("attacker.evil.com",)
            ).fetchone()[0]
        self.assertLessEqual(count, cap)

    def test_re_announce_preserves_added_at(self):
        """Re-announcing an existing peer must not reset its added_at."""
        self.mgr.add_peer("http://stable.node.net:8088")
        with sqlite3.connect(self.db_path) as conn:
            orig = conn.execute(
                "SELECT added_at FROM peers WHERE peer_url=?",
                ("http://stable.node.net:8088",)
            ).fetchone()[0]
        time.sleep(0.05)
        self.mgr.add_peer("http://stable.node.net:8088")
        with sqlite3.connect(self.db_path) as conn:
            new = conn.execute(
                "SELECT added_at FROM peers WHERE peer_url=?",
                ("http://stable.node.net:8088",)
            ).fetchone()[0]
        self.assertEqual(orig, new)


if __name__ == "__main__":
    unittest.main()
