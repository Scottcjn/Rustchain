#!/usr/bin/env python3
import unittest

from temporal_entropy_validation import validate_temporal_consistency


class TemporalEntropyValidationTests(unittest.TestCase):
    def test_frozen_profile_detected(self):
        rows = [
            {"clock_cv": 0.0100, "entropy_score": 0.5000, "thermal_score": 0.0200, "simd_identity": "g4"},
            {"clock_cv": 0.0100, "entropy_score": 0.5000, "thermal_score": 0.0200, "simd_identity": "g4"},
            {"clock_cv": 0.0100, "entropy_score": 0.5000, "thermal_score": 0.0200, "simd_identity": "g4"},
        ]
        current = rows[-1]
        result = validate_temporal_consistency(rows, current)
        self.assertTrue(result["review_required"])
        self.assertIn("frozen_profile", result["reasons"])

    def test_noisy_profile_detected(self):
        rows = [
            {"clock_cv": 0.001, "entropy_score": 0.20, "thermal_score": 0.01, "simd_identity": "g4"},
            {"clock_cv": 0.090, "entropy_score": 0.95, "thermal_score": 0.70, "simd_identity": "g4"},
            {"clock_cv": 0.002, "entropy_score": 0.15, "thermal_score": 0.02, "simd_identity": "g4"},
            {"clock_cv": 0.120, "entropy_score": 0.99, "thermal_score": 0.80, "simd_identity": "g4"},
        ]
        current = rows[-1]
        result = validate_temporal_consistency(rows, current)
        self.assertTrue(result["review_required"])
        self.assertIn("noisy_profile", result["reasons"])

    def test_expected_drift_is_ok(self):
        rows = [
            {"clock_cv": 0.020, "entropy_score": 0.55, "thermal_score": 0.10, "simd_identity": "g5"},
            {"clock_cv": 0.022, "entropy_score": 0.58, "thermal_score": 0.11, "simd_identity": "g5"},
            {"clock_cv": 0.024, "entropy_score": 0.57, "thermal_score": 0.12, "simd_identity": "g5"},
            {"clock_cv": 0.026, "entropy_score": 0.59, "thermal_score": 0.13, "simd_identity": "g5"},
        ]
        current = rows[-1]
        result = validate_temporal_consistency(rows, current)
        self.assertIn(result["status"], ("ok", "drift_warning"))
        self.assertGreater(result["consistency_score"], 0.5)


if __name__ == "__main__":
    unittest.main()
