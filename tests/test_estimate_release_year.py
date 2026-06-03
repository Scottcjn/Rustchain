#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Unit tests for _estimate_release_year in fingerprint_checks.py."""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "node"))
from fingerprint_checks import _estimate_release_year


class TestEstimateReleaseYear(unittest.TestCase):

    def test_intel_core_i7(self):
        year, details = _estimate_release_year("Intel(R) Core(TM) i7-4770 CPU @ 3.40GHz")
        self.assertEqual(year, 2013)
        self.assertIn("intel_core", details["matched"])

    def test_intel_core_i9(self):
        year, details = _estimate_release_year("Intel Core i9-13900K")
        self.assertEqual(year, 2022)
        self.assertIn("intel_core", details["matched"])

    def test_apple_m1(self):
        year, details = _estimate_release_year("Apple M1")
        self.assertEqual(year, 2020)
        self.assertEqual(details["matched"], "apple_m1")

    def test_apple_m3(self):
        year, details = _estimate_release_year("Apple M3 Pro")
        self.assertEqual(year, 2023)
        self.assertEqual(details["matched"], "apple_m3")

    def test_amd_ryzen(self):
        year, details = _estimate_release_year("AMD Ryzen 7 5800X")
        self.assertEqual(year, 2020)
        self.assertIn("amd_ryzen", details["matched"])

    def test_vintage_powerpc(self):
        year, details = _estimate_release_year("PowerPC G4 7450")
        self.assertEqual(year, 1999)
        self.assertIn("ppc_g4", details["matched"])

    def test_sparc(self):
        year, details = _estimate_release_year("UltraSPARC III")
        self.assertEqual(year, 1995)
        self.assertIn("sparc", details["matched"])

    def test_unknown_returns_none(self):
        year, details = _estimate_release_year("Some Unknown CPU 123")
        self.assertIsNone(year)
        self.assertIsNone(details.get("matched"))

    def test_empty_string(self):
        year, details = _estimate_release_year("")
        self.assertIsNone(year)

    def test_none_input(self):
        year, details = _estimate_release_year(None)
        self.assertIsNone(year)


if __name__ == "__main__":
    unittest.main()
