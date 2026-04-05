#!/usr/bin/env python3
"""
Tests for BFT digest validation in PREPARE/COMMIT handlers (CRIT-BFT-2).

Demonstrates that PREPARE and COMMIT messages with a digest that doesn't
match the PRE-PREPARE proposal are rejected, preventing equivocation.
"""

import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rustchain_bft_consensus import (
    BFTConsensus, ConsensusMessage, MessageType, ConsensusPhase
)

SECRET_KEY = "test_bft_digest_validation_2025"


class TestBFTDigestValidation(unittest.TestCase):
    """CRIT-BFT-2: PREPARE/COMMIT must validate digest matches pre-prepare."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.bft = BFTConsensus("node-A", self.tmp.name, SECRET_KEY)
        self.bft.register_peer("node-B", "http://localhost:9001")
        self.bft.register_peer("node-C", "http://localhost:9002")
        self.bft.register_peer("node-D", "http://localhost:9003")

        # Inject a PRE-PREPARE so the digest is known
        self.test_epoch = 100
        self.real_digest = hashlib.sha256(b"real_proposal").hexdigest()
        self.fake_digest = hashlib.sha256(b"fake_proposal").hexdigest()

        ts = int(time.time())
        sign_data = f"{MessageType.PRE_PREPARE.value}:{self.bft.current_view}:{self.test_epoch}:{self.real_digest}:{ts}"
        sig = self.bft._sign_message(sign_data)

        pre_prepare = ConsensusMessage(
            msg_type=MessageType.PRE_PREPARE.value,
            view=self.bft.current_view,
            epoch=self.test_epoch,
            digest=self.real_digest,
            node_id="node-B",  # pretend node-B is leader
            signature=sig,
            timestamp=ts,
            proposal={"epoch": self.test_epoch, "data": "real"}
        )
        self.bft.pre_prepare_log[self.test_epoch] = pre_prepare

    def tearDown(self):
        self.bft._cancel_view_change_timer()
        try:
            os.unlink(self.tmp.name)
        except PermissionError:
            pass

    def _make_prepare(self, node_id: str, digest: str) -> ConsensusMessage:
        ts = int(time.time())
        sign_data = f"{MessageType.PREPARE.value}:{self.bft.current_view}:{self.test_epoch}:{digest}:{ts}"
        sig = self.bft._sign_message(sign_data)
        return ConsensusMessage(
            msg_type=MessageType.PREPARE.value,
            view=self.bft.current_view,
            epoch=self.test_epoch,
            digest=digest,
            node_id=node_id,
            signature=sig,
            timestamp=ts,
        )

    def _make_commit(self, node_id: str, digest: str) -> ConsensusMessage:
        ts = int(time.time())
        sign_data = f"{MessageType.COMMIT.value}:{self.bft.current_view}:{self.test_epoch}:{digest}:{ts}"
        sig = self.bft._sign_message(sign_data)
        return ConsensusMessage(
            msg_type=MessageType.COMMIT.value,
            view=self.bft.current_view,
            epoch=self.test_epoch,
            digest=digest,
            node_id=node_id,
            signature=sig,
            timestamp=ts,
        )

    # -- PREPARE tests -------------------------------------------------------

    def test_prepare_matching_digest_accepted(self):
        """PREPARE with correct digest must be accepted."""
        msg = self._make_prepare("node-C", self.real_digest)
        self.bft.handle_prepare(msg)
        self.assertIn("node-C", self.bft.prepare_log.get(self.test_epoch, {}))

    def test_prepare_wrong_digest_rejected(self):
        """PREPARE with wrong digest must be rejected (equivocation attack)."""
        msg = self._make_prepare("node-C", self.fake_digest)
        self.bft.handle_prepare(msg)
        self.assertNotIn("node-C", self.bft.prepare_log.get(self.test_epoch, {}))

    # -- COMMIT tests --------------------------------------------------------

    def test_commit_matching_digest_accepted(self):
        """COMMIT with correct digest must be accepted."""
        msg = self._make_commit("node-C", self.real_digest)
        self.bft.handle_commit(msg)
        self.assertIn("node-C", self.bft.commit_log.get(self.test_epoch, {}))

    def test_commit_wrong_digest_rejected(self):
        """COMMIT with wrong digest must be rejected (equivocation attack)."""
        msg = self._make_commit("node-C", self.fake_digest)
        self.bft.handle_commit(msg)
        self.assertNotIn("node-C", self.bft.commit_log.get(self.test_epoch, {}))

    def test_equivocation_cannot_reach_quorum(self):
        """Byzantine nodes sending different digests cannot reach quorum.

        Before the fix, 2 honest nodes (real digest) + 1 Byzantine node
        (fake digest) would all count toward prepare quorum for the epoch,
        even though they disagree on the proposal content.
        """
        # 2 honest prepares with real digest
        self.bft.handle_prepare(self._make_prepare("node-B", self.real_digest))
        self.bft.handle_prepare(self._make_prepare("node-C", self.real_digest))

        # 1 Byzantine prepare with fake digest — should be REJECTED
        self.bft.handle_prepare(self._make_prepare("node-D", self.fake_digest))

        # Only 2 prepares should be in the log (not 3)
        self.assertEqual(
            len(self.bft.prepare_log.get(self.test_epoch, {})), 2,
            "Byzantine node's mismatched digest should not count toward quorum"
        )


if __name__ == "__main__":
    unittest.main()
