# SPDX-License-Identifier: MIT
"""
Test: P2P epoch proposal merkle self-validation flaw

Vulnerability:
  GossipLayer._handle_epoch_propose() validates the merkle root by computing
  it from the proposal's own `distribution` field and comparing it to the
  proposal's own `merkle_root`.  This is tautological — it only proves the
  proposer didn't make a typo in their own hash.  It never checks whether
  distribution recipients are actually attested miners in miner_attest_recent.

  A malicious epoch leader can craft a proposal paying only themselves,
  compute the correct merkle root for that fake distribution, and all
  receiving nodes will vote "accept" because the merkle check passes.

Fix:
  After the merkle internal-consistency check, _handle_epoch_propose now
  queries miner_attest_recent and rejects any proposal whose distribution
  includes recipients not present in the locally attested miner set.
"""

import os
import sys
import json
import sqlite3
import unittest
import tempfile
import time
import hmac
import hashlib
from unittest.mock import patch

TEST_P2P_SECRET = "test_hmac_secret_for_unit_tests_only_32chars"
os.environ.setdefault("RC_P2P_SECRET", TEST_P2P_SECRET)

# Add node directory to path
NODE_DIR = os.path.join(os.path.dirname(__file__), '..', 'node')
sys.path.insert(0, NODE_DIR)

from rustchain_p2p_gossip import GossipLayer, GossipMessage, MessageType


class TestEpochProposalMerkleValidation(unittest.TestCase):
    """Validate that epoch proposals with unattested recipients are rejected."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self._init_db()
        self.secret = TEST_P2P_SECRET
        self._patch_secret()
        # Peers: node2, node3. Self: node1.
        # Sorted nodes: [node1, node2, node3]. node1 leads epochs 0,3,6,9...
        self.gossip = self._make_gossip()

    def tearDown(self):
        try:
            os.close(self.db_fd)
        except OSError:
            pass
        try:
            os.unlink(self.db_path)
        except OSError:
            pass
        import rustchain_p2p_gossip as mod
        mod.P2P_SECRET = self._orig_secret

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE miner_attest_recent (
                    miner TEXT PRIMARY KEY,
                    ts_ok INTEGER NOT NULL,
                    device_family TEXT,
                    device_arch TEXT,
                    entropy_score REAL DEFAULT 0,
                    fingerprint_passed INTEGER DEFAULT 0
                );
                CREATE TABLE epoch_state (
                    epoch INTEGER PRIMARY KEY,
                    settled INTEGER DEFAULT 0,
                    settled_ts INTEGER
                );
            """)

    def _patch_secret(self):
        import rustchain_p2p_gossip as mod
        self._orig_secret = mod.P2P_SECRET
        mod.P2P_SECRET = self.secret

    def _make_gossip(self, peers=None):
        if peers is None:
            peers = {"node2": "http://127.0.0.1:9001", "node3": "http://127.0.0.1:9002"}
        return GossipLayer("node1", peers, self.db_path)

    def _make_proposal_message(self, epoch, proposer, distribution, merkle_root=None):
        """Craft an EPOCH_PROPOSE message with the given distribution."""
        if merkle_root is None:
            sorted_dist = sorted(distribution.items())
            merkle_root = hashlib.sha256(
                json.dumps(sorted_dist, sort_keys=True).encode()
            ).hexdigest()

        proposal_hash = hashlib.sha256(
            f"{epoch}:{merkle_root}".encode()
        ).hexdigest()[:24]

        payload = {
            "epoch": epoch,
            "proposer": proposer,
            "distribution": distribution,
            "merkle_root": merkle_root,
            "proposal_hash": proposal_hash,
            "timestamp": int(time.time()),
        }

        content = f"{MessageType.EPOCH_PROPOSE.value}:{json.dumps(payload, sort_keys=True)}"
        timestamp = int(time.time())
        message = f"{content}:{timestamp}"
        sig = hmac.new(
            self.secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        return GossipMessage(
            msg_type=MessageType.EPOCH_PROPOSE.value,
            msg_id=hashlib.sha256(f"{content}:{timestamp}".encode()).hexdigest()[:24],
            sender_id=proposer,
            timestamp=timestamp,
            ttl=3,
            signature=sig,
            payload=payload,
        )

    def _insert_attested_miner(self, miner_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO miner_attest_recent "
                "(miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (miner_id, int(time.time()), "x86", "modern", 0.85, 1)
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_self_paying_distribution_rejected(self):
        """Proposal paying only the proposer (not attested) must be rejected."""
        # Epoch 0: node1 is leader (0 % 3 == 0)
        msg = self._make_proposal_message(
            epoch=0, proposer="node1",
            distribution={"attacker_wallet": 1.5},
        )
        result = self.gossip._handle_epoch_propose(msg)
        self.assertEqual(result["vote"], "reject")
        self.assertEqual(result["reason"], "unattested_recipient")

    def test_partial_unattested_recipients_rejected(self):
        """Proposal with some valid miners AND an unattested recipient must be rejected."""
        self._insert_attested_miner("legit_miner_1")
        self._insert_attested_miner("legit_miner_2")

        msg = self._make_proposal_message(
            epoch=3, proposer="node1",
            distribution={
                "legit_miner_1": 0.5,
                "legit_miner_2": 0.5,
                "attacker_wallet": 0.5,
            },
        )
        result = self.gossip._handle_epoch_propose(msg)
        self.assertEqual(result["vote"], "reject")
        self.assertEqual(result["reason"], "unattested_recipient")

    def test_valid_distribution_accepted(self):
        """Proposal with only attested miners should be accepted."""
        self._insert_attested_miner("miner_a")
        self._insert_attested_miner("miner_b")

        msg = self._make_proposal_message(
            epoch=6, proposer="node1",
            distribution={"miner_a": 0.75, "miner_b": 0.75},
        )
        result = self.gossip._handle_epoch_propose(msg)
        self.assertEqual(result["vote"], "accept")

    def test_merkle_mismatch_still_rejected(self):
        """Wrong merkle root should still be rejected."""
        self._insert_attested_miner("miner_a")

        msg = self._make_proposal_message(
            epoch=9, proposer="node1",
            distribution={"miner_a": 1.5},
            merkle_root="deadbeef" * 8,
        )
        result = self.gossip._handle_epoch_propose(msg)
        self.assertEqual(result["vote"], "reject")
        self.assertEqual(result["reason"], "merkle_root_mismatch")

    def test_empty_distribution_accepted(self):
        """Empty distribution with correct merkle root should pass."""
        msg = self._make_proposal_message(
            epoch=12, proposer="node1",
            distribution={},
        )
        result = self.gossip._handle_epoch_propose(msg)
        self.assertEqual(result["vote"], "accept")

    def test_invalid_leader_rejected_before_merkle(self):
        """Invalid proposer rejected before merkle validation."""
        self._insert_attested_miner("miner_a")
        # Epoch 1: leader is node2, not node999
        msg = self._make_proposal_message(
            epoch=1, proposer="node999",
            distribution={"miner_a": 1.5},
        )
        result = self.gossip._handle_epoch_propose(msg)
        self.assertEqual(result["status"], "reject")
        self.assertEqual(result["reason"], "invalid_leader")

    def test_miner_removed_between_epochs(self):
        """Miner attested in epoch N but removed by N+1 should not receive rewards in N+1."""
        self._insert_attested_miner("departed_miner")

        # Epoch 0: miner is attested
        msg1 = self._make_proposal_message(
            epoch=0, proposer="node1",
            distribution={"departed_miner": 1.5},
        )
        self.assertEqual(
            self.gossip._handle_epoch_propose(msg1)["vote"], "accept"
        )

        # Remove miner from attestation table
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM miner_attest_recent WHERE miner=?",
                         ("departed_miner",))
            conn.commit()

        # Epoch 3: miner no longer attested
        msg2 = self._make_proposal_message(
            epoch=3, proposer="node1",
            distribution={"departed_miner": 1.5},
        )
        result = self.gossip._handle_epoch_propose(msg2)
        self.assertEqual(result["vote"], "reject")
        self.assertEqual(result["reason"], "unattested_recipient")

    def test_db_error_rejects_safely(self):
        """If DB query fails, proposal should be rejected (fail-safe)."""
        self._insert_attested_miner("miner_a")

        msg = self._make_proposal_message(
            epoch=15, proposer="node1",
            distribution={"miner_a": 1.5},
        )

        # Mock sqlite3.connect to raise an exception
        with patch("sqlite3.connect", side_effect=sqlite3.OperationalError("DB locked")):
            result = self.gossip._handle_epoch_propose(msg)
        self.assertEqual(result["vote"], "reject")
        self.assertEqual(result["reason"], "attested_miners_query_error")


if __name__ == '__main__':
    unittest.main()
