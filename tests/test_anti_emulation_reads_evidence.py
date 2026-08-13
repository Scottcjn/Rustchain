#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Anti-emulation must read the evidence, not the client's verdict.

The server held the string "qemu" in `vm_indicators` and never looked at it
unless the VM had already confessed via `passed: false`. Three payloads were
accepted on main:

    {"passed": true,  "data": {"vm_indicators": ["qemu"]}}
    {"passed": true,  "data": {"is_likely_vm": true}}
    {                 "data": {"vm_indicators": ["qemu"]}}   (no verdict at all)

and the only anti-emulation payload rejected was the honest one that reported
`passed: false`. The control fired exclusively on truthful clients — the third
instance of that same inversion found in this codebase, alongside the vintage
zero-reward path and the temporal score that punished only miners who varied.

The third bypass is the `== False` comparison: omitting the key skipped both
branches. `is not True` closes it.

Also covered: the console fleet reports under `emulator_indicators`, which was
not on the evidence whitelist, so Pico bridge miners were rejected with
`anti_emulation_no_evidence` while supplying evidence under a name nobody had
listed. Accepting that key without also content-checking it would have created
a fresh free pass, so both are tested.
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
    "rc_node_ae", os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")
)
MOD = importlib.util.module_from_spec(_spec)
sys.modules["rc_node_ae"] = MOD
_spec.loader.exec_module(MOD)

validate = MOD.validate_fingerprint_data

BASE = {
    "clock_drift": {"passed": True, "data": {"cv": 0.05, "samples": 500}},
    "cache_timing": {"passed": True, "data": {"l2_l1_ratio": 4.0}},
    "simd_identity": {"passed": True, "data": {"x86_features": ["sse2"]}},
}


def _fp(anti_emulation):
    checks = dict(BASE)
    checks["anti_emulation"] = anti_emulation
    return {"checks": checks}


class EvidenceOverridesVerdictTest(unittest.TestCase):

    def test_honest_clean_hardware_still_passes(self):
        ok, reason = validate(
            _fp({"passed": True, "data": {"vm_indicators": []}}),
            claimed_device={"arch": "modern"})
        self.assertTrue(ok, reason)

    def test_claimed_pass_with_vm_indicators_is_rejected(self):
        ok, reason = validate(
            _fp({"passed": True, "data": {"vm_indicators": ["qemu", "hypervisor"]}}),
            claimed_device={"arch": "modern"})
        self.assertFalse(ok, "the server was holding 'qemu' and not looking")
        self.assertTrue(reason.startswith("vm_detected"), reason)

    def test_claimed_pass_with_is_likely_vm_is_rejected(self):
        ok, reason = validate(
            _fp({"passed": True, "data": {"vm_indicators": [], "is_likely_vm": True}}),
            claimed_device={"arch": "modern"})
        self.assertFalse(ok)
        self.assertIn("is_likely_vm", reason)

    def test_omitting_the_verdict_no_longer_skips_both_branches(self):
        """The `== False` bug: no `passed` key sailed through."""
        ok, reason = validate(
            _fp({"data": {"vm_indicators": ["qemu"]}}),
            claimed_device={"arch": "modern"})
        self.assertFalse(ok, reason)

    def test_a_missing_verdict_with_clean_evidence_is_also_rejected(self):
        """No verdict is not a pass, even when the evidence looks clean."""
        ok, reason = validate(
            _fp({"data": {"vm_indicators": [], "paths_checked": ["/proc/cpuinfo"]}}),
            claimed_device={"arch": "modern"})
        self.assertFalse(ok)
        self.assertIn("no_pass_verdict", reason)

    def test_an_honest_vm_is_still_rejected(self):
        ok, reason = validate(
            _fp({"passed": False, "data": {"vm_indicators": ["qemu"]}}),
            claimed_device={"arch": "modern"})
        self.assertFalse(ok)

    def test_evidence_without_a_vm_indicators_key_still_passes(self):
        """Clients that report other evidence keys must not be broken."""
        ok, reason = validate(
            _fp({"passed": True, "data": {"paths_checked": ["/proc/cpuinfo"]}}),
            claimed_device={"arch": "modern"})
        self.assertTrue(ok, reason)


class ConsoleEvidenceKeyTest(unittest.TestCase):
    """The Pico bridge fleet reports under its own key."""

    def _console(self, anti_emulation):
        return {
            "bridge_type": "pico_serial",
            "checks": {
                "ctrl_port_timing": {"passed": True,
                                     "data": {"cv": 0.0004, "samples": 500}},
                "anti_emulation": anti_emulation,
            },
        }

    def test_console_bridge_with_clean_emulator_indicators_passes(self):
        ok, reason = validate(
            self._console({"passed": True, "data": {"emulator_indicators": []}}),
            claimed_device={"arch": "nes_6502"})
        self.assertTrue(ok, f"console fleet rejected: {reason}")

    def test_console_emulator_indicators_are_content_checked(self):
        """Whitelisting the key without reading it would be a new free pass."""
        ok, reason = validate(
            self._console({"passed": True,
                           "data": {"emulator_indicators": ["low_timing_cv"]}}),
            claimed_device={"arch": "nes_6502"})
        self.assertFalse(ok, "an emulated console claimed a pass and got it")
        self.assertIn("low_timing_cv", reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
