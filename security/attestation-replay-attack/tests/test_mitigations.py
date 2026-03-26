#!/usr/bin/env python3
"""
Tests for Cross-Node Attestation Replay Attack Mitigations

Run: python -m pytest security/attestation-replay-attack/tests/test_mitigations.py -v
"""

import hashlib
import json
import os
import sqlite3
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "patches"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from patch_cross_node_registry import (
    check_cross_node_attestation,
    record_attestation,
    cleanup_old_attestations,
    _sign_gossip,
    SHARED_ATTESTATION_SCHEMA,
)
from patch_nonce_federation import (
    generate_federated_nonce,
    validate_nonce_origin,
    hash_used_nonce,
)
from poc_ip_evasion import compute_hardware_id


# ── Cross-Node Registry Tests ────────────────────────────────────

class TestCrossNodeRegistry(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        for stmt in SHARED_ATTESTATION_SCHEMA.strip().split(";"):
            if stmt.strip():
                self.conn.execute(stmt)

    def tearDown(self):
        self.conn.close()

    def test_first_attestation_allowed(self):
        ok, reason = check_cross_node_attestation(
            self.conn, "hw_abc", "miner1", 100, "node1"
        )
        self.assertTrue(ok)

    def test_same_node_allowed(self):
        record_attestation(self.conn, "hw_abc", "miner1", 100, "node1")
        ok, reason = check_cross_node_attestation(
            self.conn, "hw_abc", "miner1", 100, "node1"
        )
        self.assertTrue(ok)  # Same node, no conflict

    def test_cross_node_blocked(self):
        record_attestation(self.conn, "hw_abc", "miner1", 100, "node1")
        ok, reason = check_cross_node_attestation(
            self.conn, "hw_abc", "miner1", 100, "node2"
        )
        self.assertFalse(ok)
        self.assertIn("node1", reason)

    def test_different_epoch_allowed(self):
        record_attestation(self.conn, "hw_abc", "miner1", 100, "node1")
        ok, reason = check_cross_node_attestation(
            self.conn, "hw_abc", "miner1", 101, "node2"
        )
        self.assertTrue(ok)

    def test_different_hardware_allowed(self):
        record_attestation(self.conn, "hw_abc", "miner1", 100, "node1")
        ok, reason = check_cross_node_attestation(
            self.conn, "hw_xyz", "miner2", 100, "node2"
        )
        self.assertTrue(ok)

    def test_record_attestation(self):
        result = record_attestation(self.conn, "hw1", "m1", 50, "node1")
        self.assertTrue(result)
        row = self.conn.execute(
            "SELECT * FROM shared_attestations WHERE hardware_id='hw1'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_duplicate_record_ignored(self):
        record_attestation(self.conn, "hw1", "m1", 50, "node1")
        record_attestation(self.conn, "hw1", "m1", 50, "node1")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM shared_attestations WHERE hardware_id='hw1'"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_cleanup_old(self):
        self.conn.execute(
            "INSERT INTO shared_attestations (hardware_id, miner_id, epoch, node_id, received_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("old_hw", "m1", 1, "node1", int(time.time()) - 100000)
        )
        self.conn.commit()
        cleanup_old_attestations(self.conn, max_age_seconds=1000)
        row = self.conn.execute(
            "SELECT * FROM shared_attestations WHERE hardware_id='old_hw'"
        ).fetchone()
        self.assertIsNone(row)


# ── Gossip Signature Tests ───────────────────────────────────────

class TestGossipSignature(unittest.TestCase):
    def test_signature_deterministic(self):
        sig1 = _sign_gossip("hw1", 100, "node1")
        sig2 = _sign_gossip("hw1", 100, "node1")
        self.assertEqual(sig1, sig2)

    def test_signature_changes_with_input(self):
        sig1 = _sign_gossip("hw1", 100, "node1")
        sig2 = _sign_gossip("hw2", 100, "node1")
        self.assertNotEqual(sig1, sig2)

    def test_signature_format(self):
        sig = _sign_gossip("hw1", 100, "node1")
        self.assertEqual(len(sig), 32)
        int(sig, 16)  # Must be valid hex


# ── Nonce Federation Tests ───────────────────────────────────────

class TestNonceFederation(unittest.TestCase):
    def test_generate_nonce(self):
        nonce, expires = generate_federated_nonce("node1")
        self.assertTrue(nonce.startswith("n"))
        self.assertIn("_", nonce)
        self.assertGreater(expires, int(time.time()))

    def test_nonce_contains_node_prefix(self):
        nonce, _ = generate_federated_nonce("node1")
        prefix = hashlib.sha256("node1".encode()).hexdigest()[:8]
        self.assertTrue(nonce.startswith(f"n{prefix}"))

    def test_nonce_unique(self):
        n1, _ = generate_federated_nonce("node1")
        n2, _ = generate_federated_nonce("node1")
        self.assertNotEqual(n1, n2)

    def test_validate_own_nonce(self):
        nonce, _ = generate_federated_nonce("node1")
        ok, reason = validate_nonce_origin(nonce, "node1")
        self.assertTrue(ok)
        self.assertEqual(reason, "valid_federated")

    def test_reject_other_node_nonce(self):
        nonce, _ = generate_federated_nonce("node1")
        ok, reason = validate_nonce_origin(nonce, "node2")
        self.assertFalse(ok)
        self.assertEqual(reason, "wrong_node_nonce")

    def test_legacy_nonce_allowed(self):
        legacy = "a" * 64
        ok, reason = validate_nonce_origin(legacy, "node1")
        self.assertTrue(ok)
        self.assertEqual(reason, "legacy_nonce")

    def test_empty_nonce_rejected(self):
        ok, reason = validate_nonce_origin("", "node1")
        self.assertFalse(ok)

    def test_invalid_format_rejected(self):
        ok, reason = validate_nonce_origin("not-a-nonce", "node1")
        self.assertFalse(ok)

    def test_nonce_hash(self):
        nonce, _ = generate_federated_nonce("node1")
        h = hash_used_nonce(nonce)
        self.assertEqual(len(h), 32)
        # Hash should not leak original nonce
        self.assertNotIn(nonce[:10], h)


# ── IP Evasion Tests ─────────────────────────────────────────────

class TestIPEvasion(unittest.TestCase):
    DEVICE = {
        "device_arch": "g4", "device_family": "PowerBook",
        "device_model": "PowerBook5,8", "cores": 1,
        "cpu_serial": "XB435T"
    }
    SIGNALS = {"macs": ["00:11:22:33:44:55"]}

    def test_same_ip_same_id(self):
        id1 = compute_hardware_id(self.DEVICE, self.SIGNALS, "1.2.3.4")
        id2 = compute_hardware_id(self.DEVICE, self.SIGNALS, "1.2.3.4")
        self.assertEqual(id1, id2)

    def test_different_ip_different_id(self):
        """This is the vulnerability: VPN changes hardware identity."""
        id1 = compute_hardware_id(self.DEVICE, self.SIGNALS, "1.2.3.4")
        id2 = compute_hardware_id(self.DEVICE, self.SIGNALS, "5.6.7.8")
        self.assertNotEqual(id1, id2)

    def test_no_ip_deterministic(self):
        id1 = compute_hardware_id(self.DEVICE, self.SIGNALS, None)
        id2 = compute_hardware_id(self.DEVICE, self.SIGNALS, None)
        self.assertEqual(id1, id2)

    def test_fix_removes_ip_dependency(self):
        """Without IP, same hardware = same ID regardless of network."""
        id1 = compute_hardware_id(self.DEVICE, self.SIGNALS, None)
        id2 = compute_hardware_id(self.DEVICE, self.SIGNALS, None)
        self.assertEqual(id1, id2)


if __name__ == "__main__":
    unittest.main()
