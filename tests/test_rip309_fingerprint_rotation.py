# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env python3
"""
Tests for RIP-309: Fingerprint Check Rotation
==============================================

Verifies that:
  - get_active_fingerprint_checks() selects exactly ACTIVE_CHECK_COUNT checks
  - Selection is deterministic: identical prev_block_hash → identical result
  - Selection is drawn from ALL_FP_CHECKS with no duplicates
  - Different block hashes produce different selections (rotation happens)
  - get_measurement_nonce() output is distinct from its input

Run:
    python -m pytest tests/test_rip309_fingerprint_rotation.py -v
"""

from __future__ import annotations

import hashlib
import os
import random
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
NODE_DIR = PROJECT_ROOT / "node"
for p in (str(PROJECT_ROOT), str(NODE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from rip_200_round_robin_1cpu1vote import (  # noqa: E402
    ACTIVE_CHECK_COUNT,
    ALL_FP_CHECKS,
    get_active_fingerprint_checks,
    get_measurement_nonce,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BLOCK_HASH_A = hashlib.sha256(b"epoch_99_last_block").digest()
_BLOCK_HASH_B = hashlib.sha256(b"epoch_100_last_block").digest()
_BLOCK_HASH_C = hashlib.sha256(b"epoch_101_last_block").digest()


# ---------------------------------------------------------------------------
# Tests: get_measurement_nonce
# ---------------------------------------------------------------------------


def test_nonce_is_32_bytes():
    nonce = get_measurement_nonce(_BLOCK_HASH_A)
    assert len(nonce) == 32


def test_nonce_differs_from_input():
    """Nonce must not equal prev_block_hash (domain separation via suffix)."""
    nonce = get_measurement_nonce(_BLOCK_HASH_A)
    assert nonce != _BLOCK_HASH_A


def test_nonce_deterministic():
    assert get_measurement_nonce(_BLOCK_HASH_A) == get_measurement_nonce(_BLOCK_HASH_A)


def test_nonce_changes_with_input():
    assert get_measurement_nonce(_BLOCK_HASH_A) != get_measurement_nonce(_BLOCK_HASH_B)


# ---------------------------------------------------------------------------
# Tests: get_active_fingerprint_checks
# ---------------------------------------------------------------------------


def test_returns_correct_count():
    checks = get_active_fingerprint_checks(_BLOCK_HASH_A)
    assert len(checks) == ACTIVE_CHECK_COUNT


def test_all_checks_in_allowed_set():
    checks = get_active_fingerprint_checks(_BLOCK_HASH_A)
    for c in checks:
        assert c in ALL_FP_CHECKS, f"Unknown check: {c!r}"


def test_no_duplicates():
    checks = get_active_fingerprint_checks(_BLOCK_HASH_A)
    assert len(checks) == len(set(checks))


def test_deterministic_same_hash():
    """Identical prev_block_hash must always yield the same 4 checks."""
    result_1 = get_active_fingerprint_checks(_BLOCK_HASH_A)
    result_2 = get_active_fingerprint_checks(_BLOCK_HASH_A)
    assert result_1 == result_2


def test_different_hashes_different_checks():
    """Different block hashes should (almost certainly) yield different check sets.

    The probability of a collision is C(6,4)/C(6,4) * (1 chance) = 1/15 per pair.
    With three independent pairs tested, collision probability is < 0.05%.
    """
    checks_a = set(get_active_fingerprint_checks(_BLOCK_HASH_A))
    checks_b = set(get_active_fingerprint_checks(_BLOCK_HASH_B))
    checks_c = set(get_active_fingerprint_checks(_BLOCK_HASH_C))
    # At least one pair must differ
    assert not (checks_a == checks_b == checks_c), (
        "All three epochs produced identical check selections — "
        "rotation does not appear to be working"
    )


def test_rotation_across_many_epochs():
    """Verify that rotation produces diverse selections over 20 synthetic epochs.

    Across 20 epochs with random block hashes, we expect more than one unique
    selection set (P(all same) < 1e-14).
    """
    rng = random.Random(42)
    selections = set()
    for _ in range(20):
        block_hash = rng.randbytes(32)
        checks = tuple(get_active_fingerprint_checks(block_hash))
        selections.add(checks)
    assert len(selections) > 1, (
        f"Expected multiple distinct check sets over 20 epochs, "
        f"got {len(selections)}"
    )


def test_inactive_checks_are_four():
    """Exactly 6 - ACTIVE_CHECK_COUNT checks should be inactive each epoch."""
    checks = get_active_fingerprint_checks(_BLOCK_HASH_A)
    inactive = [c for c in ALL_FP_CHECKS if c not in checks]
    assert len(inactive) == len(ALL_FP_CHECKS) - ACTIVE_CHECK_COUNT


def test_check_count_constants():
    """Sanity-check that the constants match the spec (4 of 6)."""
    assert len(ALL_FP_CHECKS) == 6
    assert ACTIVE_CHECK_COUNT == 4


def test_all_six_checks_present_in_constant():
    """ALL_FP_CHECKS must include the six checks named in RIP-309 spec."""
    expected = {
        "clock_drift",
        "cache_timing",
        "simd_bias",
        "thermal_drift",
        "instruction_jitter",
        "anti_emulation",
    }
    assert set(ALL_FP_CHECKS) == expected
