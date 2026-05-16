"""
Tests for RIP-PoA Fingerprint Replay & Spoofing (Bounty #248).

Proves that all three attack vectors succeed against the current system.
"""

import importlib.util
import json
import os
import random
import sqlite3
import sys
from pathlib import Path

import pytest


def _load_module(name, relpath):
    key = f"fp_replay_{name}"
    if key in sys.modules:
        return sys.modules[key]
    path = Path(__file__).resolve().parent.parent / relpath
    if not path.exists():
        pytest.skip(f"Module not found: {path}")
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


poc = _load_module("poc", "tools/rip_poa_fingerprint_replay_poc.py")
fleet = _load_module("fleet", "rips/python/rustchain/fleet_immune_system.py")


class TestFingerprintReplay:
    """Attack 1: Replay a captured fingerprint from a different machine."""

    def test_capture_produces_valid_fingerprint(self, tmp_path):
        captured = poc.capture_fingerprint(str(tmp_path / "test_fp_capture.json"))
        assert captured["all_passed"] is True
        assert len(captured["checks"]) == 6

    def test_replay_loads_captured_data(self, tmp_path):
        capture_path = tmp_path / "test_fp_replay.json"
        poc.capture_fingerprint(str(capture_path))
        random.seed(999)
        replayed = poc.replay_fingerprint(str(capture_path))
        assert replayed["all_passed"] is True
        assert "clock_drift" in replayed["checks"]

    def test_replayed_fingerprint_accepted_by_fleet_system(self, tmp_path):
        """Server accepts replayed fingerprint without question."""
        db = sqlite3.connect(":memory:")
        fleet.ensure_schema(db)

        capture_path = tmp_path / "test_fp_fleet.json"
        captured = poc.capture_fingerprint(str(capture_path))
        random.seed(42)
        replayed = poc.replay_fingerprint(str(capture_path))

        # Record the replayed fingerprint as if from a different miner
        fleet.record_fleet_signals_from_request(
            db, miner="attacker-vm", epoch=100,
            ip_address="10.0.0.1",
            attest_ts=50000,
            fingerprint=replayed,
        )

        scores = fleet.compute_fleet_scores(db, 100)
        # Single miner — no fleet detection fires
        assert "attacker-vm" in scores or len(scores) == 0
        # The point: NO verification step rejected the replay

    def test_replay_with_jitter_produces_unique_values(self, tmp_path):
        """Replayed fingerprints can be jittered to avoid exact-match detection."""
        capture_path = tmp_path / "test_fp_jitter.json"
        poc.capture_fingerprint(str(capture_path))
        replays = []
        for seed in range(5):
            random.seed(seed)
            r = poc.replay_fingerprint(str(capture_path))
            replays.append(r["checks"]["clock_drift"]["data"]["cv"])

        # Each replay has slightly different CV due to jitter
        unique_cvs = set(round(cv, 6) for cv in replays)
        assert len(unique_cvs) >= 3, "Jittered replays should produce varied CVs"


class TestClockDriftSpoofing:
    """Attack 2: Forge clock drift CV to any desired value."""

    def test_spoof_produces_valid_result(self):
        random.seed(42)
        result = poc.spoof_clock_drift(target_cv=0.025)
        assert result["passed"] is True
        assert result["data"]["cv"] > 0.0001

    @pytest.mark.parametrize("target_cv", [0.010, 0.025, 0.040, 0.060, 0.100])
    def test_spoof_approximates_target_cv(self, target_cv):
        random.seed(42)
        result = poc.spoof_clock_drift(target_cv=target_cv, samples=1000)
        actual = result["data"]["cv"]
        # Within 50% of target (statistical process)
        assert abs(actual - target_cv) < target_cv * 0.5

    def test_spoof_passes_minimum_checks(self):
        """Spoofed values pass both cv > 0.0001 and drift_stdev > 0."""
        random.seed(42)
        result = poc.spoof_clock_drift(target_cv=0.025)
        assert result["data"]["cv"] > 0.0001
        assert result["data"]["drift_stdev"] > 0

    def test_spoof_different_seeds_produce_different_values(self):
        results = []
        for seed in range(5):
            random.seed(seed)
            r = poc.spoof_clock_drift(target_cv=0.025)
            results.append(r["data"]["cv"])
        unique = set(round(v, 6) for v in results)
        assert len(unique) >= 3


class TestAntiEmulationBypass:
    """Attack 3: Bypass VM detection checks."""

    def test_bypass_returns_techniques(self):
        bypass = poc.bypass_anti_emulation_techniques()
        assert "techniques" in bypass
        assert len(bypass["techniques"]) >= 4

    def test_forged_result_passes(self):
        bypass = poc.bypass_anti_emulation_techniques()
        assert bypass["forged_result"]["passed"] is True
        assert bypass["forged_result"]["data"]["vm_indicators"] == []

    def test_all_techniques_documented(self):
        bypass = poc.bypass_anti_emulation_techniques()
        required = {"dmi_masking", "metadata_blocking", "cpuid_masking", "dmesg_filtering"}
        assert required.issubset(set(bypass["techniques"].keys()))

    def test_techniques_have_commands(self):
        bypass = poc.bypass_anti_emulation_techniques()
        for name, tech in bypass["techniques"].items():
            assert "commands" in tech, f"Missing commands for {name}"
            assert len(tech["commands"]) > 0


class TestCompleteSpoofedFingerprint:
    """Combined: Full spoofed fingerprint passes all checks."""

    def test_all_checks_present(self):
        random.seed(42)
        fp = poc.build_complete_spoofed_fingerprint()
        expected_checks = {
            "clock_drift", "cache_timing", "simd_identity",
            "thermal_drift", "instruction_jitter", "anti_emulation",
        }
        assert set(fp["checks"].keys()) == expected_checks

    def test_all_checks_pass(self):
        random.seed(42)
        fp = poc.build_complete_spoofed_fingerprint()
        assert fp["all_passed"] is True
        for name, check in fp["checks"].items():
            assert check.get("passed", False), f"Check {name} should pass"

    def test_spoofed_accepted_by_fleet_system(self):
        """Fleet system accepts completely spoofed fingerprint."""
        db = sqlite3.connect(":memory:")
        fleet.ensure_schema(db)
        random.seed(42)
        spoofed = poc.build_complete_spoofed_fingerprint()

        fleet.record_fleet_signals_from_request(
            db, miner="spoofed-vm-miner", epoch=200,
            ip_address="192.168.100.1",
            attest_ts=60000,
            fingerprint=spoofed,
        )

        scores = fleet.compute_fleet_scores(db, 200)
        # System accepted the fingerprint — no error, no rejection


class TestArchitecturalFlaw:
    """Demonstrates the fundamental trust model flaw."""

    def test_no_challenge_response_in_api(self):
        """record_fleet_signals_from_request() trusts fingerprint dict blindly."""
        import inspect
        sig = inspect.signature(fleet.record_fleet_signals_from_request)
        params = list(sig.parameters.keys())
        # The function takes 'fingerprint' as a raw dict — no nonce, no challenge
        assert "fingerprint" in params
        # No 'challenge', 'nonce', or 'signature' parameter
        assert "challenge" not in params
        assert "nonce" not in params
        assert "signature" not in params

    def test_fingerprint_is_raw_dict(self):
        """Fingerprint is accepted as plain dict, not a signed/verified object."""
        db = sqlite3.connect(":memory:")
        fleet.ensure_schema(db)

        # Can pass literally anything as fingerprint
        fleet.record_fleet_signals_from_request(
            db, miner="test", epoch=1,
            ip_address="1.2.3.4",
            attest_ts=1000,
            fingerprint={"checks": {"fake": {"passed": True}}, "all_passed": True},
        )
        # No validation error — system trusts the client completely
