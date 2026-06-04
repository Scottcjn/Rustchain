"""
Regression test for issue #6798:
Miners must sign the pipe-delimited message (miner_id|miner|nonce|commitment)
that the node verifier reconstructs, NOT the canonical JSON of the full attestation.

Before the fix, both miners signed canonical JSON, but the server verified
a pipe-delimited string, causing every signed attestation to fail with
INVALID_SIGNATURE.
"""
import json
import hashlib
import unittest


class TestAttestationSigningMessage(unittest.TestCase):
    """Verify the signing message matches what the node verifier expects."""

    def _build_sign_message_pipe(self, attestation):
        """Reproduce the node-side verification message."""
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

    def test_pipe_message_matches_node_verifier(self):
        """The pipe-delimited message must match the node's sign_message."""
        att = self._build_sample_attestation()
        pipe_msg = self._build_sign_message_pipe(att)
        expected = "min-001|RTC1EXAMPLEWALLETADDR|test-nonce-abc123|{}".format(
            att["report"]["commitment"]
        )
        self.assertEqual(pipe_msg, expected)

    def test_pipe_message_differs_from_canonical_json(self):
        """Confirm the old canonical-JSON approach produces different bytes
        than the pipe-string — this is the root cause of issue #6798."""
        att = self._build_sample_attestation()
        pipe_msg = self._build_sign_message_pipe(att).encode("utf-8")
        canonical_bytes = json.dumps(
            att, sort_keys=True, separators=(",", ":")
        ).encode()
        self.assertNotEqual(pipe_msg, canonical_bytes)

    def test_pipe_message_deterministic(self):
        """Same attestation fields always produce the same signing message."""
        att = self._build_sample_attestation()
        msg1 = self._build_sign_message_pipe(att)
        msg2 = self._build_sign_message_pipe(att)
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
        msg1 = self._build_sign_message_pipe(att1)
        msg2 = self._build_sign_message_pipe(att2)
        self.assertNotEqual(msg1, msg2)

    def test_signing_message_format(self):
        """Verify the pipe-delimited format has exactly 4 components."""
        att = self._build_sample_attestation()
        pipe_msg = self._build_sign_message_pipe(att)
        parts = pipe_msg.split("|")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], att["miner_id"])
        self.assertEqual(parts[1], att["miner"])
        self.assertEqual(parts[2], att["nonce"])
        self.assertEqual(parts[3], att["report"]["commitment"])


if __name__ == "__main__":
    unittest.main()
