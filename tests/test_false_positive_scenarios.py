"""
Tests for RIP-201 False Positive Analysis (Bounty #493).

Verifies that legitimate mining scenarios trigger false positives
in the current fleet detection system.
"""

import importlib.util
import random
import sqlite3
import sys
from pathlib import Path

import pytest


def _load_fleet_module():
    module_name = "fleet_immune_system_fp_test"
    if module_name in sys.modules:
        return sys.modules[module_name]
    module_path = (
        Path(__file__).resolve().parent.parent
        / "rips" / "python" / "rustchain" / "fleet_immune_system.py"
    )
    if not module_path.exists():
        pytest.skip(f"Fleet module not found: {module_path}")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


fleet_mod = _load_fleet_module()
THRESHOLD = 0.3


def _fp(cv=0.052, l1=4.1, l2=10.2, entropy=0.61, simd="default"):
    return {
        "checks": {
            "anti_emulation": {"passed": True, "data": {"vm_indicators": [],
                               "paths_checked": ["/proc/cpuinfo"], "dmesg_scanned": True}},
            "clock_drift": {"passed": True, "data": {"cv": round(cv, 4), "samples": 64}},
            "cache_timing": {"passed": True, "data": {"l1_hit_ns": l1, "l2_hit_ns": l2}},
            "thermal_drift": {"passed": True, "data": {"entropy": entropy}},
            "simd_identity": {"passed": True, "data": {"profile": simd}},
        },
        "all_passed": True,
    }


class TestUniversityCampus:
    """Students on same campus /24 get falsely penalized."""

    def test_shared_subnet_causes_penalty(self):
        db = sqlite3.connect(":memory:")
        fleet_mod.ensure_schema(db)
        random.seed(101)
        for i in range(6):
            fleet_mod.record_fleet_signals_from_request(
                db, miner=f"student-{i}", epoch=100,
                ip_address=f"192.168.1.{10 + i}",
                attest_ts=50000 + random.randint(0, 3600),
                fingerprint=_fp(
                    cv=round(random.uniform(0.03, 0.08), 4),
                    l1=round(random.uniform(3.5, 5.0), 1),
                    l2=round(random.uniform(9.0, 12.0), 1),
                    entropy=round(random.uniform(0.4, 0.8), 2),
                    simd=random.choice(["x86-avx2", "x86-sse4", "arm-neon", "x86-avx512"]),
                ),
            )
        scores = fleet_mod.compute_fleet_scores(db, 100)
        penalized = sum(1 for s in scores.values() if s >= THRESHOLD)
        assert penalized > 0, "University students should be falsely penalized"


class TestCloudHosting:
    """Independent AWS miners on same /24 get falsely penalized."""

    def test_same_region_causes_penalty(self):
        db = sqlite3.connect(":memory:")
        fleet_mod.ensure_schema(db)
        random.seed(102)
        for i in range(5):
            fleet_mod.record_fleet_signals_from_request(
                db, miner=f"aws-{i}", epoch=200,
                ip_address=f"172.31.16.{100 + i}",
                attest_ts=80000 + i * 120,
                fingerprint=_fp(
                    cv=round(0.045 + random.uniform(-0.005, 0.005), 4),
                    l1=round(3.8 + random.uniform(-0.2, 0.2), 1),
                    l2=round(10.0 + random.uniform(-0.5, 0.5), 1),
                    entropy=round(0.55 + random.uniform(-0.1, 0.1), 2),
                    simd="x86-avx512",
                ),
            )
        scores = fleet_mod.compute_fleet_scores(db, 200)
        penalized = sum(1 for s in scores.values() if s >= THRESHOLD)
        assert penalized >= 3, f"AWS miners should be penalized, got {penalized}"


class TestSameHardware:
    """Identical hardware from different locations gets penalized."""

    def test_identical_fingerprints_different_ips(self):
        db = sqlite3.connect(":memory:")
        fleet_mod.ensure_schema(db)
        random.seed(105)
        for i in range(5):
            fleet_mod.record_fleet_signals_from_request(
                db, miner=f"macbook-{i}", epoch=300,
                ip_address=f"198.{51 + i}.0.10",  # Different /24!
                attest_ts=60000 + random.randint(0, 14400),
                fingerprint=_fp(cv=0.052, l1=4.1, l2=10.2, entropy=0.61, simd="arm-neon"),
            )
        scores = fleet_mod.compute_fleet_scores(db, 300)
        penalized = sum(1 for s in scores.values() if s >= THRESHOLD)
        assert penalized > 0, "Same hardware model should trigger false positive"


class TestTimezoneCluster:
    """Cron job coincidence in same timezone triggers false positive."""

    def test_timing_coincidence_penalizes(self):
        db = sqlite3.connect(":memory:")
        fleet_mod.ensure_schema(db)
        random.seed(106)
        for i in range(10):
            fleet_mod.record_fleet_signals_from_request(
                db, miner=f"tz-{i}", epoch=400,
                ip_address=f"203.{i + 10}.{random.randint(1, 254)}.{random.randint(1, 254)}",
                attest_ts=90000 + random.randint(0, 25),
                fingerprint=_fp(
                    cv=round(random.uniform(0.02, 0.09), 4),
                    l1=round(random.uniform(3.0, 6.0), 1),
                    l2=round(random.uniform(8.0, 14.0), 1),
                    entropy=round(random.uniform(0.3, 0.9), 2),
                    simd=random.choice(["x86-avx2", "x86-sse4", "arm-neon"]),
                ),
            )
        scores = fleet_mod.compute_fleet_scores(db, 400)
        penalized = sum(1 for s in scores.values() if s >= THRESHOLD)
        assert penalized > 0, "Timezone clustering should trigger false positive"


class TestCGNATIsClean:
    """CGNAT with diverse hardware and spread timing should be clean."""

    def test_diverse_cgnat_not_penalized(self):
        db = sqlite3.connect(":memory:")
        fleet_mod.ensure_schema(db)
        random.seed(104)
        for i in range(8):
            fleet_mod.record_fleet_signals_from_request(
                db, miner=f"home-{i}", epoch=500,
                ip_address=f"100.64.0.{i + 1}",
                attest_ts=70000 + random.randint(0, 7200),
                fingerprint=_fp(
                    cv=round(random.uniform(0.02, 0.09), 4),
                    l1=round(random.uniform(3.0, 6.0), 1),
                    l2=round(random.uniform(8.0, 14.0), 1),
                    entropy=round(random.uniform(0.3, 0.9), 2),
                    simd=random.choice(["x86-avx2", "x86-sse4", "arm-neon", "x86-avx512", "arm-sve"]),
                ),
            )
        scores = fleet_mod.compute_fleet_scores(db, 500)
        penalized = sum(1 for s in scores.values() if s >= THRESHOLD)
        assert penalized == 0, (
            f"CGNAT with diverse hardware should not be penalized, got {penalized}"
        )
