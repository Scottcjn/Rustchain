#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""RIP-309c (closes #8342): classify before the fingerprint-shape guard, too.

RIP-309b moved device classification ahead of the `empty_fingerprint_checks`
bail so a flat vintage C miner (miners/apple2, miners/i386) sending
`fingerprint={"cycle_count": ..., "ram_kb": ...}` with no `checks` map was no
longer scored zero. It did not move classification ahead of the two guards
that run before that point: `if not fingerprint` and
`if not isinstance(fingerprint, dict)`. An i386 client that sends no separate
fingerprint object at all, or an Apple II client whose payload collapses to a
bare identity string instead of a dict, still hit `no_fingerprint_data` /
`fingerprint_not_dict` before the vintage/console branch ever ran — the same
class of bug RIP-309b fixed for the empty-checks case, just one guard higher.
"""

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.path.join(ROOT, "node")
sys.path.insert(0, NODE)

_spec = importlib.util.spec_from_file_location(
    "rc_node", os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")
)


def _load():
    mod = importlib.util.module_from_spec(_spec)
    sys.modules["rc_node"] = mod
    _spec.loader.exec_module(mod)
    return mod


MOD = _load()


class MissingFingerprintObjectTest(unittest.TestCase):
    """A limited-arch claim proves itself on claimed_device evidence when the
    client never built a separate fingerprint blob at all."""

    def test_i386_with_no_fingerprint_object_scores_on_device_evidence(self):
        """fingerprint=None used to short-circuit to no_fingerprint_data
        before claimed_arch was ever looked at."""
        device = {"arch": "i386", "cycle_count": 4021, "ram_kb": 640}
        ok, reason = MOD.validate_fingerprint_data(None, device)
        self.assertTrue(ok, reason)
        self.assertTrue(reason.startswith("micro_native_evidence"), reason)

    def test_i386_with_empty_dict_fingerprint_scores_on_device_evidence(self):
        device = {"arch": "i386", "cycle_count": 4021, "ram_kb": 640}
        ok, reason = MOD.validate_fingerprint_data({}, device)
        self.assertTrue(ok, reason)

    def test_apple2_bare_string_fingerprint_scores_on_device_evidence(self):
        """A flat client that collapses fingerprint to a raw identity string
        (not a dict) used to hit fingerprint_not_dict before classification."""
        device = {"arch": "6502", "cycle_count": 1023, "ram_kb": 64}
        ok, reason = MOD.validate_fingerprint_data("a1b2c3d4e5f60718", device)
        self.assertTrue(ok, reason)
        self.assertTrue(reason.startswith("micro_native_evidence"), reason)

    def test_i386_with_no_fingerprint_and_no_device_evidence_still_rejected(self):
        """Classifying first must not hand out a free pass: zero evidence
        anywhere is still zero evidence."""
        device = {"arch": "i386"}
        ok, reason = MOD.validate_fingerprint_data(None, device)
        self.assertFalse(ok)
        self.assertEqual(reason, "micro_insufficient_native_evidence")

    def test_i386_with_one_device_evidence_field_is_not_enough(self):
        device = {"arch": "i386", "ram_kb": 640}
        ok, reason = MOD.validate_fingerprint_data(None, device)
        self.assertFalse(ok)
        self.assertEqual(reason, "micro_insufficient_native_evidence")

    def test_modern_arch_with_no_fingerprint_is_unaffected(self):
        """A non-limited claim must not gain anything from this change: no
        fingerprint object is still an outright rejection for modern hardware."""
        ok, reason = MOD.validate_fingerprint_data(None, {"arch": "modern"})
        self.assertFalse(ok)
        self.assertEqual(reason, "no_fingerprint_data")

    def test_modern_arch_with_non_dict_fingerprint_is_unaffected(self):
        ok, reason = MOD.validate_fingerprint_data("garbage", {"arch": "modern"})
        self.assertFalse(ok)
        self.assertEqual(reason, "fingerprint_not_dict")

    def test_contradiction_veto_still_applies_with_no_fingerprint_object(self):
        """A Ryzen claiming to be an i386 must not slip through just because
        it also omits the fingerprint blob."""
        device = {
            "arch": "i386", "cycle_count": 4021, "ram_kb": 640,
            "machine": "x86_64", "cpu": "AMD Ryzen 9 7950X",
        }
        ok, reason = MOD.validate_fingerprint_data(None, device)
        self.assertFalse(ok)
        self.assertTrue(reason.startswith("capability_claim_contradicted"), reason)

    def test_existing_empty_checks_path_is_unchanged(self):
        """RIP-309b's own case (fingerprint present, checks map empty) must
        keep working exactly as before this change."""
        fp = {"simd_identity": "a1b2c3d4e5f60718", "cycle_count": 1023, "ram_kb": 64}
        ok, reason = MOD.validate_fingerprint_data(fp, {"arch": "6502"})
        self.assertTrue(ok, reason)
        self.assertTrue(reason.startswith("micro_native_evidence"), reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
