#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Two real vintage machines were being penalised for what they are.

Both found by reading production enrollment weights after a deploy, not by
reading code.

**Power Mac G5.** Rejected on every attestation with "claims g5 but lacks
PowerPC cache profile". The check required `l2_l1_ratio >= 1.05 AND
l3_l2_ratio >= 1.05`, but a PowerPC 970/970FX has L1 and L2 and **no L3at
all**. The machine was failing for not having a cache level Apple never put in
it. An absent L3 is a fact about the silicon, not a missing measurement.

**Cobalt Qube 3 (K6-2).** Enrolled at 0.4667. Classified `x86/retro` (1.4x) but
its cut-down client emits only `clock_drift` and `anti_emulation`, so it scored
2 of 6 and 1.4 x 0.333 = 0.4667 — below a modern miner, for being unable to run
four checks its hardware cannot perform.

Same shape as everything else in this area: a control that fires on honest
hardware because it assumes a capability the hardware does not have.
"""

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.path.join(ROOT, "node")
sys.path.insert(0, NODE)
os.environ.setdefault("RC_ADMIN_KEY", "t" * 64)

_spec = importlib.util.spec_from_file_location(
    "rc_node_vin", os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")
)
MOD = importlib.util.module_from_spec(_spec)
sys.modules["rc_node_vin"] = MOD
_spec.loader.exec_module(MOD)


def _cache(**data):
    return {"checks": {"cache_timing": {"passed": True, "data": data}}}


class PowerPCCacheProfileTest(unittest.TestCase):
    """A two-level hierarchy is valid PowerPC."""

    def test_g5_with_no_l3_is_accepted(self):
        """The 970FX has L1+L2 only. This is the live rejection."""
        self.assertTrue(MOD._has_powerpc_cache_profile(
            _cache(l2_l1_ratio=3.2, l3_l2_ratio=0.0)))

    def test_g5_with_l3_key_absent_entirely_is_accepted(self):
        self.assertTrue(MOD._has_powerpc_cache_profile(_cache(l2_l1_ratio=3.2)))

    def test_three_level_powerpc_still_accepted(self):
        self.assertTrue(MOD._has_powerpc_cache_profile(
            _cache(l2_l1_ratio=2.0, l3_l2_ratio=1.5)))

    def test_flat_power8_hierarchy_still_accepted(self):
        """POWER8's unified caches read flat; that path must not regress."""
        self.assertTrue(MOD._has_powerpc_cache_profile(_cache(hierarchy_ratio=1.4)))

    def test_explicit_arch_tag_still_wins(self):
        self.assertTrue(MOD._has_powerpc_cache_profile(
            {"checks": {"cache_timing": {"passed": True, "data": {"arch": "ppc64le"}}}}))

    def test_no_cache_evidence_at_all_is_still_rejected(self):
        """Relaxing L3 must not become 'accept anything'."""
        self.assertFalse(MOD._has_powerpc_cache_profile(_cache()))

    def test_an_inverted_hierarchy_is_still_rejected(self):
        """L2 faster than L1 is not a cache hierarchy, it is a fabrication."""
        self.assertFalse(MOD._has_powerpc_cache_profile(
            _cache(l2_l1_ratio=0.4, l3_l2_ratio=0.0)))

    def test_a_negative_l3_ratio_does_not_slip_through(self):
        self.assertFalse(MOD._has_powerpc_cache_profile(
            _cache(l2_l1_ratio=0.9, l3_l2_ratio=-5.0)))


class RetroCapabilityClassTest(unittest.TestCase):
    """The Qube's missing checks are structural, not failures."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.conn = sqlite3.connect(self.tmp.name)
        self.conn.row_factory = sqlite3.Row
        # exactly what the live Cobalt Qube 3 sends
        self.qube_fp = {"checks": {
            "clock_drift": {"passed": True, "data": {"cv": 0.002056, "samples": 500}},
            "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
        }}

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmp.name)

    def test_retro_is_a_capability_limited_class(self):
        self.assertIn("retro", MOD.MICRO_LIMITED_ARCHES)

    def test_the_qube_recovers_its_full_retro_tier(self):
        r = MOD.evaluate_rotating_fingerprint_checks(
            self.conn, 0, self.qube_fp, device_arch="retro", micro_accepted=True)
        self.assertEqual(r["measured_total"], 2)
        self.assertEqual(sorted(r["passed_active_checks"]),
                         ["anti_emulation", "clock_drift"])
        self.assertEqual(r["active_ratio"], 1.0)
        self.assertAlmostEqual(1.4 * r["active_ratio"], 1.4,
                               msg="the Qube earned 0.4667 before this fix")

    def test_a_modern_miner_gets_no_such_excuse(self):
        """The identical sparse payload from capable hardware still scores low."""
        r = MOD.evaluate_rotating_fingerprint_checks(
            self.conn, 0, self.qube_fp, device_arch="modern", micro_accepted=False)
        self.assertEqual(r["unmeasured_active_checks"], [])
        self.assertLess(r["active_ratio"], 0.5)

    def test_a_retro_claim_still_cannot_launder_a_real_failure(self):
        fp = {"checks": {
            "clock_drift": {"passed": True, "data": {"cv": 0.002, "samples": 500}},
            "anti_emulation": {"passed": False, "data": {"vm_indicators": ["qemu"]}},
        }}
        r = MOD.evaluate_rotating_fingerprint_checks(
            self.conn, 0, fp, device_arch="retro", micro_accepted=True)
        self.assertIn("anti_emulation", r["failed_active_checks"])
        self.assertEqual(r["active_ratio"], 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
