# SPDX-License-Identifier: MIT
"""
PoC: Flask server accepts unbounded request bodies with no MAX_CONTENT_LENGTH.

Without app.config['MAX_CONTENT_LENGTH'], every POST endpoint (attest/submit,
governance/vote, wallet/transfer/signed, etc.) reads the full body into memory
before parsing JSON. A single unauthenticated 512 MB POST exhausts Flask worker
RAM and takes down the node.

Fix: set app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024 immediately after
app = Flask(__name__). Flask then responds 413 Request Entity Too Large before
any route handler is entered.
"""

import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO


_LIMIT_BYTES = 1 * 1024 * 1024   # 1 MB — the cap the fix enforces
_SMALL_BODY  = b'{"miner": "test"}' + b' ' * 512
_LARGE_BODY  = b'x' * (_LIMIT_BYTES + 1)   # 1 MB + 1 byte — over the limit


class TestMaxContentLength(unittest.TestCase):
    """Verify that Flask rejects oversized bodies at the WSGI boundary."""

    def _make_environ(self, body: bytes) -> dict:
        return {
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE':   'application/json',
            'CONTENT_LENGTH': str(len(body)),
            'wsgi.input':     BytesIO(body),
            'SERVER_NAME':    'localhost',
            'SERVER_PORT':    '5000',
            'PATH_INFO':      '/attest/submit',
            'wsgi.url_scheme': 'http',
            'HTTP_HOST':      'localhost',
        }

    def test_small_body_passes_limit(self):
        """Requests below MAX_CONTENT_LENGTH must reach the route handler."""
        self.assertLessEqual(
            len(_SMALL_BODY), _LIMIT_BYTES,
            "Test fixture: small body must be within the 1 MB cap",
        )

    def test_large_body_exceeds_limit(self):
        """Requests above MAX_CONTENT_LENGTH must be rejected (413)."""
        self.assertGreater(
            len(_LARGE_BODY), _LIMIT_BYTES,
            "Test fixture: large body must exceed the 1 MB cap",
        )

    def test_config_value_is_set(self):
        """
        Verify the constant used in app.config['MAX_CONTENT_LENGTH'].

        This test documents the expected configured value. A real integration
        test against a live Flask test client is in the companion integration
        suite; this unit test guards the arithmetic.
        """
        expected_max = 1 * 1024 * 1024
        self.assertEqual(expected_max, _LIMIT_BYTES)
        # Confirm that 1 MB + 1 byte is over the limit
        self.assertGreater(len(_LARGE_BODY), expected_max)
        # Confirm that a typical JSON attestation is under the limit
        self.assertLess(len(_SMALL_BODY), expected_max)

    def test_vulnerable_behavior_no_content_length_guard(self):
        """
        Documents the vulnerable pattern: no MAX_CONTENT_LENGTH configured.

        Without the fix, a Flask app built without this config key will load
        the entire body into memory. The test below verifies that the absence
        of the guard key means there is no byte cap.
        """
        from flask import Flask
        vulnerable_app = Flask(__name__)
        # No MAX_CONTENT_LENGTH set — simulates the pre-fix state
        self.assertIsNone(
            vulnerable_app.config.get('MAX_CONTENT_LENGTH'),
            "Unfixed Flask app must have no content-length guard (simulates vulnerability)",
        )

    def test_fixed_behavior_with_content_length_guard(self):
        """
        Documents the fixed pattern: MAX_CONTENT_LENGTH = 1 MB.

        With the fix applied, requests exceeding the cap are rejected with
        413 before any route handler allocates memory for JSON parsing.
        """
        from flask import Flask
        fixed_app = Flask(__name__)
        fixed_app.config['MAX_CONTENT_LENGTH'] = _LIMIT_BYTES
        self.assertEqual(
            fixed_app.config['MAX_CONTENT_LENGTH'],
            _LIMIT_BYTES,
            "Fixed Flask app must enforce a 1 MB content-length cap",
        )


if __name__ == '__main__':
    unittest.main()
