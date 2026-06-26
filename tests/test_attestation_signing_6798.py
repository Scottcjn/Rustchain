"""
Regression test for issue #6798:
Miners must sign the pipe-delimited message (miner_id|miner|nonce|commitment)
that the node verifier reconstructs, NOT the canonical JSON of the full attestation.

Before the fix, both miners signed canonical JSON, but the server verified
a pipe-delimited string, causing every signed attestation to fail with
INVALID_SIGNATURE.

This test imports the actual signing helper used by both miners so that a
regression in the miner code would be caught here (tri-brain review feedback
on PR #6839).
"""
import json
import hashlib
import importlib.util
import sys
import os
import unittest

# Add miners/ to path so we can import signing_helpers
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MINERS_DIR = os.path.join(ROOT, "miners")
WINDOWS_MINER_PATH = os.path.join(
    MINERS_DIR, "windows", "rustchain_windows_miner.py"
)
sys.path.insert(0, MINERS_DIR)

from signing_helpers import build_pipe_sign_message


class TestAttestationSigningMessage(unittest.TestCase):
    """Verify the signing message matches what the node verifier expects."""

    def _node_verifier_reconstruction(self, attestation):
        """Reproduce the server-side 4-part pipe reconstruction
        (node/rustchain_v2_integrated_v2.2.1_rip200.py:3949)."""
        return "{}|{}|{}|{}".format(
            attestation["miner_id"],
            attestation["miner"],
            attestation["report"].get("nonce") or attestation.get("nonce"),
            attestation["report"]["commitment"],
        )

    def _build_sample_attestation(self):
        nonce = "test-nonce-abc123"
        wallet = "RTC1EXAMPLEWALLETADDR"
        miner_id = "min-001"
        entropy = {"variance_ns": 42.5, "source": "timer_jitter"}
        commitment = hashlib.sha256(
            (nonce + wallet + json.dumps(entropy, sort_keys=True)).encode()
        ).hexdigest()
        return {
            "miner": wallet,
            "miner_id": miner_id,
            "nonce": nonce,
            "report": {
                "nonce": nonce,
                "commitment": commitment,
                "derived": entropy,
                "entropy_score": entropy.get("variance_ns", 0.0),
            },
            "device": {
                "family": "x86",
                "arch": "x86_64",
                "model": "Test CPU",
                "cpu": "Test CPU",
                "cores": 4,
                "memory_gb": 16.0,
                "serial": None,
                "machine": "x86_64",
            },
            "signals": {"macs": ["00:00:00:00:00:00"], "hostname": "test-host"},
            "fingerprint": None,
            "warthog": None,
        }

    def test_shared_helper_matches_node_verifier(self):
        """The shared build_pipe_sign_message must produce the same bytes the
        node verifier reconstructs from the 4-part pipe split."""
        att = self._build_sample_attestation()
        miner_bytes = build_pipe_sign_message(att)
        verifier_str = self._node_verifier_reconstruction(att)
        self.assertEqual(miner_bytes, verifier_str.encode("utf-8"))

    def test_round_trip_four_parts(self):
        """Round-trip: the signed bytes split on '|' yield exactly the four
        fields the node verifier extracts."""
        att = self._build_sample_attestation()
        signed_bytes = build_pipe_sign_message(att)
        parts = signed_bytes.decode("utf-8").split("|")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], att["miner_id"])
        self.assertEqual(parts[1], att["miner"])
        self.assertEqual(parts[2], att["nonce"])
        self.assertEqual(parts[3], att["report"]["commitment"])

    def test_pipe_message_differs_from_canonical_json(self):
        """Confirm the old canonical-JSON approach produces different bytes
        than the pipe-string — this is the root cause of issue #6798."""
        att = self._build_sample_attestation()
        pipe_msg = build_pipe_sign_message(att)
        canonical_bytes = json.dumps(
            att, sort_keys=True, separators=(",", ":")
        ).encode()
        self.assertNotEqual(pipe_msg, canonical_bytes)

    def test_pipe_message_deterministic(self):
        """Same attestation fields always produce the same signing message."""
        att = self._build_sample_attestation()
        msg1 = build_pipe_sign_message(att)
        msg2 = build_pipe_sign_message(att)
        self.assertEqual(msg1, msg2)

    def test_different_nonce_changes_message(self):
        """Different nonce produces a different signing message."""
        att1 = self._build_sample_attestation()
        att2 = self._build_sample_attestation()
        att2["nonce"] = "different-nonce"
        att2["report"]["nonce"] = "different-nonce"
        att2["report"]["commitment"] = hashlib.sha256(
            (att2["nonce"] + att2["miner"] + json.dumps({"variance_ns": 42.5, "source": "timer_jitter"}, sort_keys=True)).encode()
        ).hexdigest()
        msg1 = build_pipe_sign_message(att1)
        msg2 = build_pipe_sign_message(att2)
        self.assertNotEqual(msg1, msg2)

    def test_report_nonce_takes_precedence_like_node_verifier(self):
        """Use report.nonce when the legacy top-level nonce differs."""
        att = self._build_sample_attestation()
        att["nonce"] = "stale-top-level-nonce"
        self.assertEqual(
            build_pipe_sign_message(att),
            self._node_verifier_reconstruction(att).encode("utf-8"),
        )

    def test_legacy_top_level_nonce_fallback(self):
        """Clients without report.nonce keep using the top-level nonce."""
        att = self._build_sample_attestation()
        del att["report"]["nonce"]
        self.assertEqual(
            build_pipe_sign_message(att),
            self._node_verifier_reconstruction(att).encode("utf-8"),
        )

    def test_pipe_delimiter_in_field_raises(self):
        """If any field contains a pipe character the builder must reject it."""
        att = self._build_sample_attestation()
        att["report"]["nonce"] = "bad|nonce"
        with self.assertRaises(ValueError):
            build_pipe_sign_message(att)

    def test_missing_field_raises(self):
        """Missing required fields must raise ValueError."""
        with self.assertRaises(ValueError):
            build_pipe_sign_message({"miner_id": "x", "miner": "y"})

    def test_windows_miner_signs_report_nonce(self):
        """Windows omits top-level nonce but must still submit Ed25519 fields."""
        spec = importlib.util.spec_from_file_location(
            "windows_miner_report_nonce_signing_test",
            WINDOWS_MINER_PATH,
        )
        miner_mod = importlib.util.module_from_spec(spec)
        self.assertIsNotNone(spec.loader)
        spec.loader.exec_module(miner_mod)

        captured = {}

        class _Response:
            def __init__(self, payload):
                self.status_code = 200
                self._payload = payload

            def json(self):
                return self._payload

        def fake_sign_payload(message, private_key):
            captured["message"] = message
            captured["private_key"] = private_key
            return "sig"

        def fake_post(url, **kwargs):
            if url.endswith("/attest/challenge"):
                return _Response({"nonce": "test-nonce-abc123"})
            if url.endswith("/attest/submit"):
                captured["attestation"] = kwargs["json"]
                return _Response({"ok": True})
            raise AssertionError(url)

        miner_mod.FINGERPRINT_AVAILABLE = False
        miner_mod.CRYPTO_AVAILABLE = True
        miner_mod._SIGNING_HELPERS = True
        miner_mod.sign_payload = fake_sign_payload
        miner_mod.get_or_create_keypair = lambda: {
            "private_key": "priv",
            "public_key": "pub",
        }
        miner_mod.requests.post = fake_post

        miner = miner_mod.RustChainMiner("RTC1EXAMPLEWALLETADDR")
        miner._collect_entropy = lambda: {
            "variance_ns": 42.5,
            "source": "timer_jitter",
        }
        miner._build_pow_proof = lambda: None

        self.assertTrue(miner.attest())
        attestation = captured["attestation"]
        self.assertNotIn("nonce", attestation)
        self.assertEqual(attestation["signature"], "sig")
        self.assertEqual(attestation["signature_type"], "ed25519")
        self.assertEqual(
            captured["message"],
            self._node_verifier_reconstruction(attestation).encode("utf-8"),
        )
        self.assertEqual(captured["private_key"], "priv")


if __name__ == "__main__":
    unittest.main()
