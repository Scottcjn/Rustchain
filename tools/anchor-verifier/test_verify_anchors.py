#!/usr/bin/env python3
"""
Tests for Ergo Anchor Chain Proof Verifier

Run: python -m pytest tools/anchor-verifier/test_verify_anchors.py -v
"""

import hashlib
import json
import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_anchors import (
    blake2b256,
    canonical_json,
    AnchorRecord,
    AnchorVerifier,
    ErgoClient,
    VerificationResult,
    read_anchors,
    read_attestations_for_epoch,
    recompute_commitment,
    _merkle_root,
    R5_PREFIX,
    print_results,
)


# ── Blake2b256 Tests ─────────────────────────────────────────────

class TestBlake2b256(unittest.TestCase):
    def test_known_hash(self):
        h = blake2b256(b"test")
        self.assertEqual(len(h), 64)  # 32 bytes = 64 hex chars
        self.assertIsInstance(h, str)

    def test_empty(self):
        h = blake2b256(b"")
        self.assertEqual(len(h), 64)

    def test_deterministic(self):
        self.assertEqual(blake2b256(b"hello"), blake2b256(b"hello"))

    def test_different_input(self):
        self.assertNotEqual(blake2b256(b"a"), blake2b256(b"b"))


class TestCanonicalJSON(unittest.TestCase):
    def test_sorted_keys(self):
        result = canonical_json({"b": 1, "a": 2})
        self.assertEqual(result, '{"a":2,"b":1}')

    def test_no_whitespace(self):
        result = canonical_json({"key": "value"})
        self.assertNotIn(" ", result)

    def test_deterministic(self):
        d = {"z": 1, "a": 2, "m": 3}
        self.assertEqual(canonical_json(d), canonical_json(d))


# ── Merkle Root Tests ────────────────────────────────────────────

class TestMerkleRoot(unittest.TestCase):
    def test_single_leaf(self):
        root = _merkle_root(["aabb" * 16])
        self.assertEqual(root, "aabb" * 16)

    def test_two_leaves(self):
        h1 = blake2b256(b"leaf1")
        h2 = blake2b256(b"leaf2")
        root = _merkle_root([h1, h2])
        expected = blake2b256(bytes.fromhex(h1) + bytes.fromhex(h2))
        self.assertEqual(root, expected)

    def test_empty(self):
        root = _merkle_root([])
        self.assertEqual(len(root), 64)

    def test_odd_count_pads(self):
        hashes = [blake2b256(f"leaf{i}".encode()) for i in range(3)]
        root = _merkle_root(hashes)
        self.assertEqual(len(root), 64)

    def test_deterministic(self):
        hashes = [blake2b256(f"leaf{i}".encode()) for i in range(4)]
        self.assertEqual(_merkle_root(hashes), _merkle_root(hashes))


# ── ErgoClient Tests ─────────────────────────────────────────────

class TestErgoClient(unittest.TestCase):
    def setUp(self):
        self.client = ErgoClient("http://localhost:9053")

    def test_extract_commitment_r5(self):
        """Test extracting commitment from R5 register."""
        commitment = "a" * 64
        tx = {
            "outputs": [{
                "additionalRegisters": {
                    "R5": f"{R5_PREFIX}{commitment}"
                }
            }]
        }
        result = self.client.extract_commitment_from_tx(tx)
        self.assertEqual(result, commitment)

    def test_extract_commitment_r5_dict(self):
        """R5 as dict with serializedValue."""
        commitment = "b" * 64
        tx = {
            "outputs": [{
                "additionalRegisters": {
                    "R5": {"serializedValue": f"{R5_PREFIX}{commitment}"}
                }
            }]
        }
        result = self.client.extract_commitment_from_tx(tx)
        self.assertEqual(result, commitment)

    def test_extract_no_registers(self):
        tx = {"outputs": [{"additionalRegisters": {}}]}
        result = self.client.extract_commitment_from_tx(tx)
        self.assertIsNone(result)

    def test_extract_empty_outputs(self):
        tx = {"outputs": []}
        result = self.client.extract_commitment_from_tx(tx)
        self.assertIsNone(result)

    def test_extract_no_outputs(self):
        tx = {}
        result = self.client.extract_commitment_from_tx(tx)
        self.assertIsNone(result)

    def test_extract_wrong_prefix(self):
        tx = {
            "outputs": [{
                "additionalRegisters": {
                    "R5": "0e20" + "c" * 32  # Wrong length prefix
                }
            }]
        }
        result = self.client.extract_commitment_from_tx(tx)
        self.assertIsNone(result)


# ── Database Tests ───────────────────────────────────────────────

class TestDatabaseReader(unittest.TestCase):
    def setUp(self):
        self.db_path = "/tmp/test_anchors.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ergo_anchors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rustchain_height INTEGER NOT NULL,
                rustchain_hash TEXT NOT NULL,
                commitment_hash TEXT NOT NULL,
                ergo_tx_id TEXT NOT NULL,
                ergo_height INTEGER,
                confirmations INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at INTEGER NOT NULL
            )
        """)
        # Insert test data
        for i in range(5):
            conn.execute(
                "INSERT INTO ergo_anchors "
                "(rustchain_height, rustchain_hash, commitment_hash, ergo_tx_id, "
                "ergo_height, confirmations, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (100 + i, f"hash_{i}", f"commit_{i}", f"tx_{i}",
                 200 + i, 6, "confirmed", 1000 + i)
            )
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_read_all(self):
        anchors = read_anchors(self.db_path)
        self.assertEqual(len(anchors), 5)

    def test_read_limit(self):
        anchors = read_anchors(self.db_path, limit=2)
        self.assertEqual(len(anchors), 2)

    def test_read_ordered_desc(self):
        anchors = read_anchors(self.db_path)
        heights = [a.rustchain_height for a in anchors]
        self.assertEqual(heights, sorted(heights, reverse=True))

    def test_read_nonexistent_db(self):
        anchors = read_anchors("/tmp/nonexistent_db.db")
        self.assertEqual(anchors, [])

    def test_anchor_fields(self):
        anchors = read_anchors(self.db_path, limit=1)
        a = anchors[0]
        self.assertIsInstance(a.id, int)
        self.assertIsInstance(a.rustchain_height, int)
        self.assertIsInstance(a.commitment_hash, str)
        self.assertIsInstance(a.ergo_tx_id, str)


class TestAttestationReader(unittest.TestCase):
    def setUp(self):
        self.db_path = "/tmp/test_attestations.db"

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_read_attestations_nonexistent_db(self):
        rows = read_attestations_for_epoch("/tmp/nonexistent_attestations.db", 100)

        self.assertEqual(rows, [])

    def test_read_attestations_falls_back_to_later_table(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE miner_attest_recent (
                miner_id TEXT NOT NULL,
                epoch INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE attestations (
                miner_id TEXT NOT NULL,
                epoch INTEGER NOT NULL,
                height INTEGER NOT NULL,
                fingerprint_hash TEXT NOT NULL
            )
        """)
        conn.executemany(
            "INSERT INTO attestations (miner_id, epoch, height, fingerprint_hash) "
            "VALUES (?, ?, ?, ?)",
            [
                ("miner-b", 200, 200, "hash-b"),
                ("miner-a", 200, 200, "hash-a"),
                ("miner-c", 201, 201, "hash-c"),
            ],
        )
        conn.commit()
        conn.close()

        rows = read_attestations_for_epoch(self.db_path, 200)

        self.assertEqual([row["miner_id"] for row in rows], ["miner-a", "miner-b"])
        self.assertEqual([row["fingerprint_hash"] for row in rows], ["hash-a", "hash-b"])


# ── Verifier Tests ───────────────────────────────────────────────

class TestAnchorVerifier(unittest.TestCase):
    def setUp(self):
        self.db_path = "/tmp/test_verify.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ergo_anchors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rustchain_height INTEGER NOT NULL,
                rustchain_hash TEXT NOT NULL,
                commitment_hash TEXT NOT NULL,
                ergo_tx_id TEXT NOT NULL,
                ergo_height INTEGER,
                confirmations INTEGER DEFAULT 0,
                status TEXT DEFAULT 'confirmed',
                created_at INTEGER NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO ergo_anchors VALUES (1, 100, 'hash100', 'commit100', 'tx100', 200, 6, 'confirmed', 1000)"
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_offline_verification(self):
        verifier = AnchorVerifier(self.db_path, "http://fake", offline=True)
        results = verifier.verify_all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "OFFLINE_OK")

    def test_offline_has_stored_commitment(self):
        verifier = AnchorVerifier(self.db_path, "http://fake", offline=True)
        results = verifier.verify_all()
        self.assertEqual(results[0].stored_commitment, "commit100")

    def test_verify_one_offline(self):
        verifier = AnchorVerifier(self.db_path, "http://fake", offline=True)
        anchor = AnchorRecord(
            id=1, rustchain_height=100, rustchain_hash="h",
            commitment_hash="c", ergo_tx_id="tx", ergo_height=200,
            confirmations=6, status="confirmed", created_at=1000
        )
        result = verifier.verify_one(anchor)
        self.assertEqual(result.status, "OFFLINE_OK")


# ── Commitment Recomputation Tests ───────────────────────────────

class TestCommitmentRecomputation(unittest.TestCase):
    def test_recompute_deterministic(self):
        attests = [{"miner_id": "m1", "device_arch": "g4", "epoch": 100}]
        c1 = recompute_commitment(100, "hash100", attests)
        c2 = recompute_commitment(100, "hash100", attests)
        self.assertEqual(c1, c2)

    def test_recompute_different_height(self):
        attests = [{"miner_id": "m1", "device_arch": "g4", "epoch": 100}]
        c1 = recompute_commitment(100, "hash100", attests)
        c2 = recompute_commitment(101, "hash101", attests)
        self.assertNotEqual(c1, c2)

    def test_recompute_empty_attestations(self):
        c = recompute_commitment(100, "hash100", [])
        self.assertEqual(len(c), 64)

    def test_recompute_format(self):
        attests = [{"miner_id": "m1", "device_arch": "g4", "epoch": 100}]
        c = recompute_commitment(100, "hash100", attests)
        int(c, 16)  # Must be valid hex


# ── Output Tests ─────────────────────────────────────────────────

class TestOutput(unittest.TestCase):
    def test_print_results_text(self):
        results = [
            VerificationResult(1, "tx123", 100, "MATCH", "abc", "abc", None, 5),
            VerificationResult(2, "tx456", 101, "MISMATCH", "abc", "def", None, 3, "different"),
        ]
        # Should not raise
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            print_results(results, json_output=False)
        output = f.getvalue()
        self.assertIn("MATCH", output)
        self.assertIn("MISMATCH", output)
        self.assertIn("Summary", output)

    def test_print_results_json(self):
        results = [
            VerificationResult(1, "tx123", 100, "MATCH", "abc", "abc", None, 5),
        ]
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            print_results(results, json_output=True)
        data = json.loads(f.getvalue())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["status"], "MATCH")


if __name__ == "__main__":
    unittest.main()
