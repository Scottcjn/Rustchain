#!/usr/bin/env python3
"""
Regression tests for the airdrop wallet-address de-duplication invariant.

Base (EVM) addresses are case-insensitive on-chain: 0xAbCd..., 0xabcd... and
0xABCD... are the *same* account and eth_getBalance returns the same balance
for every casing. The airdrop enforces "one claim per wallet" via _has_claimed
and UNIQUE(github_username, wallet_address, chain). Before the fix, the wallet
half of that invariant compared raw strings, so the same physical Base wallet
could collect the airdrop multiple times (once per GitHub identity) simply by
varying hex case — draining the Base allocation.

Solana uses base58, which IS case-sensitive, so different casings there are
genuinely different wallets and must stay allowed.
"""
import unittest

from airdrop_v2 import AirdropV2


class TestWalletCaseDedup(unittest.TestCase):
    def setUp(self):
        self.a = AirdropV2(":memory:")

    def test_base_same_wallet_different_case_cannot_double_claim(self):
        """Same Base wallet in different hex casing must NOT claim twice."""
        checksum = "0xAbCdEf0000000000000000000000000000000001"
        lower = "0xabcdef0000000000000000000000000000000001"
        upper = "0xABCDEF0000000000000000000000000000000001"

        ok1, _, _ = self.a.claim_airdrop(
            "alice", checksum, "base", "contributor", skip_antisybil=True
        )
        ok2, msg2, _ = self.a.claim_airdrop(
            "bob", lower, "base", "contributor", skip_antisybil=True
        )
        ok3, _, _ = self.a.claim_airdrop(
            "carol", upper, "base", "contributor", skip_antisybil=True
        )

        self.assertTrue(ok1)
        self.assertFalse(ok2, "lowercased same Base wallet should be rejected")
        self.assertFalse(ok3, "uppercased same Base wallet should be rejected")
        self.assertIn("already exists", msg2.lower())

        base = self.a.get_allocation_status()["base"]
        # Exactly one 'contributor' reward (50 wRTC) charged, not two or three.
        self.assertEqual(base["claimed_wrtc"], 50.0)

    def test_base_eligibility_check_rejects_case_variant(self):
        """check_eligibility must also see the canonical form."""
        self.a.claim_airdrop(
            "alice",
            "0xAbCdEf0000000000000000000000000000000001",
            "base",
            "contributor",
            skip_antisybil=True,
        )
        res = self.a.check_eligibility(
            "bob",
            "0xABCDEF0000000000000000000000000000000001",
            "base",
            skip_antisybil=True,
        )
        self.assertFalse(res.eligible)

    def test_solana_case_sensitivity_preserved(self):
        """base58 Solana addresses are case-sensitive: distinct casings are
        distinct wallets and must remain independently claimable."""
        ok1, _, _ = self.a.claim_airdrop(
            "carol", "AbCdEfSol111", "solana", "contributor", skip_antisybil=True
        )
        ok2, _, _ = self.a.claim_airdrop(
            "dave", "abcdefSol111", "solana", "contributor", skip_antisybil=True
        )
        self.assertTrue(ok1)
        self.assertTrue(ok2)
        self.assertEqual(self.a.get_allocation_status()["solana"]["claimed_wrtc"], 100.0)


if __name__ == "__main__":
    unittest.main()
