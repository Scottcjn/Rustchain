#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""The Power Mac G5 was rejected on every attestation, and my first fix missed.

The rejection was `claims g5 but lacks PowerPC cache profile`. The obvious
reading was that a 970FX has no L3, so requiring `l3_l2_ratio` rejected it. That
was wrong, and only a diagnostic log line showed why. The live machine reports:

    l2_l1=0.801  l3_l2=1.062  hierarchy=None  arch=None

`l3_l2` passes. **`l2_l1` is 0.801** — the client measured L2 as *faster than
L1*, which no real silicon does.

The Mac client walks a Python bytearray at fixed x86-shaped sizes
(8K/128K/4M). On a 2005 PowerPC 970 those accesses are interpreter-bound, so
the ratio is interpreter noise rather than a cache hierarchy. The machine
cannot produce this measurement through this client at all.

Reaching that check means `_has_powerpc_simd_evidence` already passed, so
AltiVec/VSX has proven the architecture. A physically impossible ratio is
therefore treated as unmeasured, not as a lie. A payload with no cache
evidence at all is still rejected.
"""

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.path.join(ROOT, "node")
sys.path.insert(0, NODE)
os.environ.setdefault("RC_ADMIN_KEY", "t" * 64)

_spec = importlib.util.spec_from_file_location(
    "rc_node_g5", os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")
)
MOD = importlib.util.module_from_spec(_spec)
sys.modules["rc_node_g5"] = MOD
_spec.loader.exec_module(MOD)


class DegenerateDetectionTest(unittest.TestCase):

    def test_the_live_g5_ratio_is_recognised_as_noise(self):
        """The exact value observed on g5-selena-179."""
        self.assertTrue(MOD._cache_measurement_is_degenerate(
            {"l2_l1_ratio": 0.801, "l3_l2_ratio": 1.062}))

    def test_a_sane_hierarchy_is_not_degenerate(self):
        for ratio in (1.0, 1.05, 2.0, 3.2, 12.0):
            self.assertFalse(MOD._cache_measurement_is_degenerate(
                {"l2_l1_ratio": ratio}), ratio)

    def test_absent_or_zero_is_not_degenerate(self):
        """Missing evidence must stay a failure, not become an excuse."""
        self.assertFalse(MOD._cache_measurement_is_degenerate({}))
        self.assertFalse(MOD._cache_measurement_is_degenerate({"l2_l1_ratio": 0.0}))
        self.assertFalse(MOD._cache_measurement_is_degenerate(None))

    def test_junk_values_do_not_raise(self):
        for junk in ({"l2_l1_ratio": "fast"}, {"l2_l1_ratio": None},
                     {"l2_l1_ratio": []}, "notadict", 42):
            self.assertIsInstance(MOD._cache_measurement_is_degenerate(junk), bool)


class G5EndToEndTest(unittest.TestCase):
    """The real payload shape, through validate_fingerprint_data."""

    def _g5(self, cache_data):
        return {"checks": {
            "clock_drift": {"passed": True, "data": {"cv": 0.12, "samples": 500}},
            "cache_timing": {"passed": True, "data": cache_data},
            "simd_identity": {"passed": True, "data": {"has_altivec": True,
                                                       "altivec": True}},
            "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
        }}

    def test_the_live_g5_payload_is_accepted(self):
        """l2_l1=0.801 l3_l2=1.062 — exactly what production rejected."""
        ok, reason = MOD.validate_fingerprint_data(
            self._g5({"l1_ns": 120.0, "l2_ns": 96.1, "l3_ns": 102.1,
                      "l2_l1_ratio": 0.801, "l3_l2_ratio": 1.062}),
            claimed_device={"arch": "g5", "family": "PowerPC",
                            "cpu": "PowerPC 970FX"})
        self.assertTrue(ok, f"the live G5 is still rejected: {reason}")

    def test_a_g5_with_a_sane_hierarchy_still_passes(self):
        ok, reason = MOD.validate_fingerprint_data(
            self._g5({"l2_l1_ratio": 3.2, "l3_l2_ratio": 1.4}),
            claimed_device={"arch": "g5", "family": "PowerPC",
                            "cpu": "PowerPC 970FX"})
        self.assertTrue(ok, reason)

    def test_no_cache_evidence_at_all_is_still_rejected(self):
        """The excuse is for an uninformative measurement, not a missing one."""
        ok, reason = MOD.validate_fingerprint_data(
            self._g5({}),
            claimed_device={"arch": "g5", "family": "PowerPC",
                            "cpu": "PowerPC 970FX"})
        self.assertFalse(ok)
        self.assertIn("cache", reason)

    def test_x86_simd_still_vetoes_a_powerpc_claim(self):
        """The SIMD gate is the real proof and must keep biting."""
        fp = self._g5({"l2_l1_ratio": 0.801})
        fp["checks"]["simd_identity"] = {"passed": True,
                                         "data": {"x86_features": ["sse2", "avx"]}}
        ok, reason = MOD.validate_fingerprint_data(
            fp, claimed_device={"arch": "g5", "family": "PowerPC",
                                "cpu": "PowerPC 970FX"})
        self.assertFalse(ok)
        self.assertIn("x86", reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
