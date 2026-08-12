#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""The temporal consistency score must reach the reward, not just the log.

`validate_temporal_consistency` has always measured a miner against its own
measurement history and detected the two shapes a forger falls into:

  frozen_profile  rel_var < 0.01   the same value replayed every epoch
  noisy_profile   rel_var > 0.8    an RNG with no physical model behind it

Its score was then discarded. The only consumer was:

    # Issue #19 temporal consistency only sets a review flag (no hard-fail).
    if temporal_review.get("review_flag"):
        app.logger.warning(...)

So a miner contradicting its own history collected the full antiquity premium
anyway. These tests pin the score to the weight.

What is deliberately NOT done here: nothing is pushed below baseline. Only the
bonus above 1.0 is at risk, because the bonus is the only thing worth forging
and a false positive should cost a premium, never someone's participation.
"""

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.path.join(ROOT, "node")
sys.path.insert(0, NODE)

_spec = importlib.util.spec_from_file_location(
    "rc_node_tc", os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")
)
MOD = importlib.util.module_from_spec(_spec)
sys.modules["rc_node_tc"] = MOD
_spec.loader.exec_module(MOD)

apply_gate = MOD.apply_temporal_consistency_to_weight
validate = MOD.validate_temporal_consistency


def _profile(clock, thermal, jitter, cache):
    return {
        "clock_drift_cv": clock,
        "thermal_variance": thermal,
        "jitter_cv": jitter,
        "cache_hierarchy_ratio": cache,
    }


def _sequence(profiles):
    return [{"ts": 1000 + i * 600, "profile": p} for i, p in enumerate(profiles)]


class GateArithmeticTest(unittest.TestCase):

    def test_baseline_and_below_is_never_reduced(self):
        """A modern miner at 0.8x is untouched, whatever its history says."""
        bad = {"score": 0.2, "reason": "temporal_review_required"}
        self.assertEqual(apply_gate(0.8, bad), 0.8)
        self.assertEqual(apply_gate(1.0, bad), 1.0)
        self.assertEqual(apply_gate(0.0005, bad), 0.0005)

    def test_a_consistent_miner_keeps_its_full_bonus(self):
        good = {"score": 1.0, "reason": "temporal_consistent"}
        self.assertAlmostEqual(apply_gate(2.5, good), 2.5)

    def test_an_inconsistent_miner_loses_bonus_not_baseline(self):
        """Worst case lands at baseline, never below it."""
        worst = {"score": 0.0, "reason": "temporal_review_required"}
        self.assertAlmostEqual(apply_gate(2.5, worst), 1.0)
        self.assertAlmostEqual(apply_gate(4.0, worst), 1.0)

    def test_partial_score_scales_only_the_bonus_portion(self):
        half = {"score": 0.5, "reason": "temporal_review_required"}
        # 1.0 + (2.5 - 1.0) * 0.5
        self.assertAlmostEqual(apply_gate(2.5, half), 1.75)

    def test_unverified_history_withholds_half_the_bonus(self):
        """Cold start: not trusted with the premium, not punished either."""
        fresh = {"score": 1.0, "reason": "insufficient_history"}
        self.assertAlmostEqual(
            apply_gate(2.5, fresh),
            1.0 + 1.5 * MOD.TEMPORAL_UNVERIFIED_BONUS_FRACTION,
        )
        self.assertGreater(apply_gate(2.5, fresh), 1.0, "honest newcomers keep a premium")
        self.assertLess(apply_gate(2.5, fresh), 2.5, "a fresh identity is not fully trusted")

    def test_a_fresh_identity_is_no_longer_scored_perfect(self):
        """The old shape returned score 1.0 for no history, so a brand new
        identity — the cheapest thing a forger can make — was the most
        trusted. The gate must not reproduce that."""
        fresh = validate([])
        self.assertEqual(fresh["reason"], "insufficient_history")
        self.assertLess(apply_gate(2.5, fresh), 2.5)

    def test_malformed_review_does_not_crash_or_inflate(self):
        for junk in (None, {}, {"score": "abc"}, {"score": None}, []):
            self.assertLessEqual(apply_gate(2.5, junk), 2.5)
        self.assertEqual(apply_gate("not-a-number", {"score": 1.0}), "not-a-number")

    def test_score_is_clamped_so_a_bad_value_cannot_inflate_weight(self):
        self.assertAlmostEqual(apply_gate(2.5, {"score": 9.0, "reason": "x"}), 2.5)
        self.assertAlmostEqual(apply_gate(2.5, {"score": -5.0, "reason": "x"}), 1.0)


class ForgerSignatureTest(unittest.TestCase):
    """The two shapes a forged history takes, end to end."""

    def test_replayed_constant_profile_loses_most_of_the_bonus(self):
        """A payload measured once and replayed has near-zero variance."""
        seq = _sequence([_profile(0.05, 3.0, 0.02, 4.0)] * 8)
        review = validate(seq)
        self.assertIn("frozen_profile:clock_drift_cv", review["flags"])
        self.assertTrue(review["review_flag"])
        gated = apply_gate(2.5, review)
        self.assertLess(gated, 1.6, f"frozen profile still earned {gated}")
        self.assertGreaterEqual(gated, 1.0)

    def test_rng_without_a_physical_model_loses_bonus(self):
        """Wild swings are as unphysical as no swings at all."""
        seq = _sequence([
            _profile(0.002, 0.2, 0.001, 1.2),
            _profile(0.30, 20.0, 0.45, 18.0),
            _profile(0.004, 0.4, 0.002, 1.4),
            _profile(0.28, 22.0, 0.40, 17.0),
            _profile(0.003, 0.3, 0.0015, 1.3),
        ])
        review = validate(seq)
        self.assertTrue(review["review_flag"], review)
        self.assertLess(apply_gate(2.5, review), 2.5)

    def test_real_hardware_drift_keeps_its_bonus(self):
        """Small, physical variation must not be mistaken for either failure.

        This is the false-positive guard: an honest G4 whose readings wander a
        few percent has to keep earning 2.5x, or the control repeats the very
        mistake it was built to fix, firing only on honest miners.
        """
        seq = _sequence([
            _profile(0.050, 3.00, 0.020, 4.00),
            _profile(0.053, 3.15, 0.021, 4.10),
            _profile(0.048, 2.90, 0.019, 3.95),
            _profile(0.055, 3.30, 0.022, 4.20),
            _profile(0.051, 3.05, 0.020, 4.05),
            _profile(0.049, 2.95, 0.0205, 3.98),
        ])
        review = validate(seq)
        self.assertFalse(review["review_flag"], f"honest drift flagged: {review['flags']}")
        self.assertAlmostEqual(apply_gate(2.5, review), 2.5)


class GateIsActuallyWiredTest(unittest.TestCase):
    """The helper being correct is worth nothing if nobody calls it.

    That is the exact failure this whole change fixes: the score was computed
    correctly for months and never reached the reward. A unit test on the
    helper alone would have passed the entire time. So assert the call sites.
    """

    SRC = os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")

    def test_both_weight_paths_apply_the_gate(self):
        import ast
        tree = ast.parse(open(self.SRC).read())
        calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "apply_temporal_consistency_to_weight"
        ]
        self.assertGreaterEqual(
            len(calls), 2,
            "expected the gate on both the attestation reward path and the "
            "epoch enroll path; enrollment is what actually sets epoch weight, "
            "so gating only attestation would be cosmetic",
        )

    def test_no_weight_assignment_from_hardware_weights_escapes_the_gate(self):
        """Every HARDWARE_WEIGHTS lookup that sets hw_weight must be followed
        by the gate, or a third weight path could quietly reintroduce the
        ungated premium."""
        src = open(self.SRC).read()
        assignments = src.count("hw_weight = HARDWARE_WEIGHTS")
        gated = src.count("apply_temporal_consistency_to_weight(hw_weight")
        self.assertGreaterEqual(
            gated, assignments,
            f"{assignments} hw_weight assignments but only {gated} gated",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
