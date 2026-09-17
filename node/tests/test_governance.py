# SPDX-License-Identifier: MIT
"""Unit tests for RustChain On-Chain Governance System (Bounty #50)."""

import sqlite3
import unittest
import time
from node.governance import (
    init_governance_db,
    create_proposal,
    cast_vote,
    tally_proposal,
    MIN_PROPOSAL_STAKE_RTC
)

class TestGovernanceSystem(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        init_governance_db(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_proposal_stake_threshold(self):
        ok, msg, pid = create_proposal(
            self.conn,
            proposer_wallet="RTCwallet1",
            title="Increase Vintage Multiplier",
            description="Boost PPC G4 multiplier",
            stake_amount=5.0  # below 10 RTC threshold
        )
        self.assertFalse(ok)
        self.assertIn("below minimum requirement", msg)

        ok, msg, pid = create_proposal(
            self.conn,
            proposer_wallet="RTCwallet1",
            title="Increase Vintage Multiplier",
            description="Boost PPC G4 multiplier",
            stake_amount=15.0
        )
        self.assertTrue(ok)
        self.assertIsNotNone(pid)

    def test_hardware_weighted_voting(self):
        ok, _, pid = create_proposal(
            self.conn,
            proposer_wallet="RTCwallet1",
            title="Ecosystem Parameter Change",
            description="Adjust epoch bounds",
            stake_amount=10.0
        )
        self.assertTrue(ok)

        # Voter A: 10 RTC with PowerPC G4 antiquity multiplier (2.5x) = 25 weight
        ok, msg = cast_vote(
            self.conn,
            proposal_id=pid,
            voter_wallet="RTCvoterA",
            miner_id="miner-ppc-g4",
            choice="yes",
            staked_rtc=10.0,
            antiquity_multiplier=2.5,
            signature="sigA",
            is_active_miner=True
        )
        self.assertTrue(ok)

        # Voter B: 20 RTC with modern bare-metal multiplier (1.0x) = 20 weight
        ok, msg = cast_vote(
            self.conn,
            proposal_id=pid,
            voter_wallet="RTCvoterB",
            miner_id="miner-x86",
            choice="no",
            staked_rtc=20.0,
            antiquity_multiplier=1.0,
            signature="sigB",
            is_active_miner=True
        )
        self.assertTrue(ok)

        tally = tally_proposal(self.conn, pid)
        self.assertEqual(tally["yes_weight"], 25.0)
        self.assertEqual(tally["no_weight"], 20.0)

    def test_duplicate_vote_rejection(self):
        ok, _, pid = create_proposal(
            self.conn,
            proposer_wallet="RTCwallet1",
            title="Proposal Test",
            description="Description",
            stake_amount=12.0
        )
        cast_vote(self.conn, pid, "RTCwallet1", "miner-1", "yes", 5.0, 1.0, "sig1")
        ok, msg = cast_vote(self.conn, pid, "RTCwallet1", "miner-1", "yes", 5.0, 1.0, "sig2")
        self.assertFalse(ok)
        self.assertIn("already voted", msg)

if __name__ == "__main__":
    unittest.main()
