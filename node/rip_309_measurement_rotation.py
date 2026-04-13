#!/usr/bin/env python3
"""
RIP-309: Rotating Measurement Freshness
========================================

Anti-Goodhart mechanism for hardware fingerprint and behavioral trust scoring.
Each epoch, a deterministic nonce derived from the previous block hash selects
which measurements are active. All measurements run; only the active subset
counts toward rewards.

Features (inspired by community feedback from opencode-moltu-1 on Moltbook):
1. Fingerprint check rotation: 4-of-6 active per epoch
2. Weighted decay aggregation: recent epochs weighted higher (EMA)
3. Spike detector: catches sudden behavioral shifts after honest streaks
4. Bimodal observation windows: "fast" (6-24h) and "slow" (72-168h) modes

Design principle: "Trust infrastructure that distrusts itself on a schedule."
"""

import hashlib
import logging
import random
import sqlite3
import time
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# All 6 fingerprint check names (must match fingerprint_checks.py)
ALL_FP_CHECKS = [
    "clock_drift",
    "cache_timing",
    "simd_identity",
    "thermal_drift",
    "instruction_jitter",
    "anti_emulation",
]

# How many checks are active per epoch
ACTIVE_FP_COUNT = 4

# First-pass behavioral metric pool grounded in existing code paths.
# These are intentionally substrate-level metrics derived from the current
# miner / attestation / settlement / claims machinery rather than aspirational
# social metrics that the repo does not yet collect.
BEHAVIORAL_METRIC_POOL = [
    {
        "name": "attestation_recency",
        "description": "How recently the miner re-attested before settlement.",
        "source": "miner_attest_recent.ts_ok / machine_passport attestations",
    },
    {
        "name": "enrollment_consistency",
        "description": "Whether the miner consistently appears in epoch_enroll snapshots.",
        "source": "sophia_elya_service.py / epoch_enroll",
    },
    {
        "name": "weight_stability",
        "description": "Whether epoch enrollment weight remains stable across re-enrollment attempts.",
        "source": "epoch_enroll preservation tests / RIP-200 enrollment flow",
    },
    {
        "name": "fingerprint_pass_rate",
        "description": "How consistently the miner passes fingerprint validation over time.",
        "source": "fingerprint_passed / anti_double_mining.py",
    },
    {
        "name": "entropy_stability",
        "description": "How stable the miner's entropy score remains across attestations.",
        "source": "entropy_score / rip_proof_of_antiquity_hardware.py",
    },
    {
        "name": "duplicate_identity_risk",
        "description": "Whether the miner clusters with duplicate machine identities in the same epoch.",
        "source": "anti_double_mining.py duplicate identity detection",
    },
    {
        "name": "reward_continuity",
        "description": "Whether the miner shows continuous reward-eligible participation across epochs.",
        "source": "epoch_rewards / rewards_implementation_rip200.py",
    },
    {
        "name": "claim_followthrough",
        "description": "Whether earned rewards are later claimed and settled cleanly.",
        "source": "claims_submission.py / claims_settlement.py",
    },
    {
        "name": "hardware_binding_consistency",
        "description": "Whether the miner's hardware binding remains consistent across attestations.",
        "source": "hardware_binding_v2.py / machine_passport.py",
    },
    {
        "name": "nonce_replay_hygiene",
        "description": "Whether attest / sync nonce handling stays clean and replay-free.",
        "source": "used_nonces / rustchain_sync_endpoints.py",
    },
]

ACTIVE_BEHAVIORAL_METRIC_COUNT = 5

# Weighted decay factor for EMA (exponential moving average)
# 0.95 means each epoch is worth 95% of the previous one
# ~14 epochs (2.3 hours) half-life; ~46 epochs (7.7 hours) to 10% weight
EMA_DECAY = 0.95

# Spike detection: if a miner's epoch score deviates from their rolling
# average by more than this many standard deviations, flag it
SPIKE_THRESHOLD_SIGMA = 2.5

# Minimum epochs before spike detection activates (need enough history)
SPIKE_MIN_HISTORY = 10

# Observation window modes (bimodal, not uniform)
# Fast mode catches sudden changes; slow mode catches gradual drift
WINDOW_FAST_RANGE = (6, 24)    # hours
WINDOW_SLOW_RANGE = (72, 168)  # hours
WINDOW_FAST_PROBABILITY = 0.6  # 60% chance of fast window


def derive_epoch_nonce(prev_block_hash: str) -> bytes:
    """
    Derive a measurement nonce for this epoch from the previous block hash.

    The nonce is unpredictable before the block is produced but verifiable after.
    This is the same property that makes PoW nonces useful.

    Args:
        prev_block_hash: Hex string of the previous epoch's block hash

    Returns:
        32-byte nonce
    """
    if not prev_block_hash:
        # Genesis epoch or missing hash — use fixed seed
        # This is acceptable ONLY for epoch 0
        logger.warning("RIP-309: No prev_block_hash, using genesis fallback nonce")
        return hashlib.sha256(b"rip309_genesis_fallback").digest()

    return hashlib.sha256(
        bytes.fromhex(prev_block_hash) + b"rip309_measurement_nonce"
    ).digest()


def get_behavioral_metric_pool() -> List[Dict[str, str]]:
    """Return the full behavioral metric pool metadata."""
    return [dict(metric) for metric in BEHAVIORAL_METRIC_POOL]


def get_active_behavioral_metrics(nonce: bytes) -> List[str]:
    """
    Select which 5-of-10 behavioral metrics are active this epoch.

    This uses a deterministic seed derived from a different nonce slice than
    fingerprint rotation so both selections are independently stable while still
    agreeing across nodes.
    """
    seed = int.from_bytes(nonce[4:8], "big")
    metric_names = [metric["name"] for metric in BEHAVIORAL_METRIC_POOL]
    active = random.Random(seed).sample(metric_names, ACTIVE_BEHAVIORAL_METRIC_COUNT)
    return sorted(active)


def get_active_fp_checks(nonce: bytes) -> List[str]:
    """
    Select which 4-of-6 fingerprint checks are active this epoch.

    Uses deterministic random seeded by the nonce, so all nodes agree
    on which checks are active for any given epoch.

    Args:
        nonce: 32-byte epoch nonce from derive_epoch_nonce()

    Returns:
        Sorted list of 4 active check names
    """
    seed = int.from_bytes(nonce[:4], "big")
    active = random.Random(seed).sample(ALL_FP_CHECKS, ACTIVE_FP_COUNT)
    return sorted(active)


def get_observation_window_hours(nonce: bytes) -> int:
    """
    Determine the observation window for this epoch (bimodal distribution).

    60% chance of fast window (6-24h), 40% chance of slow window (72-168h).
    This is better than uniform 6-168h because:
    - Fast windows catch sudden drift
    - Slow windows catch gradual gaming
    - The gap (24-72h) is intentional — no "medium" cadence to optimize for

    Args:
        nonce: 32-byte epoch nonce

    Returns:
        Observation window in hours
    """
    seed = int.from_bytes(nonce[8:12], "big")
    rng = random.Random(seed)

    if rng.random() < WINDOW_FAST_PROBABILITY:
        return rng.randint(*WINDOW_FAST_RANGE)
    else:
        return rng.randint(*WINDOW_SLOW_RANGE)


def evaluate_fingerprint_rotation(
    fingerprint_data: dict,
    active_checks: List[str],
) -> Tuple[bool, int, int]:
    """
    Evaluate a miner's fingerprint against the active check subset.

    All 6 checks still run (for logging/auditing). Only the active 4 count
    toward the pass/fail determination.

    Args:
        fingerprint_data: Dict with 'checks' key containing per-check results
        active_checks: List of active check names for this epoch

    Returns:
        Tuple of (passed, active_passed_count, active_total_count)
    """
    checks = fingerprint_data.get("checks", {})
    active_passed = 0
    active_total = len(active_checks)

    for check_name in active_checks:
        check_result = checks.get(check_name, {})
        if check_result.get("passed", False):
            active_passed += 1

    # All active checks must pass for the miner to earn full weight
    passed = active_passed == active_total
    return passed, active_passed, active_total


def compute_ema_score(
    epoch_scores: List[Tuple[int, float]],
    current_epoch: int,
    decay: float = EMA_DECAY,
) -> float:
    """
    Compute exponential moving average trust score across epochs.

    Recent epochs are weighted higher than older ones, so genuine improvement
    shows up faster while rotation variance still gets smoothed.

    This addresses opencode-moltu-1's critique that simple rolling averages
    make the improvement feedback loop too slow (50+ epochs / 8+ hours).
    With EMA decay=0.95, significant weight shifts happen within ~14 epochs
    (~2.3 hours).

    Args:
        epoch_scores: List of (epoch_number, score) tuples
        current_epoch: Current epoch number
        decay: Decay factor per epoch (0.95 = ~14 epoch half-life)

    Returns:
        Weighted average score (0.0 to 1.0)
    """
    if not epoch_scores:
        return 0.0

    weighted_sum = 0.0
    weight_sum = 0.0

    for epoch_num, score in epoch_scores:
        age = current_epoch - epoch_num
        if age < 0:
            continue
        w = decay ** age
        weighted_sum += score * w
        weight_sum += w

    if weight_sum == 0:
        return 0.0

    return weighted_sum / weight_sum


def detect_score_spike(
    epoch_scores: List[Tuple[int, float]],
    current_epoch: int,
    current_score: float,
    threshold_sigma: float = SPIKE_THRESHOLD_SIGMA,
    min_history: int = SPIKE_MIN_HISTORY,
) -> Tuple[bool, Optional[float]]:
    """
    Detect sudden behavioral shift after an honest streak.

    An agent that was honest for 90 epochs and games epoch 91 will show
    a score spike. The rolling EMA smooths over this, but the spike detector
    catches it in real time.

    This addresses opencode-moltu-1's critique that rolling averages let
    sudden gaming go undetected.

    Args:
        epoch_scores: Historical (epoch, score) tuples
        current_epoch: Current epoch
        current_score: Score for the current epoch
        threshold_sigma: Standard deviations to trigger spike
        min_history: Minimum epochs before detection activates

    Returns:
        Tuple of (is_spike, z_score). z_score is None if insufficient history.
    """
    recent = [(e, s) for e, s in epoch_scores if current_epoch - e <= 50]

    if len(recent) < min_history:
        return False, None

    scores = [s for _, s in recent]
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)

    if variance == 0:
        # All scores identical — any deviation is a spike
        if current_score != mean:
            return True, float("inf")
        return False, 0.0

    std_dev = variance ** 0.5
    z_score = (current_score - mean) / std_dev

    is_spike = abs(z_score) > threshold_sigma
    return is_spike, z_score


def get_epoch_measurement_config(
    prev_block_hash: str,
    epoch: int,
) -> Dict:
    """
    Get the complete measurement configuration for an epoch.

    This is the main entry point for the reward calculation to determine
    which measurements are active.

    Args:
        prev_block_hash: Previous block hash (hex string)
        epoch: Current epoch number

    Returns:
        Dict with active rotations and observation_window_hours, nonce
    """
    nonce = derive_epoch_nonce(prev_block_hash)
    active_fp = get_active_fp_checks(nonce)
    active_behavioral = get_active_behavioral_metrics(nonce)
    window_hours = get_observation_window_hours(nonce)
    all_behavioral = [metric["name"] for metric in BEHAVIORAL_METRIC_POOL]

    config = {
        "epoch": epoch,
        "nonce": nonce.hex(),
        "active_fingerprints": active_fp,
        "inactive_fingerprints": sorted(
            set(ALL_FP_CHECKS) - set(active_fp)
        ),
        "behavioral_metric_pool": get_behavioral_metric_pool(),
        "active_behavioral_metrics": active_behavioral,
        "inactive_behavioral_metrics": sorted(
            set(all_behavioral) - set(active_behavioral)
        ),
        "behavioral_metric_pool_size": len(BEHAVIORAL_METRIC_POOL),
        "active_behavioral_metric_count": ACTIVE_BEHAVIORAL_METRIC_COUNT,
        "observation_window_hours": window_hours,
        "window_mode": "fast" if window_hours <= 24 else "slow",
    }

    logger.info(
        "RIP-309 epoch %d: fp_active=%s behavioral_active=%s, window=%dh (%s), nonce=%s",
        epoch,
        active_fp,
        active_behavioral,
        window_hours,
        config["window_mode"],
        nonce.hex()[:16],
    )

    return config


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("RIP-309 Measurement Rotation — Self Test\n")

    # Test deterministic rotation across 20 epochs with different hashes
    print("=== Fingerprint Check Rotation (20 epochs) ===")
    check_counts = {c: 0 for c in ALL_FP_CHECKS}
    for i in range(20):
        fake_hash = hashlib.sha256(f"block_{i}".encode()).hexdigest()
        config = get_epoch_measurement_config(fake_hash, i)
        for c in config["active_fingerprints"]:
            check_counts[c] += 1
        inactive = config["inactive_fingerprints"]
        window = config["observation_window_hours"]
        mode = config["window_mode"]
        print(f"  Epoch {i:2d}: {config['active_fingerprints']}  "
              f"window={window}h ({mode})")

    print(f"\nCheck activation counts over 20 epochs:")
    for check, count in sorted(check_counts.items()):
        bar = "#" * count
        print(f"  {check:20s}: {count:2d}/20 ({count/20*100:.0f}%) {bar}")

    # Test EMA scoring
    print("\n=== EMA Scoring ===")
    # Simulate: low scores for 10 epochs, then improvement
    scores = [(i, 0.3) for i in range(10)] + [(i, 0.9) for i in range(10, 20)]
    for epoch in [10, 12, 15, 19]:
        ema = compute_ema_score(scores[:epoch+1], epoch)
        print(f"  Epoch {epoch}: EMA={ema:.3f}")

    # Test spike detection
    print("\n=== Spike Detection ===")
    honest_scores = [(i, 0.8 + random.Random(42).gauss(0, 0.05)) for i in range(20)]
    # Epoch 20: sudden drop (gaming attempt)
    is_spike, z = detect_score_spike(honest_scores, 20, 0.2)
    print(f"  Honest streak then drop to 0.2: spike={is_spike}, z={z:.2f}")
    # Epoch 20: normal variation
    is_spike, z = detect_score_spike(honest_scores, 20, 0.75)
    print(f"  Honest streak then 0.75:        spike={is_spike}, z={z:.2f}")

    # Test observation window distribution
    print("\n=== Observation Window Distribution ===")
    fast = slow = 0
    for i in range(100):
        fake_hash = hashlib.sha256(f"window_test_{i}".encode()).hexdigest()
        nonce = derive_epoch_nonce(fake_hash)
        hours = get_observation_window_hours(nonce)
        if hours <= 24:
            fast += 1
        else:
            slow += 1
    print(f"  Fast (6-24h):   {fast}%")
    print(f"  Slow (72-168h): {slow}%")
    print(f"  (Expected: ~60/40)")
