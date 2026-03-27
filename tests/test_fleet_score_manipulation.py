"""
Tests for RIP-201 Fleet Score Manipulation PoC (Bounty #494).

Verifies that:
1. Baseline fleet (no evasion) IS detected (scores > 0.3)
2. Manipulated fleet (all techniques) evades detection (scores < 0.3)
3. Evasion is sustained across 3+ consecutive epochs
4. 10+ miners all remain CLEAN simultaneously
"""

import importlib.util
import random
import sqlite3
import sys
from pathlib import Path

import pytest


def _load_fleet_module():
    module_name = "fleet_immune_system_manip_test"
    if module_name in sys.modules:
        return sys.modules[module_name]
    module_path = (
        Path(__file__).resolve().parent.parent
        / "rips"
        / "python"
        / "rustchain"
        / "fleet_immune_system.py"
    )
    if not module_path.exists():
        pytest.skip(f"Fleet module not found: {module_path}")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


fleet_mod = _load_fleet_module()

NUM_MINERS = 12
NUM_EPOCHS = 5
CLEAN_THRESHOLD = 0.3


def _identical_fingerprint():
    return {
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {"vm_indicators": [], "paths_checked": ["/proc/cpuinfo"],
                         "dmesg_scanned": True},
            },
            "clock_drift": {
                "passed": True,
                "data": {"cv": 0.052, "samples": 64},
            },
            "cache_timing": {
                "passed": True,
                "data": {"l1_hit_ns": 4.1, "l2_hit_ns": 10.2},
            },
            "thermal_drift": {
                "passed": True,
                "data": {"entropy": 0.61},
            },
            "simd_identity": {
                "passed": True,
                "data": {"profile": "same-simd"},
            },
        },
        "all_passed": True,
    }


def _minimal_fingerprint(index):
    return {
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {"vm_indicators": [], "paths_checked": ["/proc/cpuinfo"],
                         "dmesg_scanned": True},
            },
            "clock_drift": {
                "passed": True,
                "data": {"cv": round(0.03 + index * 0.007, 4), "samples": 64},
            },
        },
        "all_passed": True,
    }


def _run_baseline(db, epoch, miners):
    """All miners: same IP, same fingerprint, tight timing."""
    for i, miner in enumerate(miners):
        fleet_mod.record_fleet_signals_from_request(
            db, miner=miner, epoch=epoch,
            ip_address="10.0.0.25",
            attest_ts=1000 + i * 3,
            fingerprint=_identical_fingerprint(),
        )
    return fleet_mod.compute_fleet_scores(db, epoch)


def _run_manipulated(db, epoch, miners):
    """All 3 techniques: IP rotation + minimal FP + timing stagger."""
    random.seed(42 + epoch)
    base_ts = 100_000 * epoch
    cumulative = 0
    for i, miner in enumerate(miners):
        if i > 0:
            cumulative += max(35, random.expovariate(1.0 / 45))
        fleet_mod.record_fleet_signals_from_request(
            db, miner=miner, epoch=epoch,
            ip_address=f"198.{51 + i}.{(epoch * 7 + i) % 255}.{10 + i}",
            attest_ts=base_ts + int(cumulative),
            fingerprint=_minimal_fingerprint(i),
        )
    return fleet_mod.compute_fleet_scores(db, epoch)


class TestBaselineDetection:
    """Verify that an unmodified fleet IS detected."""

    def test_baseline_scores_above_threshold(self):
        db = sqlite3.connect(":memory:")
        fleet_mod.ensure_schema(db)
        miners = [f"miner-{i}" for i in range(NUM_MINERS)]
        scores = _run_baseline(db, 100, miners)
        max_score = max(scores.values()) if scores else 0
        assert max_score > CLEAN_THRESHOLD, (
            f"Baseline should be detected but max score is {max_score}"
        )


class TestManipulationEvasion:
    """Verify that manipulated fleet evades detection."""

    def test_all_scores_below_threshold(self):
        db = sqlite3.connect(":memory:")
        fleet_mod.ensure_schema(db)
        miners = [f"miner-{i}" for i in range(NUM_MINERS)]
        scores = _run_manipulated(db, 500, miners)
        for miner, score in scores.items():
            assert score < CLEAN_THRESHOLD, (
                f"{miner} score {score} >= {CLEAN_THRESHOLD}"
            )

    def test_ten_plus_miners_all_clean(self):
        db = sqlite3.connect(":memory:")
        fleet_mod.ensure_schema(db)
        miners = [f"miner-{i}" for i in range(NUM_MINERS)]
        scores = _run_manipulated(db, 600, miners)
        assert len(scores) >= 10, f"Expected 10+ miners, got {len(scores)}"
        assert all(s < CLEAN_THRESHOLD for s in scores.values())

    def test_sustained_across_epochs(self):
        db = sqlite3.connect(":memory:")
        fleet_mod.ensure_schema(db)
        miners = [f"miner-{i}" for i in range(NUM_MINERS)]
        clean_epochs = 0
        for epoch_offset in range(NUM_EPOCHS):
            scores = _run_manipulated(db, 700 + epoch_offset, miners)
            if all(s < CLEAN_THRESHOLD for s in scores.values()):
                clean_epochs += 1
        assert clean_epochs >= 3, (
            f"Expected 3+ clean epochs, got {clean_epochs}/{NUM_EPOCHS}"
        )

    def test_full_reward_multiplier_preserved(self):
        db = sqlite3.connect(":memory:")
        fleet_mod.ensure_schema(db)
        miners = [f"miner-{i}" for i in range(NUM_MINERS)]
        scores = _run_manipulated(db, 800, miners)
        for miner, score in scores.items():
            multiplier = fleet_mod.apply_fleet_decay(2.5, score)
            assert multiplier >= 2.0, (
                f"{miner}: multiplier {multiplier} too low (score={score})"
            )
