#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Unit tests for _parse_linux_cpuinfo in fingerprint_checks.py."""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "node"))
from fingerprint_checks import _parse_linux_cpuinfo


class TestParseLinuxCpuinfo(unittest.TestCase):

    def test_parses_x86_cpuinfo(self):
        text = (
            "processor       : 0\n"
            "model name      : Intel(R) Core(TM) i7-4770\n"
            "cpu family      : 6\n"
            "model           : 60\n"
            "stepping        : 3\n"
            "flags           : fpu vme de pse tsc msr pae mce\n"
        )
        result = _parse_linux_cpuinfo(text)
        self.assertEqual(result.get("cpu_model"), "Intel(R) Core(TM) i7-4770")
        self.assertEqual(result.get("cpu_family"), "6")
        self.assertEqual(result.get("model"), "60")
        self.assertEqual(result.get("stepping"), "3")
        self.assertEqual(result.get("flags"), "fpu vme de pse tsc msr pae mce")
        self.assertEqual(result.get("processor"), "0")

    def test_parses_arm_cpuinfo(self):
        text = (
            "processor       : 0\n"
            "Hardware        : BCM2835\n"
            "Features        : half thumb fastmult vfp edsp neon vfpv3\n"
        )
        result = _parse_linux_cpuinfo(text)
        self.assertEqual(result.get("hardware"), "BCM2835")
        self.assertEqual(result.get("flags"), "half thumb fastmult vfp edsp neon vfpv3")

    def test_parses_ppc_cpuinfo(self):
        text = "cpu             : POWER9, altivec supported\n"
        result = _parse_linux_cpuinfo(text)
        self.assertEqual(result.get("cpu_model"), "POWER9, altivec supported")

    def test_empty_input_returns_empty_dict(self):
        self.assertEqual(_parse_linux_cpuinfo(""), {})
        self.assertEqual(_parse_linux_cpuinfo("\n\n\n"), {})

    def test_lines_without_colon_are_skiped(self):
        text = "no colon here\nmodel name : AMD Ryzen 7\n"
        result = _parse_linux_cpuinfo(text)
        self.assertEqual(result.get("cpu_model"), "AMD Ryzen 7")

    def test_first_seen_value_is_retained(self):
        text = (
            "processor       : 0\n"
            "processor       : 1\n"
            "model name      : First CPU\n"
            "model name      : Second CPU\n"
        )
        result = _parse_linux_cpuinfo(text)
        self.assertEqual(result.get("processor"), "0")
        self.assertEqual(result.get("cpu_model"), "First CPU")

    def test_empty_values_are_ignored(self):
        text = "model name :   \nHardware\t:\n"
        result = _parse_linux_cpuinfo(text)
        self.assertEqual(result, {})

    def test_tab_separated_kv_pairs(self):
        text = "processor\t:\t0\nmodel name\t: Test CPU\n"
        result = _parse_linux_cpuinfo(text)
        self.assertEqual(result.get("cpu_model"), "Test CPU")


if __name__ == "__main__":
    unittest.main()
