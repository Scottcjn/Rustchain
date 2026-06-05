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
import sys
import os
import unittest
import importlib.util
from pathlib import Path

# Add miners/ to path so we can import signing_helpers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "miners"))

from signing_helpers import build_pipe_sign_message

ROOT = Path(__file__).resolve().parents[1]
LINUX_MINER_PATH = ROOT / "miners" / "linux" / "rustchain_linux_miner.py"


class TestAttestationSigningMessage(unittest.TestCase):
    """Verify the signing message matches what the node verifier expects."""

    def _node_verifier_reconstruction(self, attestation):
        """Reproduce the server-side 4-part pipe reconstruction
        (node/rustchain_v2_integrated_v2.2.1_rip200.py:3949)."""
        return "{}|{}|{}|{}".format(
            attestation["miner_id"],
            attestation["miner"],
            attestation["nonce"],
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

    def test_pipe_delimiter_in_field_raises(self):
        """If any field contains a pipe character the builder must reject it."""
        att = self._build_sample_attestation()
        att["nonce"] = "bad|nonce"
        with self.assertRaises(ValueError):
            build_pipe_sign_message(att)

    def test_missing_field_raises(self):
        """Missing required fields must raise ValueError."""
        with self.assertRaises(ValueError):
            build_pipe_sign_message({"miner_id": "x", "miner": "y"})

    def test_linux_miner_inline_fallback_matches_node_verifier(self):
        """The installed-miner inline path must sign the same bytes as the node."""
        spec = importlib.util.spec_from_file_location(
            "linux_miner_inline_signing_test",
            LINUX_MINER_PATH,
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

        miner_mod.FINGERPRINT_AVAILABLE = False
        miner_mod.WARTHOG_AVAILABLE = False
        miner_mod.CRYPTO_AVAILABLE = True
        miner_mod._SIGNING_HELPERS = False
        miner_mod.sign_payload = fake_sign_payload
        miner_mod.get_or_create_keypair = lambda: {
            "private_key": "priv",
            "public_key": "pub",
        }
        miner_mod.get_linux_serial = lambda: "test-serial"

        miner = miner_mod.LocalMiner(wallet="RTC1EXAMPLEWALLETADDR")
        miner._collect_entropy = lambda: {"variance_ns": 42.5, "source": "timer_jitter"}
        miner._get_hw_info = lambda: miner.hw_info.update({
            "family": "x86",
            "arch": "x86_64",
            "cpu": "Test CPU",
            "cores": 4,
            "memory_gb": 16.0,
            "serial": "test-serial",
            "macs": ["00:00:00:00:00:00"],
            "mac": "00:00:00:00:00:00",
            "hostname": "test-host",
            "machine": "x86_64",
        }) or miner.hw_info

        submitted = {}

        def fake_post(path, action, **kwargs):
            if path == "/attest/challenge":
                return _Response({"nonce": "test-nonce-abc123"})
            if path == "/attest/submit":
                submitted["attestation"] = kwargs["json"]
                return _Response({"ok": True})
            raise AssertionError(path)

        miner._post = fake_post

        self.assertTrue(miner.attest())
        verifier_str = self._node_verifier_reconstruction(submitted["attestation"])
        self.assertEqual(captured["message"], verifier_str.encode("utf-8"))
        self.assertEqual(captured["private_key"], "priv")

    def test_linux_miner_warns_when_attestation_signing_fails(self):
        """Signing failures must be visible instead of silently swallowed."""
        spec = importlib.util.spec_from_file_location(
            "linux_miner_signing_warning_test",
            LINUX_MINER_PATH,
        )
        miner_mod = importlib.util.module_from_spec(spec)
        self.assertIsNotNone(spec.loader)
        spec.loader.exec_module(miner_mod)

        class _Response:
            def __init__(self, payload):
                self.status_code = 200
                self._payload = payload

            def json(self):
                return self._payload

        def failing_sign_payload(message, private_key):
            raise RuntimeError("bad signing key")

        miner_mod.FINGERPRINT_AVAILABLE = False
        miner_mod.WARTHOG_AVAILABLE = False
        miner_mod.CRYPTO_AVAILABLE = True
        miner_mod._SIGNING_HELPERS = False
        miner_mod.sign_payload = failing_sign_payload
        miner_mod.get_or_create_keypair = lambda: {
            "private_key": "priv",
            "public_key": "pub",
        }
        miner_mod.get_linux_serial = lambda: "test-serial"

        miner = miner_mod.LocalMiner(wallet="RTC1EXAMPLEWALLETADDR")
        miner._collect_entropy = lambda: {"variance_ns": 42.5, "source": "timer_jitter"}
        miner._get_hw_info = lambda: miner.hw_info.update({
            "family": "x86",
            "arch": "x86_64",
            "cpu": "Test CPU",
            "cores": 4,
            "memory_gb": 16.0,
            "serial": "test-serial",
            "macs": ["00:00:00:00:00:00"],
            "mac": "00:00:00:00:00:00",
            "hostname": "test-host",
            "machine": "x86_64",
        }) or miner.hw_info

        submitted = {}

        def fake_post(path, action, **kwargs):
            if path == "/attest/challenge":
                return _Response({"nonce": "test-nonce-abc123"})
            if path == "/attest/submit":
                submitted["attestation"] = kwargs["json"]
                return _Response({"ok": True})
            raise AssertionError(path)

        miner._post = fake_post

        with self.assertLogs(level="WARNING") as logs:
            self.assertTrue(miner.attest())

        self.assertIn("attestation signing failed", "\n".join(logs.output))
        self.assertIn("bad signing key", "\n".join(logs.output))
        self.assertNotIn("signature", submitted["attestation"])


if __name__ == "__main__":
    unittest.main()
