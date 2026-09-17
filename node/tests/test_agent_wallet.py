# SPDX-License-Identifier: MIT
"""Unit tests for AI Agent Vanity Wallets & Hardware Binding (Bounty #30)."""

import unittest
from node.agent_wallet import (
    generate_agent_vanity_wallet,
    verify_agent_hardware_binding,
    construct_agent_attestation_payload
)

class TestAgentWalletSystem(unittest.TestCase):
    def test_vanity_wallet_generation(self):
        hw_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ok, msg, wallet = generate_agent_vanity_wallet("claude", hw_hash)
        self.assertTrue(ok)
        self.assertTrue(wallet.startswith("RTC-claude-"))
        self.assertEqual(len(wallet.split("-")), 3)

        # Same hardware + agent = deterministic same wallet
        ok2, _, wallet2 = generate_agent_vanity_wallet("claude", hw_hash)
        self.assertEqual(wallet, wallet2)

        # Reserved names rejected
        ok, msg, _ = generate_agent_vanity_wallet("founder", hw_hash)
        self.assertFalse(ok)
        self.assertIn("reserved", msg)

    def test_hardware_binding_verification(self):
        reg = {
            "agent_name": "claude",
            "hardware_fingerprint_hash": "hash-machine-a"
        }
        self.assertTrue(verify_agent_hardware_binding(reg, "hash-machine-a"))
        self.assertFalse(verify_agent_hardware_binding(reg, "hash-machine-b"))

    def test_agent_attestation_construction(self):
        payload = construct_agent_attestation_payload(
            miner_vanity_wallet="RTC-claude-a7f3b2",
            agent_type="claude-code",
            agent_version="2.1.29",
            hardware_fingerprint={"device_family": "x86_64", "is_likely_vm": False},
            proof_of_work={"type": "github_commits", "prs_merged": 5}
        )
        self.assertIn("agent_challenge_digest", payload)
        self.assertEqual(payload["miner"], "RTC-claude-a7f3b2")

if __name__ == "__main__":
    unittest.main()
