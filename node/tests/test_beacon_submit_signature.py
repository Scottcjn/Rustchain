#!/usr/bin/env python3
"""
Integration tests for /beacon/submit endpoint signature verification (Issue #2306).

Tests verify that the beacon submit endpoint properly validates envelope signatures
before anchoring, rejecting forged or tampered payloads.
"""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nacl.signing import SigningKey


# Import beacon_anchor module
MODULE_PATH = Path(__file__).resolve().parents[1] / "beacon_anchor.py"
SPEC = importlib.util.spec_from_file_location("beacon_anchor", MODULE_PATH)
beacon_anchor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(beacon_anchor)


def _make_temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


def _build_valid_envelope(agent_id: str = None, kind: str = "heartbeat", 
                          payload: dict = None, signing_key: SigningKey = None):
    """Build a properly signed beacon envelope."""
    if signing_key is None:
        signing_key = SigningKey.generate()
    
    pubkey_bytes = bytes(signing_key.verify_key)
    derived_agent_id = beacon_anchor._agent_id_from_pubkey(pubkey_bytes)
    
    envelope = {
        "agent_id": agent_id or derived_agent_id,
        "kind": kind,
        "nonce": f"nonce-{os.urandom(8).hex()}",
        "pubkey": pubkey_bytes.hex(),
        "payload": payload or {"status": "alive", "ts": 1234567890},
    }
    
    message = beacon_anchor._canonical_signing_payload(envelope)
    envelope["sig"] = signing_key.sign(message).signature.hex()
    
    return envelope, signing_key


class TestBeaconSubmitSignatureVerification(unittest.TestCase):
    """Test suite for issue #2306: /beacon/submit must verify envelope signatures."""
    
    def test_rejects_envelope_with_forged_signature(self):
        """Forged signatures must be rejected before anchoring."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope()
            
            # Forge a random signature (not signed by the private key)
            envelope["sig"] = os.urandom(64).hex()
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertEqual(result["ok"], False)
            self.assertEqual(result["error"], "invalid_signature")
            
            # Verify envelope was NOT stored
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            os.unlink(db_path)
    
    def test_rejects_envelope_with_tampered_payload(self):
        """Tampered payloads (signature doesn't match content) must be rejected."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope()
            
            # Tamper with the payload after signing
            envelope["payload"]["status"] = "compromised"
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertEqual(result["ok"], False)
            self.assertEqual(result["error"], "invalid_signature")
            
            # Verify envelope was NOT stored
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            os.unlink(db_path)
    
    def test_rejects_envelope_with_agent_id_pubkey_mismatch(self):
        """Agent ID must match the public key to prevent identity spoofing."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope()
            
            # Use a different agent_id than what the pubkey derives to
            envelope["agent_id"] = "bcn_deadbeefcafe"
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertEqual(result["ok"], False)
            self.assertEqual(result["error"], "agent_id_pubkey_mismatch")
            
            # Verify envelope was NOT stored
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            os.unlink(db_path)
    
    def test_rejects_envelope_with_empty_signature(self):
        """Empty signatures must be rejected."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope()
            envelope["sig"] = ""
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertEqual(result["ok"], False)
            self.assertIn("missing", result["error"])
            
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            os.unlink(db_path)
    
    def test_rejects_envelope_with_empty_pubkey(self):
        """Empty public keys must be rejected."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope()
            envelope["pubkey"] = ""
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertEqual(result["ok"], False)
            self.assertIn("missing", result["error"])
            
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            os.unlink(db_path)
    
    def test_rejects_envelope_with_invalid_hex_pubkey(self):
        """Non-hex public keys must be rejected."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope()
            envelope["pubkey"] = "not-a-hex-string!!!"
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertEqual(result["ok"], False)
            self.assertEqual(result["error"], "invalid_signature_or_pubkey_encoding")
            
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            os.unlink(db_path)
    
    def test_rejects_envelope_with_invalid_hex_signature(self):
        """Non-hex signatures must be rejected."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope()
            envelope["sig"] = "not-a-hex-signature!!!"
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertEqual(result["ok"], False)
            self.assertEqual(result["error"], "invalid_signature_or_pubkey_encoding")
            
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            os.unlink(db_path)
    
    def test_rejects_envelope_with_wrong_kind(self):
        """Invalid envelope kinds must be rejected."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope(kind="invalid_kind")
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertEqual(result["ok"], False)
            self.assertIn("invalid_kind", result["error"])
            
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            os.unlink(db_path)
    
    def test_rejects_envelope_with_missing_fields(self):
        """Envelopes with missing required fields must be rejected."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope()
            del envelope["agent_id"]
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertEqual(result["ok"], False)
            self.assertEqual(result["error"], "missing_fields")
            
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            os.unlink(db_path)


class TestBeaconSubmitValidPayloads(unittest.TestCase):
    """Regression tests: valid payloads must be accepted and anchored."""
    
    def test_accepts_valid_heartbeat_envelope(self):
        """Valid heartbeat envelopes must be accepted."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, signing_key = _build_valid_envelope(kind="heartbeat")
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertTrue(result["ok"])
            self.assertIn("id", result)
            self.assertIn("payload_hash", result)
            
            # Verify envelope was stored
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT agent_id, kind, nonce, sig FROM beacon_envelopes WHERE id = ?",
                    (result["id"],)
                ).fetchone()
            self.assertEqual(row[0], envelope["agent_id"])
            self.assertEqual(row[1], "heartbeat")
            self.assertEqual(row[2], envelope["nonce"])
            self.assertEqual(row[3], envelope["sig"])
        finally:
            os.unlink(db_path)
    
    def test_accepts_valid_hello_envelope(self):
        """Valid hello envelopes must be accepted."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope(kind="hello", payload={"greeting": "hello"})
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertTrue(result["ok"])
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 1)
        finally:
            os.unlink(db_path)
    
    def test_accepts_valid_want_envelope(self):
        """Valid want envelopes must be accepted."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope(
                kind="want", 
                payload={"request": "compute_task", "budget": 100}
            )
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertTrue(result["ok"])
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 1)
        finally:
            os.unlink(db_path)
    
    def test_accepts_valid_bounty_envelope(self):
        """Valid bounty envelopes must be accepted."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope(
                kind="bounty",
                payload={"issue": "#123", "reward": "50 RTC"}
            )
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertTrue(result["ok"])
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 1)
        finally:
            os.unlink(db_path)
    
    def test_accepts_valid_mayday_envelope(self):
        """Valid mayday (emergency) envelopes must be accepted."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope(
                kind="mayday",
                payload={"emergency": "system_failure"}
            )
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertTrue(result["ok"])
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 1)
        finally:
            os.unlink(db_path)
    
    def test_accepts_valid_accord_envelope(self):
        """Valid accord (agreement) envelopes must be accepted."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope(
                kind="accord",
                payload={"contract_id": "ctr_001", "terms": "accepted"}
            )
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertTrue(result["ok"])
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 1)
        finally:
            os.unlink(db_path)
    
    def test_accepts_valid_pushback_envelope(self):
        """Valid pushback (dispute) envelopes must be accepted."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope(
                kind="pushback",
                payload={"dispute": "contract_ctr_001", "reason": "terms_violation"}
            )
            
            result = beacon_anchor.store_envelope(envelope, db_path)
            
            self.assertTrue(result["ok"])
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 1)
        finally:
            os.unlink(db_path)
    
    def test_valid_envelope_affects_digest(self):
        """Valid envelopes must affect the beacon digest."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope()
            
            # Get initial digest (should be empty)
            initial_digest = beacon_anchor.compute_beacon_digest(db_path)
            self.assertEqual(initial_digest["count"], 0)
            self.assertIsNone(initial_digest["digest"])
            
            # Store valid envelope
            result = beacon_anchor.store_envelope(envelope, db_path)
            self.assertTrue(result["ok"])
            
            # Get new digest (should include the envelope)
            new_digest = beacon_anchor.compute_beacon_digest(db_path)
            self.assertEqual(new_digest["count"], 1)
            self.assertIsNotNone(new_digest["digest"])
            self.assertIn(result["id"], new_digest["ids"])
        finally:
            os.unlink(db_path)
    
    def test_multiple_valid_envelopes_from_different_agents(self):
        """Multiple valid envelopes from different agents must all be accepted."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            
            # Create envelopes from 3 different agents
            envelopes = []
            for i in range(3):
                env, _ = _build_valid_envelope(
                    kind="heartbeat",
                    payload={"agent_num": i}
                )
                envelopes.append(env)
            
            # Store all envelopes
            results = []
            for env in envelopes:
                result = beacon_anchor.store_envelope(env, db_path)
                results.append(result)
                self.assertTrue(result["ok"], f"Failed to store envelope {env['nonce']}")
            
            # Verify all stored
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 3)
            
            # Verify digest includes all
            digest = beacon_anchor.compute_beacon_digest(db_path)
            self.assertEqual(digest["count"], 3)
        finally:
            os.unlink(db_path)
    
    def test_duplicate_nonce_rejected(self):
        """Duplicate nonces must be rejected (replay attack prevention)."""
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_valid_envelope()
            
            # First submission should succeed
            result1 = beacon_anchor.store_envelope(envelope, db_path)
            self.assertTrue(result1["ok"])
            
            # Second submission with same nonce should fail
            result2 = beacon_anchor.store_envelope(envelope, db_path)
            self.assertEqual(result2["ok"], False)
            self.assertEqual(result2["error"], "duplicate_nonce")
            
            # Only one envelope should be stored
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 1)
        finally:
            os.unlink(db_path)


class TestSignatureVerificationLogic(unittest.TestCase):
    """Unit tests for signature verification helper functions."""
    
    def test_agent_id_derivation_is_deterministic(self):
        """Agent ID derivation from pubkey must be deterministic."""
        signing_key = SigningKey.generate()
        pubkey_bytes = bytes(signing_key.verify_key)
        
        agent_id1 = beacon_anchor._agent_id_from_pubkey(pubkey_bytes)
        agent_id2 = beacon_anchor._agent_id_from_pubkey(pubkey_bytes)
        
        self.assertEqual(agent_id1, agent_id2)
        self.assertTrue(agent_id1.startswith("bcn_"))
    
    def test_different_pubkeys_yield_different_agent_ids(self):
        """Different pubkeys must yield different agent IDs."""
        key1 = SigningKey.generate()
        key2 = SigningKey.generate()
        
        agent_id1 = beacon_anchor._agent_id_from_pubkey(bytes(key1.verify_key))
        agent_id2 = beacon_anchor._agent_id_from_pubkey(bytes(key2.verify_key))
        
        self.assertNotEqual(agent_id1, agent_id2)
    
    def test_canonical_signing_payload_excludes_sig(self):
        """Canonical signing payload must exclude the sig field."""
        envelope = {
            "agent_id": "bcn_test",
            "kind": "heartbeat",
            "nonce": "nonce123",
            "pubkey": "abcd",
            "sig": "signature_here",
            "payload": {"data": "test"}
        }
        
        payload = beacon_anchor._canonical_signing_payload(envelope)
        payload_str = payload.decode("utf-8")
        
        self.assertNotIn('"sig"', payload_str)
        self.assertIn('"agent_id"', payload_str)
        self.assertIn('"kind"', payload_str)
    
    def test_canonical_signing_payload_excludes_beacon_version(self):
        """Canonical signing payload must exclude _beacon_version field."""
        envelope = {
            "agent_id": "bcn_test",
            "kind": "heartbeat",
            "nonce": "nonce123",
            "pubkey": "abcd",
            "_beacon_version": "2.0",
        }
        
        payload = beacon_anchor._canonical_signing_payload(envelope)
        payload_str = payload.decode("utf-8")
        
        self.assertNotIn('_beacon_version', payload_str)
    
    def test_canonical_signing_payload_is_deterministic(self):
        """Canonical signing payload must be deterministic (sorted keys)."""
        envelope1 = {
            "kind": "heartbeat",
            "agent_id": "bcn_test",
            "nonce": "nonce123",
            "pubkey": "abcd",
        }
        envelope2 = {
            "agent_id": "bcn_test",
            "kind": "heartbeat",
            "pubkey": "abcd",
            "nonce": "nonce123",
        }
        
        payload1 = beacon_anchor._canonical_signing_payload(envelope1)
        payload2 = beacon_anchor._canonical_signing_payload(envelope2)
        
        self.assertEqual(payload1, payload2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
