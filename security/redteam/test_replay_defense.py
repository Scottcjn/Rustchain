# SPDX-License-Identifier: MIT
"""
Tests for RustChain Hardware Fingerprint Replay Attack & Defense
Bounty #2276: 150 RTC

Tests prove:
1. Replayed fingerprint → REJECTED
2. Fresh fingerprint → ACCEPTED
3. Modified replay (changed nonce but kept old data) → REJECTED
4. Duplicate fingerprint → REJECTED
5. Stale fingerprint → REJECTED
6. SIMD mismatch → REJECTED
"""

import copy
import time
import pytest

from replay_attack_poc import (
    capture_fingerprint,
    replay_fingerprint,
    mutate_replay,
    analyze_current_vulnerability,
)
from replay_defense import (
    NonceStore,
    FingerprintDedup,
    compute_nonce_binding,
    validate_nonce_binding,
    validate_fingerprint_freshness,
    validate_connection_crosscheck,
    validate_attestation,
    NONCE_TTL_SECONDS,
    FRESHNESS_WINDOW,
)


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def nonce_store():
    return NonceStore()


@pytest.fixture
def dedup_store():
    return FingerprintDedup()


@pytest.fixture
def legit_fingerprint():
    """A legitimate fresh fingerprint."""
    fp = capture_fingerprint(miner_id="legit-miner")
    fp["attestation_time"] = time.time()  # Ensure fresh
    return fp


@pytest.fixture
def attacker_replay(legit_fingerprint):
    """An attacker replaying a captured fingerprint."""
    return replay_fingerprint(legit_fingerprint, new_miner_id="attacker")


# ══════════════════════════════════════════════════════════════════
# Attack PoC Tests
# ══════════════════════════════════════════════════════════════════

class TestAttackPoC:
    """Verify that the attack PoC correctly demonstrates the vulnerability."""

    def test_capture_returns_valid_fingerprint(self):
        fp = capture_fingerprint()
        assert fp["architecture"] == "powerpc"
        assert fp["clock_drift"]["valid"] is True
        assert fp["cache_timing"]["valid"] is True
        assert fp["device_age"]["multiplier"] == 2.5

    def test_replay_preserves_hardware_data(self):
        captured = capture_fingerprint()
        replayed = replay_fingerprint(captured)
        assert replayed["miner_id"] != captured["miner_id"]
        assert replayed["clock_drift"] == captured["clock_drift"]
        assert replayed["cache_timing"] == captured["cache_timing"]
        assert replayed["simd_identity"] == captured["simd_identity"]
        assert replayed["thermal_profile"] == captured["thermal_profile"]

    def test_vulnerability_analysis(self):
        vuln = analyze_current_vulnerability()
        assert vuln["severity"] == "HIGH"
        assert len(vuln["missing_checks"]) >= 3


# ══════════════════════════════════════════════════════════════════
# Nonce Store Tests
# ══════════════════════════════════════════════════════════════════

class TestNonceStore:
    def test_issue_and_consume(self, nonce_store):
        nonce = nonce_store.issue()
        assert nonce_store.consume(nonce) is True

    def test_nonce_single_use(self, nonce_store):
        nonce = nonce_store.issue()
        assert nonce_store.consume(nonce) is True
        assert nonce_store.consume(nonce) is False  # Already consumed

    def test_unknown_nonce_rejected(self, nonce_store):
        assert nonce_store.consume("fake-nonce-12345") is False

    def test_expired_nonce_rejected(self, nonce_store):
        nonce = nonce_store.issue()
        # Simulate expiration
        nonce_store._nonces[nonce] = time.time() - NONCE_TTL_SECONDS - 10
        assert nonce_store.consume(nonce) is False


# ══════════════════════════════════════════════════════════════════
# Deduplication Tests
# ══════════════════════════════════════════════════════════════════

class TestDeduplication:
    def test_first_submission_accepted(self, dedup_store, legit_fingerprint):
        is_dup, _ = dedup_store.is_duplicate(legit_fingerprint)
        assert is_dup is False

    def test_duplicate_rejected(self, dedup_store, legit_fingerprint):
        dedup_store.is_duplicate(legit_fingerprint)  # First time
        is_dup, _ = dedup_store.is_duplicate(legit_fingerprint)  # Second time
        assert is_dup is True

    def test_replay_detected_as_duplicate(self, dedup_store, legit_fingerprint, attacker_replay):
        """Replayed data has same hardware hash → detected as duplicate."""
        dedup_store.is_duplicate(legit_fingerprint)
        is_dup, _ = dedup_store.is_duplicate(attacker_replay)
        assert is_dup is True

    def test_different_hardware_not_duplicate(self, dedup_store, legit_fingerprint):
        dedup_store.is_duplicate(legit_fingerprint)
        other = capture_fingerprint(miner_id="other-miner")
        other["clock_drift"]["mean_ns"] = 9999999.9  # Different hardware
        is_dup, _ = dedup_store.is_duplicate(other)
        assert is_dup is False


# ══════════════════════════════════════════════════════════════════
# Freshness Validation Tests
# ══════════════════════════════════════════════════════════════════

class TestFreshness:
    def test_fresh_fingerprint_accepted(self, legit_fingerprint):
        ok, msg = validate_fingerprint_freshness(legit_fingerprint)
        assert ok is True

    def test_stale_fingerprint_rejected(self, legit_fingerprint):
        legit_fingerprint["attestation_time"] = time.time() - FRESHNESS_WINDOW - 60
        ok, msg = validate_fingerprint_freshness(legit_fingerprint)
        assert ok is False
        assert "STALE" in msg

    def test_future_timestamp_rejected(self, legit_fingerprint):
        legit_fingerprint["attestation_time"] = time.time() + 120  # 2 min in future
        ok, msg = validate_fingerprint_freshness(legit_fingerprint)
        assert ok is False
        assert "FUTURE" in msg


# ══════════════════════════════════════════════════════════════════
# Connection Cross-Check Tests
# ══════════════════════════════════════════════════════════════════

class TestConnectionCrosscheck:
    def test_valid_powerpc_accepted(self, legit_fingerprint):
        ok, msg = validate_connection_crosscheck(legit_fingerprint)
        assert ok is True

    def test_powerpc_with_sse_rejected(self, legit_fingerprint):
        legit_fingerprint["simd_identity"]["sse_present"] = True
        ok, msg = validate_connection_crosscheck(legit_fingerprint)
        assert ok is False
        assert "SIMD_MISMATCH" in msg

    def test_x86_with_altivec_rejected(self):
        fp = capture_fingerprint()
        fp["architecture"] = "x86_64"
        fp["simd_identity"]["altivec_present"] = True
        ok, msg = validate_connection_crosscheck(fp)
        assert ok is False

    def test_tls_mismatch_rejected(self, legit_fingerprint):
        ok, msg = validate_connection_crosscheck(
            legit_fingerprint, tls_fingerprint="TLS1.3-AES256-GCM"
        )
        assert ok is False
        assert "TLS_MISMATCH" in msg

    def test_ip_instability_rejected(self, legit_fingerprint):
        # 15 unique IPs is suspicious
        ips = [f"10.0.0.{i}" for i in range(15)]
        ok, msg = validate_connection_crosscheck(
            legit_fingerprint, connection_ip="10.0.0.99", previous_ips=ips
        )
        assert ok is False
        assert "IP_INSTABILITY" in msg


# ══════════════════════════════════════════════════════════════════
# Nonce Binding Tests
# ══════════════════════════════════════════════════════════════════

class TestNonceBinding:
    def test_correct_hmac_accepted(self, legit_fingerprint):
        nonce = "test-nonce-abc123"
        correct_hmac = compute_nonce_binding(nonce, legit_fingerprint)
        ok, msg = validate_nonce_binding(legit_fingerprint, nonce, correct_hmac)
        assert ok is True

    def test_wrong_hmac_rejected(self, legit_fingerprint):
        nonce = "test-nonce-abc123"
        ok, msg = validate_nonce_binding(legit_fingerprint, nonce, "fake-hmac")
        assert ok is False
        assert "MISMATCH" in msg

    def test_different_nonce_rejected(self, legit_fingerprint):
        nonce_a = "nonce-a"
        nonce_b = "nonce-b"
        hmac_a = compute_nonce_binding(nonce_a, legit_fingerprint)
        ok, msg = validate_nonce_binding(legit_fingerprint, nonce_b, hmac_a)
        assert ok is False


# ══════════════════════════════════════════════════════════════════
# Full Pipeline: REQUIRED BOUNTY TESTS
# ══════════════════════════════════════════════════════════════════

class TestFullPipeline:
    """
    Bounty requirement: Tests proving the defense works.
    - Replayed fingerprint → REJECTED
    - Fresh fingerprint → ACCEPTED
    - Modified replay (changed nonce but kept old data) → REJECTED
    """

    def test_fresh_fingerprint_ACCEPTED(self, nonce_store, dedup_store, legit_fingerprint):
        """Fresh, legitimate fingerprint with valid nonce → ACCEPTED."""
        nonce = nonce_store.issue()
        hmac_val = compute_nonce_binding(nonce, legit_fingerprint)

        result = validate_attestation(
            fingerprint=legit_fingerprint,
            nonce=nonce,
            claimed_hmac=hmac_val,
            nonce_store=nonce_store,
            dedup_store=dedup_store,
        )
        assert result.accepted is True, f"Expected ACCEPTED: {result.summary()}"

    def test_replayed_fingerprint_REJECTED(self, nonce_store, dedup_store, legit_fingerprint, attacker_replay):
        """Attacker replays captured fingerprint → REJECTED (nonce invalid)."""
        # Legitimate miner completes attestation first
        nonce1 = nonce_store.issue()
        hmac1 = compute_nonce_binding(nonce1, legit_fingerprint)
        validate_attestation(
            legit_fingerprint, nonce1, hmac1, nonce_store, dedup_store
        )

        # Attacker tries to replay with a new nonce but old data
        nonce2 = nonce_store.issue()
        # Attacker computes HMAC from replayed data — but data is same as legit
        attacker_hmac = compute_nonce_binding(nonce2, attacker_replay)
        result = validate_attestation(
            fingerprint=attacker_replay,
            nonce=nonce2,
            claimed_hmac=attacker_hmac,
            nonce_store=nonce_store,
            dedup_store=dedup_store,
        )
        assert result.accepted is False, f"Expected REJECTED: {result.summary()}"
        # Should fail on deduplication (same hardware data)
        assert result.checks["deduplication"][0] is False

    def test_modified_replay_REJECTED(self, nonce_store, dedup_store, legit_fingerprint):
        """Attacker changes nonce but keeps old fingerprint data → REJECTED."""
        # Get a valid nonce
        nonce = nonce_store.issue()
        # Attacker uses the mutate_replay function (injects nonce but keeps old HW data)
        modified = mutate_replay(legit_fingerprint, server_nonce=nonce)
        # Attacker tries a fake HMAC
        fake_hmac = "0" * 64

        result = validate_attestation(
            fingerprint=modified,
            nonce=nonce,
            claimed_hmac=fake_hmac,
            nonce_store=nonce_store,
            dedup_store=dedup_store,
        )
        assert result.accepted is False, f"Expected REJECTED: {result.summary()}"
        assert result.checks["nonce_binding"][0] is False

    def test_stale_replay_REJECTED(self, nonce_store, dedup_store):
        """Fingerprint from hours ago replayed now → REJECTED on freshness."""
        old_fp = capture_fingerprint()
        old_fp["attestation_time"] = time.time() - 7200  # 2 hours ago

        nonce = nonce_store.issue()
        hmac_val = compute_nonce_binding(nonce, old_fp)
        result = validate_attestation(
            old_fp, nonce, hmac_val, nonce_store, dedup_store
        )
        assert result.accepted is False
        assert result.checks["freshness"][0] is False

    def test_no_nonce_REJECTED(self, nonce_store, dedup_store, legit_fingerprint):
        """Attestation without valid nonce → REJECTED."""
        result = validate_attestation(
            fingerprint=legit_fingerprint,
            nonce="nonexistent-nonce",
            claimed_hmac="whatever",
            nonce_store=nonce_store,
            dedup_store=dedup_store,
        )
        assert result.accepted is False
        assert result.checks["nonce_validity"][0] is False
