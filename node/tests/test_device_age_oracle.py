import os
import sys
import unittest
from unittest import mock


try:
    import fingerprint_checks
except ModuleNotFoundError:
    # Allow running tests from repo root (node/ isn't on sys.path by default).
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import fingerprint_checks


class TestDeviceAgeOracle(unittest.TestCase):
    def test_intel_core_gen_maps_to_year_and_passes(self):
        cpuinfo = "\n".join(
            [
                "model name\t: Intel(R) Core(TM) i7-4770 CPU @ 3.40GHz",
                "flags\t\t: fpu sse sse2 sse4_1 sse4_2 avx",
            ]
        )

        def fake_read(path, max_bytes=0):
            if path == "/proc/cpuinfo":
                return cpuinfo
            return None

        with mock.patch.object(fingerprint_checks, "_read_text_file", side_effect=fake_read), mock.patch.object(
            fingerprint_checks.platform, "machine", return_value="x86_64"
        ):
            passed, data = fingerprint_checks.check_device_age_oracle()

        self.assertTrue(passed)
        self.assertEqual(data["estimated_release_year"], 2013)
        self.assertEqual(data["mismatch_reasons"], [])
        self.assertGreaterEqual(data["confidence"], 0.5)

    def test_intel_11th_gen_mobile_4digit_parsing(self):
        cpuinfo = "\n".join(
            [
                "model name\t: Intel(R) Core(TM) i7-1165G7 @ 2.80GHz",
                "flags\t\t: fpu sse sse2 sse4_1 sse4_2 avx avx2",
            ]
        )

        def fake_read(path, max_bytes=0):
            if path == "/proc/cpuinfo":
                return cpuinfo
            return None

        with mock.patch.object(fingerprint_checks, "_read_text_file", side_effect=fake_read), mock.patch.object(
            fingerprint_checks.platform, "machine", return_value="x86_64"
        ):
            passed, data = fingerprint_checks.check_device_age_oracle()

        self.assertTrue(passed)
        self.assertEqual(data["estimated_release_year"], 2021)

    def test_spoofed_vintage_claim_on_x86_fails(self):
        cpuinfo = "\n".join(
            [
                "model name\t: PowerPC G4 (7447A)",
                "flags\t\t: fpu sse sse2 avx",
            ]
        )

        def fake_read(path, max_bytes=0):
            if path == "/proc/cpuinfo":
                return cpuinfo
            return None

        with mock.patch.object(fingerprint_checks, "_read_text_file", side_effect=fake_read), mock.patch.object(
            fingerprint_checks.platform, "machine", return_value="x86_64"
        ):
            passed, data = fingerprint_checks.check_device_age_oracle()

        self.assertFalse(passed)
        self.assertIn("device_age_oracle_mismatch", data.get("fail_reason", ""))
        self.assertTrue(data["mismatch_reasons"])

    def test_macos_sysctl_fallback_works(self):
        def fake_read(path, max_bytes=0):
            # Simulate non-Linux environment
            return None

        with mock.patch.object(fingerprint_checks, "_read_text_file", side_effect=fake_read), mock.patch.object(
            fingerprint_checks, "_run_cmd", return_value="Apple M2"
        ), mock.patch.object(fingerprint_checks.platform, "machine", return_value="arm64"):
            passed, data = fingerprint_checks.check_device_age_oracle()

        self.assertTrue(passed)
        self.assertEqual(data["estimated_release_year"], 2022)
        self.assertGreaterEqual(data["confidence"], 0.5)


if __name__ == "__main__":
    unittest.main()
