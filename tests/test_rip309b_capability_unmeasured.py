#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""RIP-309b: `unmeasured` is neutral, and proving nothing scores nothing.

Two failures this pins:

1. The honest vintage fleet earned zero. `validate_fingerprint_data` returned
   `empty_fingerprint_checks` before the device was classified, so the flat C
   miners (miners/apple2, miners/i386) died before the vintage branch could
   help. An honest 486 reporting a truthful `clock_drift: false` was scored as
   a failure, while a client hardcoding `"passed": true` scored 1.0 — the
   control fired only on honest miners.

2. The obvious fix introduces a worse hole. If every active check is
   `unmeasured`, the denominator is empty, and returning 1.0 there hands a
   perfect score to a payload carrying no evidence at all. The empty
   denominator must fail closed.
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

_spec = importlib.util.spec_from_file_location(
    "rc_node", os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")
)


def _load():
    mod = importlib.util.module_from_spec(_spec)
    sys.modules["rc_node"] = mod
    _spec.loader.exec_module(mod)
    return mod


MOD = _load()


def _check(passed=True, **data):
    return {"passed": passed, "data": data}


class RotationScoringTest(unittest.TestCase):
    """evaluate_rotating_fingerprint_checks: the three-state denominator."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.conn = sqlite3.connect(self.tmp.name)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmp.name)

    def _eval(self, fingerprint, arch=None, micro_accepted=False):
        return MOD.evaluate_rotating_fingerprint_checks(
            self.conn, 0, fingerprint, device_arch=arch, micro_accepted=micro_accepted
        )

    def test_missing_checks_on_modern_hardware_are_failures_not_neutral(self):
        """Capable hardware gets no excuse: absent checks count as failures.

        measured_total is the full active set here, not zero — the checks are
        counted and failed, rather than dropped from the denominator. Only a
        capability-limited class earns the neutral treatment.
        """
        res = self._eval({"checks": {}}, arch="modern")
        self.assertEqual(res["unmeasured_active_checks"], [])
        self.assertEqual(res["measured_total"], len(res["active_checks"]))
        self.assertEqual(res["passed_active_checks"], [])
        self.assertEqual(res["active_ratio"], 0.0)

    def test_all_unmeasured_without_evidence_scores_zero(self):
        """The hole: capability-limited class, but no native evidence earned."""
        res = self._eval({"checks": {}}, arch="6502", micro_accepted=False)
        self.assertEqual(res["measured_total"], 0)
        self.assertEqual(
            res["active_ratio"], 0.0,
            "an all-unmeasured payload that proved nothing must not score 1.0",
        )

    def test_all_unmeasured_with_earned_evidence_scores_one(self):
        """An accepted micro is not punished for hardware it cannot have."""
        res = self._eval({"checks": {}}, arch="6502", micro_accepted=True)
        self.assertEqual(res["active_ratio"], 1.0)
        self.assertEqual(res["measured_total"], 0)
        self.assertTrue(res["unmeasured_active_checks"])

    def test_unmeasured_leaves_the_denominator_not_the_numerator(self):
        """A micro passing one real check scores 1.0, not 1/4."""
        fp = {"checks": {"anti_emulation": _check(vm_indicators=[])}}
        res = self._eval(fp, arch="nes_6502", micro_accepted=True)
        self.assertEqual(res["measured_total"], 1)
        self.assertEqual(res["passed_active_checks"], ["anti_emulation"])
        self.assertEqual(res["active_ratio"], 1.0)

    def test_a_real_failure_still_counts_against_a_limited_class(self):
        """`unmeasured` must not launder an actual reported failure."""
        fp = {"checks": {"anti_emulation": _check(passed=False, vm_indicators=["qemu"])}}
        res = self._eval(fp, arch="nes_6502", micro_accepted=True)
        self.assertEqual(res["failed_active_checks"], ["anti_emulation"])
        self.assertEqual(res["active_ratio"], 0.0)

    def test_modern_arch_gets_no_unmeasured_excuse(self):
        """A missing check on capable hardware is a failure, not neutral."""
        res = self._eval({"checks": {}}, arch="modern")
        self.assertEqual(res["unmeasured_active_checks"], [])
        self.assertEqual(res["active_ratio"], 0.0)


class MicroAcceptanceTest(unittest.TestCase):
    """validate_fingerprint_data: classify before bailing on an empty map."""

    def test_apple2_flat_payload_is_accepted_on_native_evidence(self):
        fp = {"simd_identity": "a1b2c3d4e5f60718", "cycle_count": 1023, "ram_kb": 64}
        ok, reason = MOD.validate_fingerprint_data(fp, {"arch": "6502"})
        self.assertTrue(ok, reason)
        self.assertTrue(reason.startswith("micro_native_evidence"), reason)

    def test_one_evidence_field_is_not_enough(self):
        ok, reason = MOD.validate_fingerprint_data({"ram_kb": 64}, {"arch": "6502"})
        self.assertFalse(ok)
        self.assertEqual(reason, "micro_insufficient_native_evidence")

    def test_modern_claim_with_empty_checks_still_rejected(self):
        ok, reason = MOD.validate_fingerprint_data({"checks": {}}, {"arch": "modern"})
        self.assertFalse(ok)
        self.assertEqual(reason, "empty_fingerprint_checks")

    def test_modern_evidence_vetoes_a_micro_claim(self):
        """The contradiction veto is what stops a Ryzen claiming to be a 6502."""
        fp = {"cycle_count": 1023, "ram_kb": 64}
        ok, reason = MOD.validate_fingerprint_data(
            fp, {"arch": "6502", "machine": "x86_64", "cpu": "AMD Ryzen 9 7950X"}
        )
        self.assertFalse(ok)
        self.assertTrue(reason.startswith("capability_claim_contradicted"), reason)

    def test_micro_accepted_helper_requires_all_three_conditions(self):
        good = {"cycle_count": 1023, "ram_kb": 64}
        self.assertTrue(MOD._micro_accepted_for_rotation("6502", good, {"arch": "6502"}))
        # contradicted
        self.assertFalse(
            MOD._micro_accepted_for_rotation("6502", good, {"machine": "x86_64"})
        )
        # not a limited class
        self.assertFalse(MOD._micro_accepted_for_rotation("modern", good, {}))
        # insufficient evidence
        self.assertFalse(MOD._micro_accepted_for_rotation("6502", {"ram_kb": 64}, {}))


class MultiplierTableTest(unittest.TestCase):
    """Standalone micros sit below console, and the two tables agree."""

    def test_standalone_micros_rank_below_console_silicon(self):
        w = MOD.HARDWARE_WEIGHTS
        self.assertLess(w["MOS"]["6502"], w["console"]["nes_6502"])
        self.assertLess(w["MOS"]["65c816"], w["console"]["snes_65c816"])
        self.assertLess(w["Zilog"]["z80"], w["console"]["gameboy_z80"])

    def test_defaults_sit_under_named_arches(self):
        w = MOD.HARDWARE_WEIGHTS
        self.assertLess(w["MOS"]["default"], w["MOS"]["6502"])
        self.assertLess(w["Zilog"]["default"], w["Zilog"]["z80"])

    def test_micro_bonus_still_beats_modern_hardware(self):
        w = MOD.HARDWARE_WEIGHTS
        self.assertGreater(w["MOS"]["6502"], w["x86_64"]["modern"])

    def test_the_two_multiplier_tables_agree_on_the_same_silicon(self):
        """A second table disagreeing about one chip is how divergence starts."""
        import rip_200_round_robin_1cpu1vote as rr
        anti = rr.ANTIQUITY_MULTIPLIERS
        w = MOD.HARDWARE_WEIGHTS
        for arch, family in (("6502", "MOS"), ("65c816", "MOS"), ("z80", "Zilog")):
            self.assertEqual(
                w[family][arch], anti[arch],
                f"HARDWARE_WEIGHTS[{family}][{arch}] and "
                f"ANTIQUITY_MULTIPLIERS[{arch}] disagree",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
