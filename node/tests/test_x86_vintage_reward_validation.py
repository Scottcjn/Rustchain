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
        "device_age_oracle": _check(
            cpu_model=brand, cpu_family=str(family), arch="i686",
            flags_sample=[], mismatch_reasons=[], confidence=0.8,
        ),
    }
    if measurements:
        checks["cache_timing"] = _check(
            l1_ns=40.0, l2_ns=80.0, l3_ns=240.0,
            l2_l1_ratio=2.0, l3_l2_ratio=3.0,
        )
        checks["simd_identity"] = _check(
            arch="i686", simd_flags_count=1,
            has_sse=False, has_avx=False, has_altivec=False, has_neon=False,
            sample_flags=["fpu"],
        )
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
            {"device_family": "x86", "device_arch": arch}, fingerprint,
            measurement_report_verified=True,
        )

    def test_honest_tscless_486_keeps_tier_without_overall_pass_gate(self):
        fp = _fingerprint("Am486DX4", 4)
        self.assertEqual(self._reward("486", fp), {"device_family": "x86", "device_arch": "486"})

    def test_honest_tscless_486_fingerprint_can_omit_clock_drift(self):
        fp = _fingerprint("Am486DX4", 4)
        fp["checks"]["anti_emulation"] = _check(vm_indicators=[], paths_checked=["/proc/cpuinfo"])
        passed, reason = self.mod.validate_fingerprint_data(
            fp, {"family": "x86", "arch": "486"}, allow_tscless_x86_reward=True,
        )
        self.assertTrue(passed, reason)

    def test_tscless_relaxation_is_not_global(self):
        fp = _fingerprint("Am486DX4", 4)
        fp["checks"]["anti_emulation"] = _check(vm_indicators=[], paths_checked=["/proc/cpuinfo"])
        passed, reason = self.mod.validate_fingerprint_data(fp, {"family": "x86", "arch": "486"})
        self.assertFalse(passed)
        self.assertEqual(reason, "missing_required_check:clock_drift")

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

    def test_legacy_cache_profile_is_not_server_revalidated_evidence(self):
        fp = _fingerprint("Am486DX4", 4, measurements=False)
        fp["checks"]["cache_timing"] = _check(profile=[12.5, 24.0, 70.0])
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_inconsistent_derived_cache_ratios_are_not_evidence(self):
        fp = _fingerprint("Am486DX4", 4)
        fp["checks"]["cache_timing"]["data"]["l2_l1_ratio"] = 9.0
        self.assertFalse(
            self.mod._has_validated_x86_measurement(
                "cache_timing", fp["checks"]["cache_timing"]["data"]
            )
        )

    def test_unsigned_measurement_report_never_gets_vintage_weight(self):
        fp = _fingerprint("Am486DX4", 4)
        out = self.mod._derive_enroll_weight_device(
            {"device_family": "x86", "device_arch": "486"}, fp,
            fingerprint_passed=True, measurement_report_verified=False,
        )
        self.assertEqual(out["device_arch"], "default")

    def test_canonical_signer_must_control_reward_identity(self):
        pubkey = "11" * 32
        owned_miner = self.mod.address_from_pubkey(pubkey)
        self.assertTrue(
            self.mod._canonical_attestation_signer_owns_miner(pubkey, owned_miner)
        )
        self.assertTrue(
            self.mod._canonical_attestation_signer_owns_miner(pubkey, pubkey)
        )
        self.assertFalse(
            self.mod._canonical_attestation_signer_owns_miner(pubkey, "RTC" + "22" * 20)
        )
        self.assertFalse(
            self.mod._canonical_attestation_signer_owns_miner("not-hex", owned_miner)
        )

    def test_flags_only_payload_is_not_validated_evidence(self):
        fp = _fingerprint("Am486DX4", 4, measurements=False)
        fp["checks"]["simd_identity"] = {"data": {"has_sse": False}}
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_missing_current_simd_observation_cannot_hide_modern_flags(self):
        fp = _fingerprint("Intel Pentium III 800MHz", 6)
        del fp["checks"]["simd_identity"]
        self.assertEqual(self._reward("pentium_iii", fp)["device_arch"], "default")

    def test_incomplete_simd_observation_cannot_hide_modern_flags(self):
        fp = _fingerprint("Intel Pentium III 800MHz", 6)
        fp["checks"]["simd_identity"] = _check(
            simd_flags_count=32, sample_flags=["fpu"],
        )
        self.assertEqual(self._reward("pentium_iii", fp)["device_arch"], "default")

    def test_modern_passed_simd_clamps_vintage_claim(self):
        fp = _fingerprint(
            "Am486DX4", 4,
            simd_identity=_check(has_sse=True, sample_flags=["sse2"]),
        )
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_sampled_avx_flag_clamps_without_boolean_hint(self):
        fp = _fingerprint(
            "Intel Pentium III 800MHz", 6,
            simd_identity=_check(sample_flags=["avx2"]),
        )
        self.assertEqual(self._reward("pentium_iii", fp)["device_arch"], "default")

    def test_contradiction_in_simd_alias_cannot_be_shadowed(self):
        fp = _fingerprint(
            "Am486DX4", 4,
            simd_identity=_check(sample_flags=["legacy"]),
            simd_bias=_check(has_avx=True, sample_flags=["avx"]),
        )
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_failed_simd_check_still_supplies_negative_evidence(self):
        fp = _fingerprint(
            "Am486DX4", 4,
            simd_identity=_check(False, sample_flags=["avx2"], fail_reason="mismatch"),
        )
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_age_oracle_avx_sample_is_negative_evidence(self):
        fp = _fingerprint("Am486DX4", 4)
        fp["checks"]["device_age_oracle"]["data"]["flags_sample"] = ["avx2"]
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_age_oracle_sse_generation_must_fit_claimed_cpu(self):
        fp = _fingerprint("Intel Pentium III 800MHz", 6)
        fp["checks"]["device_age_oracle"]["data"]["flags_sample"] = ["sse2"]
        self.assertEqual(self._reward("pentium_iii", fp)["device_arch"], "default")

    def test_age_oracle_requires_current_flags_sample_field(self):
        fp = _fingerprint("Am486DX4", 4)
        del fp["checks"]["device_age_oracle"]["data"]["flags_sample"]
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_sse2_is_not_original_sse_and_clamps_pentium_ii(self):
        fp = _fingerprint(
            "Intel Pentium II 450MHz", 6,
            simd_identity=_check(sample_flags=["sse2"]),
        )
        self.assertEqual(self._reward("pentium_ii", fp)["device_arch"], "default")

    def test_failed_sse2_observation_clamps_486(self):
        fp = _fingerprint(
            "Am486DX4", 4,
            simd_identity=_check(False, sample_flags=["sse2"], fail_reason="mismatch"),
        )
        self.assertEqual(self._reward("486", fp)["device_arch"], "default")

    def test_sse2_clamps_pentium_iii_but_is_valid_for_dothan(self):
        p3 = _fingerprint(
            "Intel Pentium III 800MHz", 6,
            simd_identity=_check(sample_flags=["sse2"]),
        )
        self.assertEqual(self._reward("pentium_iii", p3)["device_arch"], "default")

        dothan = _fingerprint(
            "Intel Pentium M 2000MHz", 6,
            simd_identity=_check(
                arch="i686", simd_flags_count=1,
                has_sse=True, has_avx=False, has_altivec=False, has_neon=False,
                sample_flags=["sse2"],
            ),
        )
        self.assertEqual(self._reward("pentium_m_dothan", dothan)["device_arch"], "pentium_m_dothan")

    def test_later_sse_generations_exceed_pentium_m_subtypes(self):
        dothan = _fingerprint(
            "Intel Pentium M 2000MHz", 6,
            simd_identity=_check(sample_flags=["sse3"]),
        )
        self.assertEqual(self._reward("pentium_m_dothan", dothan)["device_arch"], "default")

        yonah = _fingerprint(
            "Intel Pentium M 2.0GHz", 6,
            simd_identity=_check(sample_flags=["ssse3"]),
        )
        self.assertEqual(self._reward("pentium_m_yonah", yonah)["device_arch"], "default")

    def test_linux_pni_alias_exceeds_dothan(self):
        fp = _fingerprint(
            "Intel Pentium M 2000MHz", 6,
            simd_identity=_check(
                arch="i686", simd_flags_count=2,
                has_sse=True, has_avx=False, has_altivec=False, has_neon=False,
                sample_flags=["sse2", "pni"],
            ),
        )
        self.assertEqual(self._reward("pentium_m_dothan", fp)["device_arch"], "default")

    def test_amd_sse4a_alias_exceeds_all_pentium_m_subtypes(self):
        fp = _fingerprint(
            "Intel Pentium M 2.0GHz", 6,
            simd_identity=_check(
                arch="i686", simd_flags_count=2,
                has_sse=True, has_avx=False, has_altivec=False, has_neon=False,
                sample_flags=["sse2", "sse4a"],
            ),
        )
        self.assertEqual(self._reward("pentium_m_yonah", fp)["device_arch"], "default")

    def test_pentium_iii_sse_is_legitimate(self):
        fp = _fingerprint(
            "Intel(R) Pentium(R) III 800MHz", 6,
            simd_identity=_check(
                arch="i686", simd_flags_count=1,
                has_sse=True, has_avx=False, has_altivec=False, has_neon=False,
                sample_flags=["sse"],
            ),
        )
        self.assertEqual(self._reward("pentium_iii", fp)["device_arch"], "pentium_iii")

    def test_pentium_ii_with_sse_is_clamped(self):
        fp = _fingerprint(
            "Intel Pentium II 450MHz", 6,
            simd_identity=_check(has_sse=True, sample_flags=["sse"]),
        )
        self.assertEqual(self._reward("pentium_ii", fp)["device_arch"], "default")

    def test_real_world_pentium_iii_cpu_brand_is_accepted(self):
        fp = _fingerprint("Intel(R) Pentium(R) III CPU 800MHz", 6)
        self.assertEqual(self._reward("pentium_iii", fp)["device_arch"], "pentium_iii")

    def test_real_world_486_dx_slash_brand_is_accepted(self):
        fp = _fingerprint("486 DX/2", 4)
        self.assertEqual(self._reward("486", fp)["device_arch"], "486")

    def test_pentium_m_claim_is_disambiguated_down_only(self):
        fp = _fingerprint("Intel(R) Pentium(R) M processor 1600MHz", 6)
        self.assertEqual(self._reward("pentium_m_banias", fp)["device_arch"], "pentium_m_banias")
        self.assertEqual(self._reward("pentium_m_dothan", fp)["device_arch"], "pentium_m_dothan")

    def test_undifferentiated_pentium_m_cannot_keep_higher_subtype(self):
        fp = _fingerprint("Intel Pentium M", 6)
        self.assertEqual(self._reward("pentium_m_banias", fp)["device_arch"], "pentium_m_yonah")

    def test_failed_overall_fingerprint_never_gets_vintage_weight(self):
        fp = _fingerprint("Am486DX4", 4)
        out = self.mod._derive_enroll_weight_device(
            {"device_family": "x86", "device_arch": "486"}, fp,
            fingerprint_passed=False, measurement_report_verified=True,
        )
        self.assertEqual(out["device_arch"], "default")

    def test_reward_clamp_does_not_rewrite_general_identity(self):
        verified = {"device_family": "x86", "device_arch": "486"}
        fp = _fingerprint("Intel Core i7-9750H", 6)
        self.assertEqual(self.mod._derive_enroll_weight_device(verified, fp)["device_arch"], "default")
        self.assertEqual(verified, {"device_family": "x86", "device_arch": "486"})


if __name__ == "__main__":
    unittest.main()
