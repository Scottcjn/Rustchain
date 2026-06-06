"""
Regression test for issue #6894:
Windows miner silently downgrades Ed25519 attestations to unsigned.

Root cause: build_pipe_sign_message() required a top-level attestation['nonce'],
but the Windows miner only stores the nonce inside report.nonce.  The resulting
KeyError was swallowed by the signing guard and the attestation was submitted
without a signature.

After the fix, the helper mirrors the node verifier's nonce precedence:
report.nonce first, then top-level nonce.
"""
import json
import hashlib
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "miners"))

from signing_helpers import build_pipe_sign_message


def _windows_attestation(nonce="a1b2c3d4"):
    """Build an attestation shaped like the Windows miner produces it —
    nonce lives ONLY inside report, NOT at the top level."""
    wallet = "RTCf69dd944558d4e843a4a676495a97638055caea2"
    miner_id = "windows_dbe53391"
    entropy = {"variance_ns": 88.1, "source": "timer_jitter"}
    commitment = hashlib.sha256(
        (nonce + wallet + json.dumps(entropy, sort_keys=True)).encode()
    ).hexdigest()
    return {
        "miner": wallet,
        "miner_id": miner_id,
        # NOTE: no top-level "nonce" — this is the Windows payload shape
        "report": {
            "nonce": nonce,
            "commitment": commitment,
            "derived": entropy,
            "entropy_score": entropy.get("variance_ns", 0.0),
        },
        "device": {
            "family": "x86",
            "arch": "x86_64",
            "model": "Intel(R) Core(TM) i7",
            "cpu": "Intel(R) Core(TM) i7",
            "cores": 8,
        },
        "signals": {"macs": ["AA:BB:CC:DD:EE:FF"], "hostname": "win-miner"},
    }


class TestWindowsAttestationNonce(unittest.TestCase):
    """Signing helper must work with the Windows payload shape."""

    def test_windows_payload_no_top_level_nonce(self):
        """The Windows attestation (no top-level nonce) must produce valid
        signing bytes without raising."""
        att = _windows_attestation()
        msg = build_pipe_sign_message(att)
        self.assertIsInstance(msg, bytes)
        # Should contain all four pipe-separated fields
        parts = msg.decode("utf-8").split("|")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], att["miner_id"])
        self.assertEqual(parts[1], att["miner"])
        # Nonce comes from report
        self.assertEqual(parts[2], att["report"]["nonce"])
        self.assertEqual(parts[3], att["report"]["commitment"])

    def test_report_nonce_preferred_over_top_level(self):
        """When both report.nonce and top-level nonce exist, report.nonce
        should win — matching the node verifier's precedence."""
        att = _windows_attestation(nonce="report-nonce-val")
        att["nonce"] = "top-level-nonce-val"  # add a conflicting top-level
        msg = build_pipe_sign_message(att)
        parts = msg.decode("utf-8").split("|")
        # report.nonce must be used, not the top-level one
        self.assertEqual(parts[2], "report-nonce-val")

    def test_top_level_nonce_fallback(self):
        """If report has no nonce but top-level does, use top-level."""
        att = _windows_attestation()
        # Remove nonce from report, put it at top level instead
        del att["report"]["nonce"]
        att["nonce"] = "top-level-only-nonce"
        msg = build_pipe_sign_message(att)
        parts = msg.decode("utf-8").split("|")
        self.assertEqual(parts[2], "top-level-only-nonce")

    def test_no_nonce_anywhere_raises(self):
        """Missing nonce in both locations must raise ValueError."""
        att = _windows_attestation()
        del att["report"]["nonce"]
        with self.assertRaises(ValueError):
            build_pipe_sign_message(att)

    def test_linux_payload_still_works(self):
        """Linux-shaped payload (top-level + report nonce) still works."""
        nonce = "linux-nonce-999"
        wallet = "RTC1EXAMPLEWALLET"
        miner_id = "linux_abc123"
        entropy = {"variance_ns": 42.5, "source": "timer_jitter"}
        commitment = hashlib.sha256(
            (nonce + wallet + json.dumps(entropy, sort_keys=True)).encode()
        ).hexdigest()
        att = {
            "miner": wallet,
            "miner_id": miner_id,
            "nonce": nonce,  # Linux sets top-level nonce
            "report": {
                "nonce": nonce,
                "commitment": commitment,
                "derived": entropy,
            },
        }
        msg = build_pipe_sign_message(att)
        parts = msg.decode("utf-8").split("|")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[2], nonce)

    def test_windows_round_trip_matches_node(self):
        """The bytes produced for a Windows attestation match the node
        verifier's 4-part reconstruction exactly."""
        att = _windows_attestation()
        miner_bytes = build_pipe_sign_message(att)
        # Node verifier reconstructs:
        # miner_id|miner|nonce|commitment  where nonce comes from report
        node_str = "{}|{}|{}|{}".format(
            att["miner_id"],
            att["miner"],
            att["report"]["nonce"],
            att["report"]["commitment"],
        )
        self.assertEqual(miner_bytes, node_str.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
