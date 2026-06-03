# SPDX-License-Identifier: MIT
"""
Integration tests for MAX_CONTENT_LENGTH enforcement on the real RustChain app.

Flask sets app.config['MAX_CONTENT_LENGTH'] = 1 MB. Without an explicit
errorhandler, Werkzeug raises RequestEntityTooLarge inside route handlers
that wrap their body with a broad `except Exception`, causing a 500 instead
of the expected 413. This suite verifies the fix works on real routes.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")

import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "rustchain_node",
    os.path.join(os.path.dirname(__file__), "rustchain_v2_integrated_v2.2.1_rip200.py"),
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_app = _mod.app

_LIMIT = 1 * 1024 * 1024        # 1 MB
_OVER  = b"x" * (_LIMIT + 1)    # 1 MB + 1 byte


class TestMaxContentLengthConfig(unittest.TestCase):
    """Verify the config value is present and correct."""

    def test_config_is_set(self):
        self.assertEqual(_app.config["MAX_CONTENT_LENGTH"], _LIMIT)


class TestOversizedBodyReturns413(unittest.TestCase):
    """Real-route coverage: oversized bodies must return 413, not 500."""

    def setUp(self):
        _app.config["TESTING"] = True
        self.client = _app.test_client()

    def _post_oversized(self, path: str):
        return self.client.post(
            path,
            data=_OVER,
            content_type="application/json",
            headers={"Content-Length": str(len(_OVER))},
        )

    def test_attest_submit_returns_413(self):
        resp = self._post_oversized("/attest/submit")
        self.assertEqual(resp.status_code, 413)

    def test_wallet_transfer_signed_returns_413(self):
        resp = self._post_oversized("/wallet/transfer/signed")
        self.assertEqual(resp.status_code, 413)

    def test_governance_vote_returns_413(self):
        resp = self._post_oversized("/governance/vote")
        self.assertEqual(resp.status_code, 413)

    def test_413_response_is_json(self):
        resp = self._post_oversized("/attest/submit")
        self.assertEqual(resp.status_code, 413)
        data = resp.get_json()
        self.assertIsNotNone(data, "413 response must be JSON")
        self.assertEqual(data.get("code"), "REQUEST_TOO_LARGE")

    def test_normal_body_is_not_rejected(self):
        resp = self.client.post(
            "/attest/submit",
            json={"miner": "test"},
        )
        self.assertNotEqual(resp.status_code, 413)


if __name__ == "__main__":
    unittest.main()
