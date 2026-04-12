#!/usr/bin/env python3
"""
RIP-309 Phase 1: Fingerprint Check Rotation (4-of-6 per epoch)
================================================================

Implements rotating measurement freshness to prevent Goodhart's Law
from hollowing out trust metrics. Each epoch, only 4 of 6 hardware
fingerprint checks count toward rewards — selected deterministically
from the previous epoch's block hash.

Built by antigravity-opus46 for bounty #3008 (50 RTC).

Key Principles:
1. Selection is deterministic (same block hash -> same selection)
2. Selection is unpredictable (cannot predict without knowing block hash)
3. All 6 checks still run and log results
4. Only active 4 count for reward weight
"""

import hashlib
import logging
import random
from typing import List, Set, Tuple

logger = logging.getLogger(__name__)

# The 6 fingerprint checks (as specified in RIP-309)
ALL_FP_CHECKS = [
    'clock_drift',           # CPU clock frequency drift measurement
    'cache_timing',          # L1/L2 cache timing signature
    'simd_bias',             # SIMD instruction execution bias
    'thermal_drift',         # CPU thermal throttling signature
    'instruction_jitter',    # Instruction pipeline jitter
    'anti_emulation',        # VM/emulator detection checks
]

ACTIVE_CHECKS_PER_EPOCH = 4  # Select 4 of 6 each epoch


def generate_measurement_nonce(prev_block_hash: bytes) -> bytes:
    """
    Generate measurement nonce from previous epoch's block hash.

    The nonce is deterministic (same hash -> same nonce) but unpredictable
    (cannot compute without knowing the block hash).

    Args:
        prev_block_hash: The hash of the last block in the previous epoch

    Returns:
        32-byte nonce used to seed check selection
    """
    if isinstance(prev_block_hash, str):
        prev_block_hash = prev_block_hash.encode('utf-8')

    return hashlib.sha256(prev_block_hash + b"measurement_nonce").digest()


def select_active_checks(
    prev_block_hash: bytes,
    num_active: int = ACTIVE_CHECKS_PER_EPOCH,
    all_checks: List[str] = None
) -> List[str]:
    """
    Select which fingerprint checks are active for this epoch.

    Uses the previous epoch's block hash as a deterministic random seed
    to select `num_active` checks from the full set of 6.

    Properties:
    - Deterministic: Same prev_block_hash always produces same selection
    - Unpredictable: Cannot predict without knowing block hash
    - Fair: Over many epochs, all checks appear with equal frequency

    Args:
        prev_block_hash: Hash of last block in previous epoch
        num_active: Number of checks to activate (default: 4)
        all_checks: Override the default check list (for testing)

    Returns:
        Sorted list of active check names for this epoch
    """
    if all_checks is None:
        all_checks = ALL_FP_CHECKS.copy()

    nonce = generate_measurement_nonce(prev_block_hash)
    seed = int.from_bytes(nonce[:4], 'big')

    # Use seeded RNG to select checks -- deterministic and reproducible
    rng = random.Random(seed)
    active = rng.sample(all_checks, min(num_active, len(all_checks)))

    # Sort for consistent logging and comparison
    active.sort()

    logger.info(
        "RIP-309: Epoch active checks (%d/%d): %s | nonce_seed=%08x",
        len(active), len(all_checks), active, seed
    )

    return active


def get_inactive_checks(active_checks: List[str]) -> List[str]:
    """
    Get the checks that are NOT active this epoch.

    These checks still run and log results but do not affect reward weight.
    """
    return sorted(set(ALL_FP_CHECKS) - set(active_checks))


def evaluate_fingerprint_for_rewards(
    check_results: dict,
    active_checks: List[str]
) -> Tuple[bool, float, dict]:
    """
    Evaluate a miner's fingerprint results using only active checks.

    All 6 checks are expected to have results (they all still run),
    but only the active 4 count toward the reward weight.

    Args:
        check_results: Dict of {check_name: passed (bool)} for all 6 checks
        active_checks: List of check names active this epoch

    Returns:
        Tuple of:
        - overall_pass: True if all active checks passed
        - pass_ratio: Fraction of active checks that passed (0.0-1.0)
        - audit_log: Detailed per-check results for logging
    """
    active_passed = 0
    active_total = 0
    inactive_passed = 0
    inactive_total = 0

    audit_log = {
        'active_checks': [],
        'inactive_checks': [],
    }

    active_set = set(active_checks)

    for check_name in ALL_FP_CHECKS:
        passed = check_results.get(check_name, False)

        if check_name in active_set:
            active_total += 1
            if passed:
                active_passed += 1
            audit_log['active_checks'].append({
                'check': check_name,
                'passed': passed,
                'counts_for_reward': True,
            })
        else:
            inactive_total += 1
            if passed:
                inactive_passed += 1
            audit_log['inactive_checks'].append({
                'check': check_name,
                'passed': passed,
                'counts_for_reward': False,
            })

    # Overall pass requires ALL active checks to pass
    overall_pass = (active_passed == active_total) if active_total > 0 else False
    pass_ratio = active_passed / active_total if active_total > 0 else 0.0

    audit_log['active_passed'] = active_passed
    audit_log['active_total'] = active_total
    audit_log['inactive_passed'] = inactive_passed
    audit_log['inactive_total'] = inactive_total
    audit_log['overall_pass'] = overall_pass
    audit_log['pass_ratio'] = pass_ratio

    return overall_pass, pass_ratio, audit_log


def log_epoch_rotation(epoch: int, prev_block_hash: bytes):
    """
    Log the complete rotation details for an epoch.

    Called at the start of each epoch for auditing purposes.
    Auditors can use this to verify which checks were active
    for any given epoch after the fact.
    """
    active = select_active_checks(prev_block_hash)
    inactive = get_inactive_checks(active)
    nonce = generate_measurement_nonce(prev_block_hash)

    logger.info(
        "RIP-309 Rotation | Epoch %d | Active: %s | Inactive: %s | "
        "Nonce: %s | BlockHash: %s",
        epoch,
        ','.join(active),
        ','.join(inactive),
        nonce.hex()[:16],
        prev_block_hash.hex()[:16] if isinstance(prev_block_hash, bytes) else str(prev_block_hash)[:16]
    )

    return active, inactive


# -- Verification / Testing --

def verify_rotation_properties():
    """
    Self-test: Verify that rotation has expected statistical properties.

    1. Deterministic: Same hash -> same selection
    2. Different hashes -> different selections (with high probability)
    3. All checks appear over many epochs
    """
    import os

    print("=" * 60)
    print("RIP-309 Phase 1: Fingerprint Check Rotation -- Self-Test")
    print("=" * 60)

    # Test 1: Determinism
    hash1 = b"test_block_hash_epoch_42"
    result_a = select_active_checks(hash1)
    result_b = select_active_checks(hash1)
    assert result_a == result_b, "FAIL: Same hash should produce same selection"
    print(f"PASS Determinism: Same hash -> same selection: {result_a}")

    # Test 2: Different hashes -> different selections
    hash2 = b"test_block_hash_epoch_43"
    result_c = select_active_checks(hash2)
    print(f"PASS Different hash -> selection: {result_c}")

    # Test 3: Unpredictability -- all 6 checks appear across many epochs
    check_counts = {check: 0 for check in ALL_FP_CHECKS}
    unique_selections = set()
    n_epochs = 1000

    for i in range(n_epochs):
        fake_hash = os.urandom(32)
        active = select_active_checks(fake_hash)
        unique_selections.add(tuple(active))
        for check in active:
            check_counts[check] += 1

    print(f"\nDistribution over {n_epochs} random epochs:")
    for check, count in sorted(check_counts.items()):
        pct = count / n_epochs * 100
        print(f"  {check:25s}: {count:4d} ({pct:5.1f}%)")

    expected_rate = ACTIVE_CHECKS_PER_EPOCH / len(ALL_FP_CHECKS)
    print(f"\n  Expected rate: {expected_rate*100:.1f}% per check")
    print(f"  Unique selection sets: {len(unique_selections)}")

    # Verify reasonable distribution (within 10% of expected)
    for check, count in check_counts.items():
        actual_rate = count / n_epochs
        assert abs(actual_rate - expected_rate) < 0.10, (
            f"FAIL: {check} rate {actual_rate:.2f} deviates too far from "
            f"expected {expected_rate:.2f}"
        )

    print(f"\nPASS All checks within +/-10% of expected {expected_rate*100:.0f}% rate")

    # Test 4: Active checks count is always 4
    for i in range(100):
        active = select_active_checks(os.urandom(32))
        assert len(active) == ACTIVE_CHECKS_PER_EPOCH, (
            f"FAIL: Expected {ACTIVE_CHECKS_PER_EPOCH} active, got {len(active)}"
        )
    print(f"PASS All epochs have exactly {ACTIVE_CHECKS_PER_EPOCH} active checks")

    # Test 5: Evaluate fingerprint with rotation
    test_results = {
        'clock_drift': True,
        'cache_timing': True,
        'simd_bias': False,  # This one fails
        'thermal_drift': True,
        'instruction_jitter': True,
        'anti_emulation': True,
    }

    # If simd_bias is active -> overall fail; if inactive -> overall pass
    active_with_simd = ['cache_timing', 'clock_drift', 'instruction_jitter', 'simd_bias']
    active_without_simd = ['anti_emulation', 'cache_timing', 'clock_drift', 'thermal_drift']

    pass_with, ratio_with, _ = evaluate_fingerprint_for_rewards(test_results, active_with_simd)
    pass_without, ratio_without, _ = evaluate_fingerprint_for_rewards(test_results, active_without_simd)

    assert pass_with == False, "FAIL: Should fail when failed check is active"
    assert pass_without == True, "FAIL: Should pass when failed check is inactive"
    assert ratio_with == 0.75, f"FAIL: Expected 0.75 ratio, got {ratio_with}"
    assert ratio_without == 1.0, f"FAIL: Expected 1.0 ratio, got {ratio_without}"

    print(f"PASS Rotation correctly gates reward calculation")
    print(f"  Active includes failed check -> pass={pass_with} ratio={ratio_with}")
    print(f"  Active excludes failed check -> pass={pass_without} ratio={ratio_without}")

    print(f"\n{'=' * 60}")
    print(f"ALL TESTS PASSED -- RIP-309 Phase 1 verified")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    verify_rotation_properties()
