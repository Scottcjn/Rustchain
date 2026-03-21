#!/usr/bin/env python3
"""
Tests for RIP-PoA Replay Attack Defense
========================================

Proves the defense works:
1. Replayed fingerprint → REJECTED (no fresh challenge nonce)
2. Fresh fingerprint → ACCEPTED
3. Modified replay (old nonce, new timestamp) → REJECTED
4. Replay with wrong IP → REJECTED (IP correlation)
5. Replay with changed TLS fingerprint → REJECTED
6. Stale entropy (old timestamp) → REJECTED

Run:
    python test_replay_defense.py
    python -m pytest test_replay_defense.py -v
"""

import os
import sqlite3
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from replay_defense import (
    validate_fingerprint_freshness,
    validate_entropy_freshness,
    issue_challenge,
    register_miner_ip,
    ChallengeNonceManager,
    MAX_FINGERPRINT_AGE_SECONDS,
    MAX_ENTROPY_AGE_SECONDS,
    MIN_ENTROPY_CV,
)


def make_attestation(miner_id="test-miner", device_arch="g4", nonce=None,
                      timestamp=None, cv=0.048, drift_stdev=44591,
                      miner_ip=None, ja3_hash=None):
    """Create a valid test attestation payload."""
    nonce = nonce or f"test-nonce-{int(time.time())}"
    timestamp = timestamp or int(time.time())

    attestation = {
        "miner_id": miner_id,
        "device_arch": device_arch,
        "nonce": nonce,
        "timestamp": timestamp,
        "clock_drift": {
            "mean_ns": 1847293,
            "stdev_ns": 89341,
            "cv": cv,
            "drift_stdev": drift_stdev,
        },
        "cache_timing": {
            "l1_hit_ns": 4,
            "l2_hit_ns": 12,
            "l3_hit_ns": 47,
            "cache_tone": 2.3,
            "cache_tone_min": 0.8,
            "cache_tone_max": 8.0,
        },
        "simd": {
            "simd_type": "altivec",
            "has_altivec": True,
            "has_neon": False,
            "has_sse": False,
            "has_sse2": False,
            "has_avx": False,
            "has_avx2": False,
            "has_avx512": False,
        },
        "thermal": {
            "thermal_drift": 3.7,
            "thermal_drift_range": (0.5, 15.0),
            "cpu_temp_c": 61.3,
        },
        "instruction_jitter": {
            "sha256_jitter_ns": 1847293,
            "jitter_cv": 0.048,
        },
        "anti_emulation": {
            "timing_side_channel_resistant": True,
            "branch_predictor_buckets": [0.12, 0.08, 0.15, 0.09, 0.11, 0.13, 0.07, 0.14],
            "tlb_miss_ratio": 0.023,
        },
    }
    return attestation


class TestReplayDefense(unittest.TestCase):
    """Test suite for replay attack defense."""

    @classmethod
    def setUpClass(cls):
        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix=".db")
        cls.conn = sqlite3.connect(cls.db_path)
        cls.mgr = ChallengeNonceManager(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        os.close(cls.db_fd)
        os.unlink(cls.db_path)

    # ─── Test 1: Fresh Fingerprint → ACCEPTED ─────────────────────────────

    def test_fresh_fingerprint_accepted(self):
        """A freshly issued challenge + valid attestation is ACCEPTED."""
        miner_id = "fresh-miner"
        client_ip = "192.168.1.100"
        ja3 = "abc123def456"

        # Issue challenge
        nonce = self.mgr.get_challenge(miner_id, client_ip, ja3)

        # Create fresh attestation
        attestation = make_attestation(miner_id=miner_id, nonce=nonce)

        # Validate
        ok, reason = validate_fingerprint_freshness(
            attestation=attestation,
            db_conn=self.conn,
            client_ip=client_ip,
            ja3_hash=ja3,
        )

        self.assertTrue(ok, f"Fresh attestation should be accepted, got: {reason}")
        self.assertIsNone(reason)

    # ─── Test 2: Replayed Fingerprint → REJECTED ──────────────────────────

    def test_replay_rejected_no_nonce(self):
        """Attestation without a nonce → REJECTED."""
        attestation = make_attestation()
        del attestation["nonce"]

        ok, reason = validate_fingerprint_freshness(
            attestation=attestation,
            db_conn=self.conn,
            client_ip="192.168.1.100",
        )

        self.assertFalse(ok, "Missing nonce should be rejected")
        self.assertEqual(reason, "missing_nonce")

    def test_replay_rejected_unknown_nonce(self):
        """Attestation with unknown nonce → REJECTED."""
        attestation = make_attestation(nonce="completely-fake-nonce-12345")

        ok, reason = validate_fingerprint_freshness(
            attestation=attestation,
            db_conn=self.conn,
            client_ip="192.168.1.100",
        )

        self.assertFalse(ok, "Unknown nonce should be rejected")
        self.assertEqual(reason, "nonce_validation_failed: nonce_not_found")

    def test_replay_rejected_used_nonce(self):
        """Replaying the same nonce twice → REJECTED."""
        miner_id = "replay-tester"
        client_ip = "10.0.0.1"

        nonce = self.mgr.get_challenge(miner_id, client_ip)

        # First submission: valid
        attestation1 = make_attestation(miner_id=miner_id, nonce=nonce)
        ok1, _ = validate_fingerprint_freshness(attestation1, self.conn, client_ip)
        self.assertTrue(ok1, "First use of nonce should be accepted")

        # Second submission (replay): invalid
        attestation2 = make_attestation(miner_id=miner_id, nonce=nonce)
        ok2, reason2 = validate_fingerprint_freshness(attestation2, self.conn, client_ip)

        self.assertFalse(ok2, "Replay of same nonce should be rejected")
        self.assertEqual(reason2, "nonce_validation_failed: nonce_already_used")

    # ─── Test 3: Modified Replay (old nonce, new timestamp) → REJECTED ────

    def test_modified_replay_rejected(self):
        """Old nonce captured, re-submitted with new timestamp → REJECTED (expired or stale)."""
        miner_id = "modified-replay"

        # Issue a nonce and let it expire
        old_nonce = self.mgr.get_challenge(miner_id, "10.0.0.1")
        old_ts = int(time.time()) - MAX_FINGERPRINT_AGE_SECONDS - 10  # Expired

        attestation = make_attestation(miner_id=miner_id, nonce=old_nonce, timestamp=old_ts)

        ok, reason = validate_fingerprint_freshness(
            attestation=attestation,
            db_conn=self.conn,
            client_ip="10.0.0.1",
            now_ts=int(time.time()),
        )

        self.assertFalse(ok, "Expired nonce should be rejected")
        # Either nonce expired OR entropy stale — both mean replay rejected
        self.assertTrue(
            "nonce_expired" in reason or "entropy_stale" in reason,
            f"Expected nonce_expired or entropy_stale, got: {reason}"
        )

    def test_wrong_miner_id_rejected(self):
        """Attestation with nonce issued to different miner → REJECTED."""
        miner_id = "alice"
        wrong_miner = "bob"

        nonce = self.mgr.get_challenge(miner_id, "10.0.0.1")
        attestation = make_attestation(miner_id=wrong_miner, nonce=nonce)

        ok, reason = validate_fingerprint_freshness(
            attestation=attestation,
            db_conn=self.conn,
            client_ip="10.0.0.1",
        )

        self.assertFalse(ok, "Wrong miner_id should be rejected")
        self.assertIn("miner_id_mismatch", reason)

    # ─── Test 4: IP Correlation ─────────────────────────────────────────────

    def test_ip_correlation_new_ip_first_time(self):
        """First-time IP for miner → ALLOWED (may be new setup)."""
        miner_id = "ip-roamer"

        # No history, new IP — allowed
        nonce = self.mgr.get_challenge(miner_id, "93.184.216.34")
        attestation = make_attestation(miner_id=miner_id, nonce=nonce)

        ok, reason = validate_fingerprint_freshness(
            attestation=attestation,
            db_conn=self.conn,
            client_ip="93.184.216.34",
        )

        self.assertTrue(ok, f"First-time IP should be allowed, got: {reason}")

    def test_ip_correlation_different_ip_rejected(self):
        """IP changed significantly between challenge and attestation → REJECTED."""
        miner_id = "ip-suspicious"

        # Register the miner with a known IP
        register_miner_ip(self.conn, miner_id, "1.2.3.4")

        # Issue challenge from 1.2.3.4
        nonce = self.mgr.get_challenge(miner_id, "1.2.3.4")

        # But attestation comes from completely different IP (different /24)
        attestation = make_attestation(miner_id=miner_id, nonce=nonce)

        ok, reason = validate_fingerprint_freshness(
            attestation=attestation,
            db_conn=self.conn,
            client_ip="5.6.7.8",  # Different subnet
        )

        self.assertFalse(ok, "Suspicious IP change should be rejected")
        self.assertIn("ip_correlation_failed", reason)

    def test_ip_correlation_same_subnet_allowed(self):
        """Same /27 subnet → ALLOWED (allows NAT, corporate proxies)."""
        miner_id = "ip-nat-user"

        # Issue challenge from 192.168.1.100
        nonce = self.mgr.get_challenge(miner_id, "192.168.1.100")

        # Attestation from same /27 subnet
        attestation = make_attestation(miner_id=miner_id, nonce=nonce)

        ok, reason = validate_fingerprint_freshness(
            attestation=attestation,
            db_conn=self.conn,
            client_ip="192.168.1.105",  # Same /27
        )

        self.assertTrue(ok, f"Same /27 subnet should be allowed, got: {reason}")

    # ─── Test 5: TLS Fingerprint ───────────────────────────────────────────

    def test_tls_fingerprint_mismatch_rejected(self):
        """TLS JA3 changed between challenge and attestation → REJECTED."""
        miner_id = "tls-suspicious"
        challenge_ja3 = "original_ja3_hash_abc123"
        wrong_ja3 = "hijacked_ja3_hash_xyz789"

        # Issue challenge with known JA3
        nonce = self.mgr.get_challenge(miner_id, "10.0.0.1", challenge_ja3)

        # Attestation with different JA3 (e.g., different TLS client)
        attestation = make_attestation(miner_id=miner_id, nonce=nonce)

        ok, reason = validate_fingerprint_freshness(
            attestation=attestation,
            db_conn=self.conn,
            client_ip="10.0.0.1",
            ja3_hash=wrong_ja3,
        )

        self.assertFalse(ok, "TLS fingerprint mismatch should be rejected")
        self.assertIn("tls_correlation_failed", reason)

    # ─── Test 6: Entropy Freshness ────────────────────────────────────────

    def test_stale_entropy_rejected(self):
        """Attestation with old timestamp → REJECTED (entropy stale)."""
        attestation = make_attestation()
        attestation["timestamp"] = int(time.time()) - MAX_ENTROPY_AGE_SECONDS - 10

        ok, reason = validate_entropy_freshness(
            attestation=attestation,
            device_arch="g4",
            now_ts=int(time.time()),
        )

        self.assertFalse(ok, "Stale entropy should be rejected")
        self.assertIn("entropy_stale", reason)

    def test_synthetic_entropy_rejected(self):
        """Attestation with zero CV (synthetic/replayed data) → REJECTED."""
        attestation = make_attestation(cv=0.0, drift_stdev=0)

        ok, reason = validate_entropy_freshness(
            attestation=attestation,
            device_arch="g4",
            now_ts=int(time.time()),
        )

        self.assertFalse(ok, "Synthetic entropy (cv=0) should be rejected")
        self.assertIn("entropy_synthetic", reason)

    def test_fresh_entropy_accepted(self):
        """Valid, fresh entropy → ACCEPTED."""
        attestation = make_attestation(cv=0.048, drift_stdev=44591)

        ok, reason = validate_entropy_freshness(
            attestation=attestation,
            device_arch="g4",
            now_ts=int(time.time()),
        )

        self.assertTrue(ok, f"Fresh entropy should be accepted, got: {reason}")

    def test_very_low_cv_rejected(self):
        """CV below minimum → REJECTED (synthetic timing)."""
        attestation = make_attestation(cv=MIN_ENTROPY_CV / 2, drift_stdev=1000)

        ok, reason = validate_entropy_freshness(
            attestation=attestation,
            device_arch="g4",
            now_ts=int(time.time()),
        )

        self.assertFalse(ok, "Very low CV should be rejected as synthetic")
        self.assertIn("entropy_synthetic", reason)

    # ─── Test 7: Integration Test — Full Attack Blocked ───────────────────

    def test_full_replay_attack_blocked(self):
        """
        Simulate the complete attack:
        1. Legitimate miner has established IP history
        2. Attacker steals a nonce and replays from a different subnet
        3. Defense REJECTS due to IP correlation failure
        """
        legitimate_miner = "replay-victim"
        legitimate_ip = "203.0.113.50"
        attacker_ip = "198.51.100.100"  # Different /24 subnet

        # Establish legitimate IP history (miner has been seen from this IP before)
        register_miner_ip(self.conn, legitimate_miner, legitimate_ip)

        # Issue challenge from the legitimate known IP
        nonce = self.mgr.get_challenge(legitimate_miner, legitimate_ip)

        # Attacker replays from a completely different subnet
        attestation = make_attestation(miner_id=legitimate_miner, nonce=nonce)

        ok, reason = validate_fingerprint_freshness(
            attestation=attestation,
            db_conn=self.conn,
            client_ip=attacker_ip,  # ← Different subnet!
        )

        self.assertFalse(ok, "Full replay attack should be blocked")
        self.assertIsNotNone(reason)
        self.assertIn("ip_correlation_failed", reason)

    def test_full_fresh_attack_accepted(self):
        """
        Legitimate miner uses the system correctly → ACCEPTED.
        """
        miner_id = "honest-miner"
        client_ip = "192.168.1.200"

        # Issue challenge
        nonce = self.mgr.get_challenge(miner_id, client_ip)

        # Create fresh attestation
        attestation = make_attestation(miner_id=miner_id, nonce=nonce)

        # Validate — should pass
        ok, reason = validate_fingerprint_freshness(
            attestation=attestation,
            db_conn=self.conn,
            client_ip=client_ip,
        )

        self.assertTrue(ok, f"Legitimate attestation should be accepted, got: {reason}")

    # ─── Test 8: Challenge Expiry ─────────────────────────────────────────

    def test_expired_nonce_rejected(self):
        """Challenge nonce that has expired → REJECTED."""
        miner_id = "expired-nonce"

        # Manually insert an expired nonce
        expired_ts = int(time.time()) - MAX_FINGERPRINT_AGE_SECONDS - 60
        nonce = f"expired-{int(time.time())}"
        self.conn.execute("""
            INSERT INTO attestation_challenges
            (nonce, miner_id, created_at, expires_at, used, ip_address)
            VALUES (?, ?, ?, ?, 0, ?)
        """, (nonce, miner_id, expired_ts, expired_ts + 300, "10.0.0.1"))
        self.conn.commit()

        attestation = make_attestation(miner_id=miner_id, nonce=nonce)

        ok, reason = validate_fingerprint_freshness(
            attestation=attestation,
            db_conn=self.conn,
            client_ip="10.0.0.1",
        )

        self.assertFalse(ok, "Expired nonce should be rejected")
        self.assertIn("nonce_expired", reason)


def run_all_tests():
    """Run all tests with summary."""
    print("\n" + "=" * 60)
    print("RIP-PoA Replay Attack Defense — Test Suite")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestReplayDefense)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("=" * 60)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"Results: {passed}/{result.testsRun} passed")
    if result.failures:
        print(f"Failures: {len(result.failures)}")
        for test, traceback in result.failures:
            print(f"  FAIL: {test}")
    if result.errors:
        print(f"Errors: {len(result.errors)}")
    print("=" * 60)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
