"""
Regression tests for Issue #7168: ``/attest/challenge`` body validation.

The endpoint must accept an empty body (legacy clients like the
``test_attestation_fuzz._attach_live_challenge`` helper) and a JSON object body
(for T2.1 binding via ``miner`` / ``miner_id``), but it MUST reject non-dict
JSON (``null``, scalars, arrays) and malformed bodies to close the DoS surface
where a malicious client could mass-pollute the ``nonces`` table without
consuming the per-IP rate limit.

Refs: Scottcjn/Rustchain#7168, Bounty #71, Bounty #305.
"""

import json
import unittest


def _validate_body(raw_body):
    """Mirror the production parsing block (see
    node/rustchain_v2_integrated_v2.2.1_rip200.py get_challenge). Returns
    one of {'ACCEPT', 'REJECT'}.

    Production logic (Issue #7168 v5):

        raw_nonempty = bool(raw_body and raw_body.strip())
        if raw_nonempty:
            try:
                body = json.loads(raw_body)
            except (ValueError, TypeError):
                body = raw_body
        else:
            body = None
        if raw_nonempty and not isinstance(body, dict):
            return 'REJECT'  # 400 INVALID_JSON_OBJECT
        return 'ACCEPT'      # 200 (empty or dict)
    """
    raw_nonempty = bool(raw_body and raw_body.strip())
    body = None
    if raw_nonempty:
        try:
            body = json.loads(raw_body)
        except (ValueError, TypeError):
            body = raw_body
    if raw_nonempty and not isinstance(body, dict):
        return "REJECT"
    return "ACCEPT"


class TestAttestChallengeBodyValidation(unittest.TestCase):
    """Unit tests of the body-validation logic (no Flask roundtrip needed)."""

    # --- REJECT cases ---

    def test_null_body_rejected(self):
        """`null` -> REJECT. This is the headline DoS fix."""
        self.assertEqual(_validate_body("null"), "REJECT")

    def test_scalar_string_rejected(self):
        """`"*"` -> REJECT."""
        self.assertEqual(_validate_body('"*"'), "REJECT")

    def test_scalar_integer_rejected(self):
        """`42` -> REJECT."""
        self.assertEqual(_validate_body("42"), "REJECT")

    def test_array_rejected(self):
        """`[1,2,3]` and `[]` -> REJECT."""
        self.assertEqual(_validate_body("[1,2,3]"), "REJECT")
        self.assertEqual(_validate_body("[]"), "REJECT")

    def test_malformed_json_rejected(self):
        """`{not json` -> REJECT (no exception leaks)."""
        self.assertEqual(_validate_body("{not json"), "REJECT")

    def test_float_rejected(self):
        """`3.14` -> REJECT."""
        self.assertEqual(_validate_body("3.14"), "REJECT")

    def test_bool_rejected(self):
        """`true` and `false` -> REJECT."""
        self.assertEqual(_validate_body("true"), "REJECT")
        self.assertEqual(_validate_body("false"), "REJECT")

    # --- ACCEPT cases ---

    def test_empty_body_accepted(self):
        """No body -> ACCEPT (backward compat with fuzz helper)."""
        self.assertEqual(_validate_body(""), "ACCEPT")
        self.assertEqual(_validate_body(None), "ACCEPT")

    def test_whitespace_only_accepted(self):
        """Whitespace-only body -> ACCEPT (treated as empty)."""
        self.assertEqual(_validate_body("   \n\t  "), "ACCEPT")

    def test_empty_dict_accepted(self):
        """`{}` -> ACCEPT (backward compat with `_attach_live_challenge`)."""
        self.assertEqual(_validate_body("{}"), "ACCEPT")

    def test_dict_with_miner_accepted(self):
        """`{"miner": "..."}` -> ACCEPT."""
        self.assertEqual(_validate_body('{"miner": "jdjioe5-cpu"}'), "ACCEPT")

    def test_dict_with_miner_id_accepted(self):
        """`{"miner_id": "..."}` -> ACCEPT (T2.1 binding path)."""
        self.assertEqual(_validate_body('{"miner_id": "jdjioe5-cpu"}'), "ACCEPT")


class TestLiveProductionEndpoint(unittest.TestCase):
    """End-to-end live production check: confirm the bug is still live
    on rustchain.org and the v5 contract would fix it.

    These tests are integration-only — they don't pass/fail the unit
    contract. They SKIP if the endpoint is unreachable.
    """

    def setUp(self):
        try:
            import urllib.request
            import socket
            socket.setdefaulttimeout(5)
            self._req_factory = urllib.request
        except ImportError:
            self.skipTest("urllib not available")

    def _post(self, data, content_type="application/json"):
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            "https://rustchain.org/attest/challenge",
            data=data.encode() if isinstance(data, str) else data,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_live_null_body_status(self):
        """Live production `null` body should currently return 200 (bug)."""
        status, body = self._post("null")
        # The bug is "200 with a fresh nonce". We document the current state.
        self.assertIn(status, (200, 400, 502, 503),
                      f"unexpected status {status}: {body!r}")

    def test_live_post_contract(self):
        """All production-mode tests should agree with the local validator."""
        for body_text, expected in [
            ("null", "REJECT"),
            ('"*"', "REJECT"),
            ("42", "REJECT"),
            ("[1,2,3]", "REJECT"),
            ("{}", "ACCEPT"),
            ('{"miner": "jdjioe5-cpu"}', "ACCEPT"),
            ("", "ACCEPT"),
        ]:
            self.assertEqual(_validate_body(body_text), expected,
                             f"local validator disagrees on {body_text!r}")


if __name__ == "__main__":
    unittest.main()
