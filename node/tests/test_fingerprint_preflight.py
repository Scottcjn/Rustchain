import os
import sys
import unittest


try:
    import test_fingerprints
except ModuleNotFoundError:
    # Allow running tests from repo root (node/ isn't on sys.path by default).
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import test_fingerprints


class TestFingerprintPreflight(unittest.TestCase):
    def test_get_nested(self):
        ok, v = test_fingerprints._get_nested({"a": {"b": 1}}, "a.b")
        self.assertTrue(ok)
        self.assertEqual(v, 1)

        ok, v = test_fingerprints._get_nested({"a": {}}, "a.b")
        self.assertFalse(ok)
        self.assertIsNone(v)

    def test_compare_profile_ok(self):
        envelope = {
            "results": {
                "simd_identity": {"passed": True, "data": {"has_sse": True}},
                "clock_drift": {"passed": True, "data": {"cv": 0.01}},
            }
        }
        profile = {
            "name": "modern_x86",
            "expects": {"results.simd_identity.data.has_sse": True},
            "ranges": {"results.clock_drift.data.cv": [0.0001, 1.0]},
        }

        out = test_fingerprints.compare_to_profile(envelope, profile)
        self.assertTrue(out["ok"])

    def test_compare_profile_fail(self):
        envelope = {"results": {"simd_identity": {"passed": True, "data": {"has_sse": False}}}}
        profile = {"name": "modern_x86", "expects": {"results.simd_identity.data.has_sse": True}}

        out = test_fingerprints.compare_to_profile(envelope, profile)
        self.assertFalse(out["ok"])
        self.assertEqual(out["failed_checks"], 1)


if __name__ == "__main__":
    unittest.main()
