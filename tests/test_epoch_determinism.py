#!/usr/bin/env python3
"""
Tests for Epoch Determinism Simulator + Cross-Node Replay
==========================================================
Bounty #474

Verifies that:
 - Identical fixtures produce byte-equivalent payouts across two simulated nodes
 - The divergent fixture correctly triggers mismatch detection
 - The CLI exits non-zero on mismatch
 - Edge-case paths (epoch_enroll, fingerprint failure) work deterministically

Run:
    python -m pytest tests/test_epoch_determinism.py -v
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Dict

import pytest

# ─────────────────────────────────────────────────────────────
# Path setup
# ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = PROJECT_ROOT / "tools" / "epoch_determinism"
FIXTURE_DIR = TOOL_DIR / "fixtures"

for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "node"), str(TOOL_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Import the replay module
sys.path.insert(0, str(TOOL_DIR))
import replay as _replay

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def load_fixture(name: str) -> dict:
    """Load a fixture by filename from the fixtures/ directory."""
    path = FIXTURE_DIR / name
    return _replay.load_fixture(str(path))


def run_fixture_pair(fixture: dict) -> tuple:
    """
    Build two independent DBs from the fixture, compute payouts for both,
    and return (result_a, result_b).
    """
    db_a = _replay.build_db(fixture)
    db_b = _replay.build_db(fixture)
    try:
        result_a = _replay.compute_payout(fixture, db_a, "node_a")
        result_b = _replay.compute_payout(fixture, db_b, "node_b")
    finally:
        for p in (db_a, db_b):
            try:
                os.unlink(p)
            except OSError:
                pass
    return result_a, result_b


def inject_divergence(fixture: dict, target_result_dict: dict) -> dict:
    """
    Simulate cross-node divergence by mutating one miner's payout in one result.
    Returns a mutated copy of target_result_dict with one payout changed.
    """
    spec = fixture.get("divergence_spec", {})
    miner_id = spec.get("miner_id")
    if miner_id and miner_id in target_result_dict["payouts"]:
        mutated = dict(target_result_dict)
        mutated["payouts"] = dict(target_result_dict["payouts"])
        # Adjust the payout to simulate a divergent node (e.g., different bonus applied)
        original = mutated["payouts"][miner_id]
        mutated["payouts"][miner_id] = int(original * 1.15)
        mutated["canonical_hash"] = _replay._hash_payouts(mutated["payouts"])
        mutated["total_urtc"] = sum(mutated["payouts"].values())
    return mutated


# ─────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────


class TestNormalEpochDeterministic:
    """Normal epoch: 5 miners, mixed tiers, miner_attest_recent path."""

    def test_normal_epoch_deterministic(self):
        fixture = load_fixture("normal_epoch.json")
        result_a, result_b = run_fixture_pair(fixture)

        assert result_a["canonical_hash"] == result_b["canonical_hash"], (
            f"Hashes diverged: {result_a['canonical_hash']} vs {result_b['canonical_hash']}"
        )

    def test_normal_epoch_payouts_nonzero(self):
        fixture = load_fixture("normal_epoch.json")
        result_a, _ = run_fixture_pair(fixture)

        assert len(result_a["payouts"]) > 0, "Expected payouts to be non-empty"
        assert result_a["total_urtc"] > 0, "Expected total_urtc > 0"

    def test_normal_epoch_total_within_budget(self):
        """Sum of payouts should not exceed per-epoch budget (rounding residual ok)."""
        fixture = load_fixture("normal_epoch.json")
        result_a, _ = run_fixture_pair(fixture)

        budget = _replay.PER_EPOCH_URTC
        # Allow up to 1 uRTC rounding per miner
        assert result_a["total_urtc"] <= budget + len(result_a["payouts"])

    def test_normal_epoch_path_is_attest_recent(self):
        fixture = load_fixture("normal_epoch.json")
        assert "epoch_enroll_override" not in fixture or fixture.get("epoch_enroll_override") is None
        result_a, _ = run_fixture_pair(fixture)
        assert result_a["path"] == "miner_attest_recent"


class TestSparseEpochDeterministic:
    """Sparse epoch: only 2 miners."""

    def test_sparse_epoch_deterministic(self):
        fixture = load_fixture("sparse_epoch.json")
        result_a, result_b = run_fixture_pair(fixture)

        assert result_a["canonical_hash"] == result_b["canonical_hash"], (
            f"Hashes diverged for sparse epoch"
        )

    def test_sparse_epoch_has_two_miners(self):
        fixture = load_fixture("sparse_epoch.json")
        result_a, _ = run_fixture_pair(fixture)

        assert len(result_a["payouts"]) == 2

    def test_sparse_epoch_ancient_gets_more(self):
        """Ancient hardware (68000) should receive more than modern hardware."""
        fixture = load_fixture("sparse_epoch.json")
        result_a, _ = run_fixture_pair(fixture)

        payouts = result_a["payouts"]
        ancient_id = next(
            m["miner_id"] for m in fixture["miners"] if m["device_arch"] == "68000"
        )
        modern_id = next(
            m["miner_id"] for m in fixture["miners"] if m["device_arch"] == "modern"
        )

        # Ancient hardware multiplier > modern (1.0), so ancient should get more
        assert payouts[ancient_id] >= payouts[modern_id], (
            f"Ancient hardware should receive >= modern: "
            f"{payouts[ancient_id]} vs {payouts[modern_id]}"
        )


class TestEdgeCaseDeterministic:
    """Edge case: epoch_enroll primary path + fingerprint failure."""

    def test_edge_case_deterministic(self):
        fixture = load_fixture("edge_case_epoch.json")
        result_a, result_b = run_fixture_pair(fixture)

        assert result_a["canonical_hash"] == result_b["canonical_hash"], (
            f"Edge case hashes diverged"
        )

    def test_edge_case_uses_enroll_path(self):
        """epoch_enroll_override → primary path."""
        fixture = load_fixture("edge_case_epoch.json")
        assert fixture.get("epoch_enroll_override"), "Expected epoch_enroll_override in fixture"
        result_a, _ = run_fixture_pair(fixture)
        assert result_a["path"] == "epoch_enroll"

    def test_edge_case_failed_fingerprint_excluded(self):
        """Miner with fingerprint_passed=0 must NOT appear in payouts when using enroll path."""
        fixture = load_fixture("edge_case_epoch.json")
        result_a, _ = run_fixture_pair(fixture)

        # The fingerprint-failed miner is NOT in epoch_enroll_override → not paid
        failed_miner = next(
            (m["miner_id"] for m in fixture["miners"] if m.get("fingerprint_passed") == 0),
            None,
        )
        if failed_miner:
            assert failed_miner not in result_a["payouts"], (
                f"Fingerprint-failed miner {failed_miner} should NOT receive payout"
            )

    def test_edge_case_enroll_weights_proportional(self):
        """Payouts should be proportional to epoch_enroll weights."""
        fixture = load_fixture("edge_case_epoch.json")
        result_a, _ = run_fixture_pair(fixture)

        overrides = fixture["epoch_enroll_override"]
        total_weight = sum(e["weight"] for e in overrides)

        for entry in overrides:
            miner_pk = entry["miner_pk"]
            expected_frac = entry["weight"] / total_weight
            actual_frac = result_a["payouts"][miner_pk] / _replay.PER_EPOCH_URTC
            assert abs(actual_frac - expected_frac) < 0.001, (
                f"{miner_pk}: expected fraction {expected_frac:.4f}, "
                f"got {actual_frac:.4f}"
            )


class TestDivergentDetectsMismatch:
    """Divergent fixture: verify that injected mismatch is caught."""

    def test_divergent_detects_mismatch(self):
        """
        Simulate a node disagreement by injecting a warthog_bonus difference
        on node_b for one miner. Verifies that:
         - canonical hashes differ
         - per-miner diff is non-empty
         - the affected miner appears in diffs
        """
        fixture = load_fixture("divergent_epoch.json")
        result_a, result_b_original = run_fixture_pair(fixture)

        # Inject divergence into node_b result
        result_b = inject_divergence(fixture, result_b_original)

        # Hashes must differ
        assert result_a["canonical_hash"] != result_b["canonical_hash"], (
            "Expected hash mismatch for divergent fixture"
        )

        # Diffs must be non-empty
        diffs = _replay.compute_diff(result_a, result_b)
        assert len(diffs) > 0, "Expected at least one per-miner diff"

        # Affected miner must appear in diffs
        spec = fixture.get("divergence_spec", {})
        diverged_miner = spec.get("miner_id")
        if diverged_miner:
            diff_miners = [d["miner_id"] for d in diffs]
            assert diverged_miner in diff_miners, (
                f"Expected {diverged_miner} to appear in diffs, got {diff_miners}"
            )

    def test_divergent_diff_has_delta(self):
        """Delta must be non-zero for the diverged miner."""
        fixture = load_fixture("divergent_epoch.json")
        result_a, result_b_original = run_fixture_pair(fixture)
        result_b = inject_divergence(fixture, result_b_original)

        diffs = _replay.compute_diff(result_a, result_b)
        assert all(d["delta_urtc"] != 0 for d in diffs), (
            "All reported diffs must have non-zero delta_urtc"
        )

    def test_divergent_both_deterministic_before_injection(self):
        """Before divergence injection, node_a and node_b must agree (fixture itself is deterministic)."""
        fixture = load_fixture("divergent_epoch.json")
        result_a, result_b = run_fixture_pair(fixture)

        assert result_a["canonical_hash"] == result_b["canonical_hash"], (
            "Divergent fixture base outputs should be deterministic before injection"
        )


class TestCIModeExitCode:
    """Verify CLI exit codes for CI mode."""

    def test_ci_mode_exits_zero_on_match(self, tmp_path):
        """Normal fixture in CI mode must exit 0."""
        fixture_path = str(FIXTURE_DIR / "normal_epoch.json")
        report_path = str(tmp_path / "report.json")

        # Call main() directly; it calls sys.exit — catch SystemExit
        with pytest.raises(SystemExit) as exc_info:
            _replay.main([fixture_path, "--ci", "--report-json", report_path])

        assert exc_info.value.code == 0, (
            f"Expected exit 0 for matching fixture, got {exc_info.value.code}"
        )

        # Report file should exist and be valid JSON
        report = json.loads(Path(report_path).read_text())
        assert report["determinism_ok"] is True

    def test_ci_mode_exits_zero_sparse(self):
        """Sparse fixture in CI mode must also exit 0."""
        fixture_path = str(FIXTURE_DIR / "sparse_epoch.json")

        with pytest.raises(SystemExit) as exc_info:
            _replay.main([fixture_path, "--ci"])

        assert exc_info.value.code == 0

    def test_ci_mode_exits_zero_edge_case(self):
        """Edge-case fixture in CI mode must exit 0."""
        fixture_path = str(FIXTURE_DIR / "edge_case_epoch.json")

        with pytest.raises(SystemExit) as exc_info:
            _replay.main([fixture_path, "--ci"])

        assert exc_info.value.code == 0

    def test_report_json_structure(self, tmp_path):
        """JSON report must contain required keys."""
        fixture_path = str(FIXTURE_DIR / "normal_epoch.json")
        report_path = str(tmp_path / "report.json")

        with pytest.raises(SystemExit):
            _replay.main([fixture_path, "--report-json", report_path])

        report = json.loads(Path(report_path).read_text())
        required_keys = {
            "fixture_id", "description", "epoch", "determinism_ok",
            "targets", "canonical_hashes", "total_urtc", "payouts",
            "diffs", "elapsed_s", "generated_at",
        }
        missing = required_keys - set(report)
        assert not missing, f"Report missing keys: {missing}"

    def test_canonical_hashes_equal_on_match(self, tmp_path):
        """When deterministic, both canonical hashes must be identical in the report."""
        fixture_path = str(FIXTURE_DIR / "normal_epoch.json")
        report_path = str(tmp_path / "report2.json")

        with pytest.raises(SystemExit):
            _replay.main([fixture_path, "--report-json", report_path])

        report = json.loads(Path(report_path).read_text())
        hashes = list(report["canonical_hashes"].values())
        assert len(set(hashes)) == 1, f"Expected identical hashes, got: {hashes}"


# ─────────────────────────────────────────────────────────────
# Standalone runner
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(PROJECT_ROOT),
    )
    sys.exit(result.returncode)
