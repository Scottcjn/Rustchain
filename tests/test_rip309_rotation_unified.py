# SPDX-License-Identifier: MIT
"""Fix B: the RIP-309 rotation must pick the SAME 4-of-6 subset on every path.

Before this fix the enroll side (integrated node select_active_fingerprint_checks)
used sha256("rip-309:" + hash) with a sorted-per-name-hash ranking over a tuple
containing "simd_bias", while settlement (finalize_epoch) and the reward path
(rip_309_measurement_rotation.get_reward_active_fingerprint_checks, golden-tested)
used sha256(hash_bytes + b"measurement_nonce") with random.Random(seed).sample
over names containing "simd_identity". For the same epoch the two sides picked
different subsets: weight was granted against one set and vetoed against another.

All selectors now delegate to rip_309_measurement_rotation.
"""
import hashlib
import random
import sys

import pytest

integrated_node = sys.modules["integrated_node"]
rr_mod = sys.modules["rr_mod"]

from rip_309_measurement_rotation import (
    ALL_FP_CHECKS,
    derive_reward_measurement_nonce,
    get_reward_active_fingerprint_checks,
)

SAMPLE_HASHES = [
    hashlib.sha256(f"block_{i}".encode()).hexdigest() for i in range(25)
]


def test_enroll_selector_matches_reward_selector():
    for h in SAMPLE_HASHES:
        enroll = set(integrated_node.select_active_fingerprint_checks(h))
        reward = set(get_reward_active_fingerprint_checks(bytes.fromhex(h)))
        assert enroll == reward, f"divergent subsets for hash {h}"


def test_roundrobin_duplicate_selector_matches_reward_selector():
    for h in SAMPLE_HASHES:
        rr = set(rr_mod.select_active_fingerprint_checks(h))
        reward = set(get_reward_active_fingerprint_checks(bytes.fromhex(h)))
        assert rr == reward


def test_enroll_selector_matches_old_finalize_epoch_inline_algorithm():
    """finalize_epoch used to inline this exact algorithm; the delegation must
    preserve it bit-for-bit (settlement behavior unchanged)."""
    for h in SAMPLE_HASHES:
        prev_bytes = bytes.fromhex(h)
        nonce = hashlib.sha256(prev_bytes + b"measurement_nonce").digest()
        seed = int.from_bytes(nonce[:4], "big")
        inline = set(random.Random(seed).sample(list(ALL_FP_CHECKS), 4))
        assert set(integrated_node.select_active_fingerprint_checks(h)) == inline


def test_canonical_names_use_simd_identity_not_simd_bias():
    assert "simd_identity" in integrated_node.RIP309_ROTATING_FINGERPRINT_CHECKS
    assert "simd_bias" not in integrated_node.RIP309_ROTATING_FINGERPRINT_CHECKS
    assert "simd_identity" in rr_mod.ROTATING_FINGERPRINT_CHECKS
    assert "simd_bias" not in rr_mod.ROTATING_FINGERPRINT_CHECKS
    assert tuple(integrated_node.RIP309_ROTATING_FINGERPRINT_CHECKS) == tuple(ALL_FP_CHECKS)


def test_fail_closed_preserved_on_unavailable_hash():
    """T3.6: empty / all-zeros / non-hex hashes must still activate ALL checks."""
    for bad in ("", "   ", None, "0" * 64, "not-hex-at-all", "zz" * 32):
        active = integrated_node.select_active_fingerprint_checks(bad)
        assert set(active) == set(ALL_FP_CHECKS), f"{bad!r} must fail closed"
        assert len(active) == 6
        rr_active = rr_mod.select_active_fingerprint_checks(bad if bad != "not-hex-at-all" else bad)
        assert set(rr_active) == set(ALL_FP_CHECKS)


def test_real_hash_selects_four_deterministically():
    h = "a" * 64
    active = integrated_node.select_active_fingerprint_checks(h)
    assert len(active) == 4
    assert active == integrated_node.select_active_fingerprint_checks(h)


def test_non_canonical_active_count_raises():
    with pytest.raises(ValueError):
        integrated_node.select_active_fingerprint_checks("a" * 64, active_count=3)
    with pytest.raises(ValueError):
        rr_mod.select_active_fingerprint_checks("a" * 64, active_count=5)


def test_measurement_nonce_is_canonical():
    for h in SAMPLE_HASHES:
        expected = derive_reward_measurement_nonce(bytes.fromhex(h)).hex()
        assert integrated_node.derive_measurement_nonce(h) == expected
        assert rr_mod.derive_measurement_nonce(h) == expected


def test_old_and_new_enroll_algorithms_actually_disagreed():
    """Regression documentation: prove the pre-fix enroll algorithm picked a
    DIFFERENT subset than settlement for at least one real-looking hash, i.e.
    the bug was real and this fix changes the enroll-side subset."""
    old_tuple = ("clock_drift", "cache_timing", "simd_bias",
                 "thermal_drift", "instruction_jitter", "anti_emulation")

    def old_enroll_select(h):
        nonce = hashlib.sha256(f"rip-309:{h}".encode()).hexdigest()
        ranked = sorted(
            old_tuple,
            key=lambda name: hashlib.sha256(f"{nonce}:{name}".encode()).hexdigest(),
        )
        return set(ranked[:4])

    alias = {"simd_bias": "simd_identity"}
    disagreements = 0
    for h in SAMPLE_HASHES:
        old = {alias.get(n, n) for n in old_enroll_select(h)}
        new = set(get_reward_active_fingerprint_checks(bytes.fromhex(h)))
        if old != new:
            disagreements += 1
    assert disagreements > 0, "expected the legacy enroll algorithm to diverge"


def test_simd_alias_mirroring_in_reward_map():
    checks = rr_mod._mirror_simd_aliases({"simd_bias": False})
    assert checks["simd_identity"] is False
    checks = rr_mod._mirror_simd_aliases({"simd_identity": True})
    assert checks["simd_bias"] is True
    assert rr_mod._mirror_simd_aliases("garbage") == {}
