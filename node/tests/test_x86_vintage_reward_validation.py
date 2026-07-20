# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for bounty #16271 vintage-x86 reward validation."""
import importlib.util
import os
import tempfile
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


def _check(passed=True, **data):
    return {"passed": passed, "data": data}


def _fingerprint(brand, family, measurements=True, **extra_checks):
    checks = {
        "device_age_oracle": _check(cpu_model=brand, cpu_family=str(family)),
    }
    if measurements:
        checks["cache_timing"] = _check(l1_ns=40.0, l2_ns=115.0)
    checks.update(extra_checks)
    return {"checks": checks}


class X86VintageRewardValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ.setdefault("RUSTCHAIN_DB_PATH", os.path.join(cls._tmp.name, "x86-reward.db"))
        os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
        spec = importlib.util.spec_from_file_location("rcnode_x86_reward_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def _reward(self, arch, fingerprint):
        return self.mod._derive_enroll_weight_device(
            {"device_family": "x86", "device_arch": arch}, fingerprint
        )

    def test_honest_tscless_486_keeps_tier_without_overall_pass_gate(self):
        fp = _fingerprint("Am486DX4", 4)
        self.assertEqual(self._reward("486", fp), {"device_family": "x86", "device_arch": "486"})

    def test_honest_tscless_486_fingerprint_can_omit_clock_drift(self):
        fp = _fingerprint("Am486DX4", 4)
        fp["checks"]["anti_emulation"] = _check(vm_indicators=[], paths_checked=["/proc/cpuinfo"])
        passed, reason = self.mod.validate_fingerprint_data(fp, {"family": "x86", "arch": "486"})
        self.assertTrue(passed, reason)

    def test_modern_family_and_brand_cannot_claim_486(self):
        fp = _fingerprint("Intel Core i7-9750H", 6)
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_family_six_pentium_iii_is_not_family_five_pentium(self):
        fp = _fingerprint("Intel Pentium III 800MHz", 6)
        self.assertEqual(self._reward("pentium", fp)["device_arch"], "default")

    def test_mixed_case_anchored_pentium_brand_is_accepted(self):
        fp = _fingerprint("pEnTiUm 200", 5)
        self.assertEqual(self._reward("pentium", fp)["device_arch"], "pentium")

    def test_plain_pentium_downgrades_mmx_claim(self):
        fp = _fingerprint("Intel Pentium 200", 5)
        self.assertEqual(self._reward("pentium_mmx", fp)["device_arch"], "pentium")

    def test_mmx_brand_never_inflates_plain_pentium_claim(self):
        fp = _fingerprint("Intel Pentium MMX 233MHz", 5)
        self.assertEqual(self._reward("pentium", fp)["device_arch"], "pentium")

    def test_bare_brand_without_measurement_is_clamped(self):
        fp = _fingerprint("Am486DX4", 4, measurements=False)
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_data_without_explicit_pass_is_not_evidence(self):
        fp = _fingerprint("Am486DX4", 4, measurements=False)
        fp["checks"]["cache_timing"] = {"data": {"l1_ns": 40.0}}
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_passed_arbitrary_data_is_not_measurement_evidence(self):
        fp = _fingerprint("Am486DX4", 4, measurements=False)
        fp["checks"]["cache_timing"] = _check(note="passed")
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_passed_boolean_metric_is_not_measurement_evidence(self):
        fp = _fingerprint("Am486DX4", 4, measurements=False)
        fp["checks"]["thermal_drift"] = _check(variance=True)
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_nonpositive_metrics_are_not_measurement_evidence(self):
        fp = _fingerprint("Am486DX4", 4, measurements=False)
        fp["checks"]["cache_timing"] = _check(l1_ns=-40.0, l2_ns=0)
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_legacy_cache_profile_is_measurement_evidence(self):
        fp = _fingerprint("Am486DX4", 4, measurements=False)
        fp["checks"]["cache_timing"] = _check(profile=[12.5, 24.0, 70.0])
        self.assertEqual(self._reward("486", fp)["device_arch"], "486")

    def test_flags_only_payload_is_not_validated_evidence(self):
        fp = _fingerprint("Am486DX4", 4, measurements=False)
        fp["checks"]["simd_identity"] = {"data": {"has_sse": False}}
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_modern_passed_simd_clamps_vintage_claim(self):
        fp = _fingerprint(
            "Am486DX4", 4,
            simd_identity=_check(has_sse=True, sample_flags=["sse2"]),
        )
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_pentium_iii_sse_is_legitimate(self):
        fp = _fingerprint(
            "Intel(R) Pentium(R) III 800MHz", 6,
            simd_identity=_check(has_sse=True, has_avx=False, sample_flags=["sse"]),
        )
        self.assertEqual(self._reward("pentium_iii", fp)["device_arch"], "pentium_iii")

    def test_pentium_ii_with_sse_is_clamped(self):
        fp = _fingerprint(
            "Intel Pentium II 450MHz", 6,
            simd_identity=_check(has_sse=True, sample_flags=["sse"]),
        )
        self.assertEqual(self._reward("pentium_ii", fp)["device_arch"], "default")

    def test_reward_clamp_does_not_rewrite_general_identity(self):
        verified = {"device_family": "x86", "device_arch": "486"}
        fp = _fingerprint("Intel Core i7-9750H", 6)
        self.assertEqual(self.mod._derive_enroll_weight_device(verified, fp)["device_arch"], "default")
        self.assertEqual(verified, {"device_family": "x86", "device_arch": "486"})


if __name__ == "__main__":
    unittest.main()
