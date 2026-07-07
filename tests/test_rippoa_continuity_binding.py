#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests for the RIP-PoA continuity binding reference contract."""

import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.rippoa_continuity_binding import (
    ContinuityReading,
    continuity_commitment,
    evaluate_continuity,
    hardware_binding_continuity_evidence,
)


def _reading(ppm=-40.125, **overrides):
    data = {
        "arch": "x86_64",
        "probe": "rdtsc_raw",
        "ppm": ppm,
        "temperature_c": 43.2,
        "duration_minutes": 45.0,
        "samples": 240,
        "source": "macbookair7,2-lab",
    }
    data.update(overrides)
    return ContinuityReading(**data)


class TestRipPoaContinuityBinding(unittest.TestCase):
    def test_ppm_delta_inside_tolerance_is_same_box_continuity_only(self):
        result = evaluate_continuity(_reading(), _reading(ppm=-40.18))

        self.assertTrue(result["same_box"])
        self.assertEqual(result["reason"], "within_tolerance")
        self.assertFalse(result["identity_claim"])
        self.assertLess(result["delta_ppm"], 0.30)

    def test_ppm_delta_outside_tolerance_flags_possible_hardware_swap(self):
        result = evaluate_continuity(_reading(), _reading(ppm=-39.1))

        self.assertFalse(result["same_box"])
        self.assertEqual(result["reason"], "possible_hardware_swap")
        self.assertFalse(result["identity_claim"])

    def test_kernel_calibrated_probe_is_rejected(self):
        result = evaluate_continuity(
            _reading(probe="mach_absolute_time"),
            _reading(probe="mach_absolute_time"),
        )

        self.assertFalse(result["same_box"])
        self.assertEqual(result["reason"], "invalid_baseline:probe_not_raw_rdtsc")

    def test_short_or_sparse_baselines_are_not_accepted(self):
        short = evaluate_continuity(_reading(duration_minutes=5), _reading())
        sparse = evaluate_continuity(_reading(samples=20), _reading())

        self.assertEqual(short["reason"], "invalid_baseline:baseline_too_short")
        self.assertEqual(sparse["reason"], "invalid_baseline:insufficient_samples")

    def test_continuity_commitment_is_stable_under_extra_precision(self):
        first = _reading(ppm=-40.1234564, temperature_c=43.2004)
        second = _reading(ppm=-40.1234563, temperature_c=43.20049)

        self.assertEqual(continuity_commitment(first), continuity_commitment(second))

    def test_hardware_binding_keeps_assigned_id_authoritative(self):
        evidence = hardware_binding_continuity_evidence(
            "miner-alpha",
            "io-platform-uuid+serial+mac",
            _reading(),
        )

        self.assertEqual(evidence["identity_source"], "assigned_hardware_id")
        self.assertEqual(evidence["continuity"]["probe"], "rdtsc_raw")
        self.assertIn("per_unit_physical_identity", evidence["non_goals"])
        self.assertRegex(evidence["continuity_commitment"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
