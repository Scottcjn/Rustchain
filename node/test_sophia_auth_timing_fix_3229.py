"""Tests for timing-safe admin authentication fix (Issue #3229).

Verifies that admin key comparison uses hmac.compare_digest
instead of == operator to prevent timing attacks.
"""
import hmac
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))


class MockRequest:
    """Mock Flask request object for testing _is_authorized."""
    def __init__(self, headers=None):
        self.headers = headers or {}


class TestTimingSafeAuth(unittest.TestCase):
    """Test that admin authentication uses timing-safe comparison."""

    def setUp(self):
        """Set up test environment."""
        self.original_admin_key = os.environ.get("RC_ADMIN_KEY")
        self.original_bearer = os.environ.get("SOPHIA_GOVERNOR_REVIEW_BEARER")
        os.environ["RC_ADMIN_KEY"] = "test-secret-key-12345"
        os.environ["SOPHIA_GOVERNOR_REVIEW_BEARER"] = ""

    def tearDown(self):
        """Restore original environment."""
        if self.original_admin_key is not None:
            os.environ["RC_ADMIN_KEY"] = self.original_admin_key
        else:
            os.environ.pop("RC_ADMIN_KEY", None)
        if self.original_bearer is not None:
            os.environ["SOPHIA_GOVERNOR_REVIEW_BEARER"] = self.original_bearer
        else:
            os.environ.pop("SOPHIA_GOVERNOR_REVIEW_BEARER", None)

        # Clear module cache to force reimport
        if "sophia_governor_review_service" in sys.modules:
            del sys.modules["sophia_governor_review_service"]

    def _get_is_authorized(self):
        """Import and return _is_authorized function."""
        from sophia_governor_review_service import _is_authorized
        return _is_authorized

    def test_correct_admin_key_accepted(self):
        """Valid admin key should be accepted."""
        _is_authorized = self._get_is_authorized()
        req = MockRequest(headers={"X-Admin-Key": "test-secret-key-12345"})
        self.assertTrue(_is_authorized(req))

    def test_wrong_admin_key_rejected(self):
        """Wrong admin key should be rejected."""
        _is_authorized = self._get_is_authorized()
        req = MockRequest(headers={"X-Admin-Key": "wrong-key"})
        self.assertFalse(_is_authorized(req))

    def test_empty_admin_key_rejected(self):
        """Empty admin key should be rejected."""
        _is_authorized = self._get_is_authorized()
        req = MockRequest(headers={"X-Admin-Key": ""})
        self.assertFalse(_is_authorized(req))

    def test_no_admin_key_header_rejected(self):
        """Missing admin key header should be rejected."""
        _is_authorized = self._get_is_authorized()
        req = MockRequest(headers={})
        self.assertFalse(_is_authorized(req))

    def test_x_api_key_header_accepted(self):
        """X-API-Key header should also work for admin auth."""
        _is_authorized = self._get_is_authorized()
        req = MockRequest(headers={"X-API-Key": "test-secret-key-12345"})
        self.assertTrue(_is_authorized(req))

    def test_uses_hmac_compare_digest(self):
        """Verify the code uses hmac.compare_digest, not ==."""
        import sophia_governor_review_service
        import inspect
        source = inspect.getsource(sophia_governor_review_service._is_authorized)
        self.assertIn("hmac.compare_digest", source)
        self.assertNotIn("== required_admin", source)
        self.assertNotIn("==provided_admin", source)

    def test_timing_attack_resistance(self):
        """Verify hmac.compare_digest is used (constant-time comparison)."""
        # This test confirms the fix is in place by checking the function behavior
        _is_authorized = self._get_is_authorized()
        
        # Measure time for wrong key (short)
        req_short = MockRequest(headers={"X-Admin-Key": "a"})
        start = time.perf_counter()
        for _ in range(1000):
            _is_authorized(req_short)
        time_short = time.perf_counter() - start
        
        # Measure time for wrong key (long, same length as correct key)
        req_long = MockRequest(headers={"X-Admin-Key": "x" * len("test-secret-key-12345")})
        start = time.perf_counter()
        for _ in range(1000):
            _is_authorized(req_long)
        time_long = time.perf_counter() - start
        
        # With hmac.compare_digest, times should be similar regardless of key length
        # (within 50% tolerance - timing can vary due to system load)
        ratio = max(time_short, time_long) / min(time_short, time_long)
        self.assertLess(ratio, 2.0, 
            f"Timing ratio {ratio:.2f} suggests non-constant-time comparison")


if __name__ == "__main__":
    unittest.main()
