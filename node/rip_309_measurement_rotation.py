#!/usr/bin/env python3
"""
RIP-309: Rotating Measurement Freshness
========================================

Anti-Goodhart mechanism for hardware fingerprint and behavioral trust scoring.
Each epoch, a deterministic nonce derived from the previous block hash selects
which measurements are active. All measurements run; only the active subset
counts toward rewards.

Phase 4 extension in this file:
- deterministic challenge rotation across layers from the RIP-309 nonce
- challenge plan generation for:
  * timing challenge (substrate)
  * continuity challenge (memory / continuity)
  * coordination challenge (distinctness / coordination)

This module intentionally provides challenge planning + observability, not a
pretend challenge-response executor.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import sqlite3
import time
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Sequence, Tuple

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

CHALLENGE_TYPES = [
    "timing_challenge",
    "continuity_challenge",
    "coordination_challenge",
]

CHALLENGE_LAYER_MAP = {
    "timing_challenge": "substrate",
    "continuity_challenge": "memory_continuity",
    "coordination_challenge": "distinctness_coordination",
}

TIMING_PROBES = [
    "clock_drift",
    "cache_timing",
    "instruction_jitter",
    "thermal_drift",
]

CONTINUITY_MODALITIES = [
    "memory_anchor_recall",
    "state_sequence_replay",
    "uptime_window_consistency",
    "attestation_chain_gap_check",
]

COORDINATION_MODALITIES = [
    "distinct_response_window",
    "peer_order_divergence",
    "multi_agent_nonce_partition",
    "cohort_separation_check",
]


@dataclass(frozen=True)
class ChallengeSpec:
    challenge_type: str
    layer: str
    seed: str
    interval_slots: int
    offset_slots: int
    timeout_seconds: int
    parameters: Dict[str, object]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def derive_epoch_nonce(prev_block_hash: str) -> bytes:
    """
    Derive a measurement nonce for this epoch from the previous block hash.

    The nonce is unpredictable before the block is produced but verifiable after.
    """
    if not prev_block_hash:
        logger.warning("RIP-309: No prev_block_hash, using genesis fallback nonce")
        return hashlib.sha256(b"rip309_genesis_fallback").digest()

    return hashlib.sha256(
        bytes.fromhex(prev_block_hash) + b"rip309_measurement_nonce"
    ).digest()


def _derive_stream(nonce: bytes, label: str) -> bytes:
    return hashlib.sha256(nonce + label.encode("utf-8")).digest()


def _rng_from_stream(nonce: bytes, label: str) -> random.Random:
    seed = int.from_bytes(_derive_stream(nonce, label)[:8], "big")
    return random.Random(seed)


def get_active_fp_checks(nonce: bytes) -> List[str]:
    """Select which 4-of-6 fingerprint checks are active this epoch."""
    rng = _rng_from_stream(nonce, "active_fingerprint_checks")
    active = rng.sample(ALL_FP_CHECKS, ACTIVE_FP_COUNT)
    return sorted(active)


def get_observation_window_hours(nonce: bytes) -> int:
    """Determine the observation window for this epoch (bimodal distribution)."""
    rng = _rng_from_stream(nonce, "observation_window_hours")
    if rng.random() < WINDOW_FAST_PROBABILITY:
        return rng.randint(*WINDOW_FAST_RANGE)
    return rng.randint(*WINDOW_SLOW_RANGE)


def evaluate_fingerprint_rotation(
    fingerprint_data: dict,
    active_checks: List[str],
) -> Tuple[bool, int, int]:
    """Evaluate a miner's fingerprint against the active check subset."""
    checks = fingerprint_data.get("checks", {})
    active_passed = 0
    active_total = len(active_checks)

    for check_name in active_checks:
        check_result = checks.get(check_name, {})
        if check_result.get("passed", False):
            active_passed += 1

    passed = active_passed == active_total
    return passed, active_passed, active_total


def compute_ema_score(
    epoch_scores: List[Tuple[int, float]],
    current_epoch: int,
    decay: float = EMA_DECAY,
) -> float:
    """Compute exponential moving average trust score across epochs."""
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
    """Detect sudden behavioral shift after an honest streak."""
    recent = [(e, s) for e, s in epoch_scores if current_epoch - e <= 50]

    if len(recent) < min_history:
        return False, None

    scores = [s for _, s in recent]
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)

    if variance == 0:
        if current_score != mean:
            return True, float("inf")
        return False, 0.0

    std_dev = variance ** 0.5
    z_score = (current_score - mean) / std_dev

    is_spike = abs(z_score) > threshold_sigma
    return is_spike, z_score


def _choose(rng: random.Random, items: Sequence[str]) -> str:
    return items[rng.randrange(len(items))]


def build_timing_challenge(nonce: bytes, epoch: int) -> ChallengeSpec:
    rng = _rng_from_stream(nonce, f"timing:{epoch}")
    return ChallengeSpec(
        challenge_type="timing_challenge",
        layer=CHALLENGE_LAYER_MAP["timing_challenge"],
        seed=_derive_stream(nonce, f"timing-seed:{epoch}").hex(),
        interval_slots=rng.randint(3, 11),
        offset_slots=rng.randint(0, 2),
        timeout_seconds=rng.randint(20, 90),
        parameters={
            "probe": _choose(rng, TIMING_PROBES),
            "sample_count": rng.randint(8, 32),
            "burst_count": rng.randint(2, 6),
            "jitter_budget_ms": rng.randint(15, 180),
        },
    )


def build_continuity_challenge(nonce: bytes, epoch: int) -> ChallengeSpec:
    rng = _rng_from_stream(nonce, f"continuity:{epoch}")
    return ChallengeSpec(
        challenge_type="continuity_challenge",
        layer=CHALLENGE_LAYER_MAP["continuity_challenge"],
        seed=_derive_stream(nonce, f"continuity-seed:{epoch}").hex(),
        interval_slots=rng.randint(6, 18),
        offset_slots=rng.randint(0, 5),
        timeout_seconds=rng.randint(45, 240),
        parameters={
            "mode": _choose(rng, CONTINUITY_MODALITIES),
            "required_depth": rng.randint(2, 6),
            "lookback_epochs": rng.randint(1, 5),
            "anchor_count": rng.randint(1, 4),
        },
    )


def build_coordination_challenge(nonce: bytes, epoch: int) -> ChallengeSpec:
    rng = _rng_from_stream(nonce, f"coordination:{epoch}")
    return ChallengeSpec(
        challenge_type="coordination_challenge",
        layer=CHALLENGE_LAYER_MAP["coordination_challenge"],
        seed=_derive_stream(nonce, f"coordination-seed:{epoch}").hex(),
        interval_slots=rng.randint(9, 27),
        offset_slots=rng.randint(0, 8),
        timeout_seconds=rng.randint(60, 300),
        parameters={
            "mode": _choose(rng, COORDINATION_MODALITIES),
            "cohort_size": rng.randint(2, 7),
            "distinctness_threshold": round(rng.uniform(0.55, 0.95), 3),
            "response_window_seconds": rng.randint(20, 120),
        },
    )


def get_epoch_challenge_plan(prev_block_hash: str, epoch: int) -> Dict:
    """
    Build the deterministic Phase 4 challenge plan for an epoch.

    This is intentionally a planning/observability layer, not a challenge
    fulfillment/execution layer.
    """
    nonce = derive_epoch_nonce(prev_block_hash)
    challenges = [
        build_timing_challenge(nonce, epoch),
        build_continuity_challenge(nonce, epoch),
        build_coordination_challenge(nonce, epoch),
    ]

    challenge_order_rng = _rng_from_stream(nonce, f"challenge-order:{epoch}")
    challenges = list(challenges)
    challenge_order_rng.shuffle(challenges)

    return {
        "epoch": epoch,
        "nonce": nonce.hex(),
        "challenge_rotation_version": 1,
        "challenge_count": len(challenges),
        "active_challenges": [challenge.to_dict() for challenge in challenges],
        "layers_covered": [challenge.layer for challenge in challenges],
    }


def persist_epoch_challenge_plan(
    db_path: str,
    prev_block_hash: str,
    epoch: int,
) -> Dict:
    """Persist the deterministic challenge plan for auditability."""
    plan = get_epoch_challenge_plan(prev_block_hash, epoch)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rip309_epoch_challenges (
                epoch INTEGER PRIMARY KEY,
                prev_block_hash TEXT,
                nonce TEXT NOT NULL,
                challenge_plan_json TEXT NOT NULL,
                created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO rip309_epoch_challenges (
                epoch, prev_block_hash, nonce, challenge_plan_json
            ) VALUES (?, ?, ?, ?)
            """,
            (epoch, prev_block_hash, plan["nonce"], json.dumps(plan, sort_keys=True)),
        )
        conn.commit()

    return plan


def get_epoch_measurement_config(
    prev_block_hash: str,
    epoch: int,
) -> Dict:
    """Get the complete measurement + challenge configuration for an epoch."""
    nonce = derive_epoch_nonce(prev_block_hash)
    active_fp = get_active_fp_checks(nonce)
    window_hours = get_observation_window_hours(nonce)
    challenge_rotation = get_epoch_challenge_plan(prev_block_hash, epoch)

    config = {
        "epoch": epoch,
        "nonce": nonce.hex(),
        "active_fingerprints": active_fp,
        "inactive_fingerprints": sorted(
            set(ALL_FP_CHECKS) - set(active_fp)
        ),
        "observation_window_hours": window_hours,
        "window_mode": "fast" if window_hours <= 24 else "slow",
        "challenge_rotation": challenge_rotation,
    }

    logger.info(
        "RIP-309 epoch %d: active=%s, window=%dh (%s), challenges=%s, nonce=%s",
        epoch,
        active_fp,
        window_hours,
        config["window_mode"],
        [c["challenge_type"] for c in challenge_rotation["active_challenges"]],
        nonce.hex()[:16],
    )

    return config


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("RIP-309 Measurement Rotation — Self Test\n")

    print("=== Fingerprint Check Rotation (20 epochs) ===")
    check_counts = {c: 0 for c in ALL_FP_CHECKS}
    for i in range(20):
        fake_hash = hashlib.sha256(f"block_{i}".encode()).hexdigest()
        config = get_epoch_measurement_config(fake_hash, i)
        for c in config["active_fingerprints"]:
            check_counts[c] += 1
        window = config["observation_window_hours"]
        mode = config["window_mode"]
        challenges = [c["challenge_type"] for c in config["challenge_rotation"]["active_challenges"]]
        print(
            f"  Epoch {i:2d}: {config['active_fingerprints']} "
            f"window={window}h ({mode}) challenges={challenges}"
        )

    print(f"\nCheck activation counts over 20 epochs:")
    for check, count in sorted(check_counts.items()):
        bar = "#" * count
        print(f"  {check:20s}: {count:2d}/20 ({count/20*100:.0f}%) {bar}")

    print("\n=== EMA Scoring ===")
    scores = [(i, 0.3) for i in range(10)] + [(i, 0.9) for i in range(10, 20)]
    for epoch in [10, 12, 15, 19]:
        ema = compute_ema_score(scores[:epoch + 1], epoch)
        print(f"  Epoch {epoch}: EMA={ema:.3f}")

    print("\n=== Spike Detection ===")
    honest_scores = [(i, 0.8 + random.Random(42).gauss(0, 0.05)) for i in range(20)]
    is_spike, z = detect_score_spike(honest_scores, 20, 0.2)
    print(f"  Honest streak then drop to 0.2: spike={is_spike}, z={z:.2f}")
    is_spike, z = detect_score_spike(honest_scores, 20, 0.75)
    print(f"  Honest streak then 0.75:        spike={is_spike}, z={z:.2f}")

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
    print("  (Expected: ~60/40)")
