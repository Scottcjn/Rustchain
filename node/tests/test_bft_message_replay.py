# SPDX-License-Identifier: MIT
"""
Tests for BFT consensus message replay prevention.

Covers the fix for: Cross-epoch BFT consensus message replay.
The BFT module previously accepted stale PREPARE/COMMIT messages because
handle_prepare() and handle_commit() never checked timestamp freshness
against CONSENSUS_MESSAGE_TTL, and _check_prepare_quorum() did not verify
that all prepares share the same digest as the PRE-PREPARE.
"""

import importlib.util
import os
import sys
import time
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_bft_consensus.py")

spec = importlib.util.spec_from_file_location("rustchain_bft_consensus", MODULE_PATH)
bft_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bft_mod)

BFTConsensus = bft_mod.BFTConsensus
ConsensusMessage = bft_mod.ConsensusMessage
CONSENSUS_MESSAGE_TTL = bft_mod.CONSENSUS_MESSAGE_TTL
MessageType = bft_mod.MessageType
ConsensusPhase = bft_mod.ConsensusPhase


def _make_bft(node_id="node-1", db_path=":memory:", secret="test-secret-key"):
    """Create a BFTConsensus instance with a peer to enable quorum calculations."""
    bft = BFTConsensus(node_id, db_path, secret)
    bft.register_peer("node-2", "http://127.0.0.1:9001")
    bft.register_peer("node-3", "http://127.0.0.1:9002")
    return bft


def _make_prepare_msg(bft, epoch=1, view=None, digest="abc123", timestamp=None, node_id="node-2"):
    """Craft a PREPARE message signed by the given node_id."""
    if view is None:
        view = bft.current_view
    if timestamp is None:
        timestamp = int(time.time())
    sign_data = f"{MessageType.PREPARE.value}:{view}:{epoch}:{digest}:{timestamp}"
    signature = bft._sign_message(sign_data)
    return ConsensusMessage(
        msg_type=MessageType.PREPARE.value,
        view=view,
        epoch=epoch,
        digest=digest,
        node_id=node_id,
        signature=signature,
        timestamp=timestamp,
    )


def _make_commit_msg(bft, epoch=1, view=None, digest="abc123", timestamp=None, node_id="node-2"):
    """Craft a COMMIT message signed by the given node_id."""
    if view is None:
        view = bft.current_view
    if timestamp is None:
        timestamp = int(time.time())
    sign_data = f"{MessageType.COMMIT.value}:{view}:{epoch}:{digest}:{timestamp}:{timestamp}"
    # Actually the sign_data format in handle_commit uses the msg fields directly
    sign_data = f"{MessageType.COMMIT.value}:{view}:{epoch}:{digest}:{timestamp}"
    signature = bft._sign_message(sign_data)
    return ConsensusMessage(
        msg_type=MessageType.COMMIT.value,
        view=view,
        epoch=epoch,
        digest=digest,
        node_id=node_id,
        signature=signature,
        timestamp=timestamp,
    )


class TestPrepareTimestampFreshness(unittest.TestCase):
    """Stale PREPARE messages (older than CONSENSUS_MESSAGE_TTL) must be rejected."""

    def test_stale_prepare_rejected(self):
        bft = _make_bft()
        stale_ts = int(time.time()) - CONSENSUS_MESSAGE_TTL - 60  # 6 minutes old
        msg = _make_prepare_msg(bft, timestamp=stale_ts)
        bft.handle_prepare(msg)
        # Should not be stored
        self.assertNotIn(1, bft.prepare_log)

    def test_fresh_prepare_accepted(self):
        bft = _make_bft()
        msg = _make_prepare_msg(bft, timestamp=int(time.time()))
        bft.handle_prepare(msg)
        self.assertIn(1, bft.prepare_log)
        self.assertIn("node-2", bft.prepare_log[1])


class TestCommitTimestampFreshness(unittest.TestCase):
    """Stale COMMIT messages must be rejected."""

    def test_stale_commit_rejected(self):
        bft = _make_bft()
        stale_ts = int(time.time()) - CONSENSUS_MESSAGE_TTL - 60
        msg = _make_commit_msg(bft, timestamp=stale_ts)
        bft.handle_commit(msg)
        self.assertNotIn(1, bft.commit_log)

    def test_fresh_commit_accepted(self):
        bft = _make_bft()
        msg = _make_commit_msg(bft, timestamp=int(time.time()))
        bft.handle_commit(msg)
        self.assertIn(1, bft.commit_log)
        self.assertIn("node-2", bft.commit_log[1])


class TestCommitViewValidation(unittest.TestCase):
    """COMMIT messages with wrong view must be rejected."""

    def test_commit_wrong_view_rejected(self):
        bft = _make_bft()
        bft.current_view = 5
        msg = _make_commit_msg(bft, view=3)  # wrong view
        bft.handle_commit(msg)
        self.assertNotIn(1, bft.commit_log)

    def test_commit_correct_view_accepted(self):
        bft = _make_bft()
        bft.current_view = 5
        msg = _make_commit_msg(bft, view=5)
        bft.handle_commit(msg)
        self.assertIn(1, bft.commit_log)


class TestPrepareDigestConsistency(unittest.TestCase):
    """PREPARE messages with digest not matching the PRE-PREPARE must be rejected."""

    def test_prepare_digest_mismatch_rejected(self):
        bft = _make_bft()
        # Simulate a PRE-PREPARE with digest "correct-digest"
        pre_prepare = ConsensusMessage(
            msg_type=MessageType.PRE_PREPARE.value,
            view=0,
            epoch=1,
            digest="correct-digest",
            node_id=bft.get_leader(0),
            signature="sig",
            timestamp=int(time.time()),
        )
        bft.pre_prepare_log[1] = pre_prepare

        # PREPARE with wrong digest
        msg = _make_prepare_msg(bft, epoch=1, digest="wrong-digest")
        bft.handle_prepare(msg)
        self.assertNotIn(1, bft.prepare_log)

    def test_prepare_digest_match_accepted(self):
        bft = _make_bft()
        correct_digest = "correct-digest"
        pre_prepare = ConsensusMessage(
            msg_type=MessageType.PRE_PREPARE.value,
            view=0,
            epoch=1,
            digest=correct_digest,
            node_id=bft.get_leader(0),
            signature="sig",
            timestamp=int(time.time()),
        )
        bft.pre_prepare_log[1] = pre_prepare

        msg = _make_prepare_msg(bft, epoch=1, digest=correct_digest)
        bft.handle_prepare(msg)
        self.assertIn(1, bft.prepare_log)

    def test_prepare_without_pre_prepare_accepted(self):
        """PREPARE arriving before PRE-PREPARE should still be stored (ordering flexibility)."""
        bft = _make_bft()
        msg = _make_prepare_msg(bft, epoch=1, digest="some-digest")
        bft.handle_prepare(msg)
        # Stored because no PRE-PREPARE yet to compare against
        self.assertIn(1, bft.prepare_log)


class TestCommitDigestConsistency(unittest.TestCase):
    """COMMIT messages with digest not matching the PRE-PREPARE must be rejected."""

    def test_commit_digest_mismatch_rejected(self):
        bft = _make_bft()
        pre_prepare = ConsensusMessage(
            msg_type=MessageType.PRE_PREPARE.value,
            view=0,
            epoch=1,
            digest="correct-digest",
            node_id=bft.get_leader(0),
            signature="sig",
            timestamp=int(time.time()),
        )
        bft.pre_prepare_log[1] = pre_prepare

        msg = _make_commit_msg(bft, epoch=1, digest="wrong-digest")
        bft.handle_commit(msg)
        self.assertNotIn(1, bft.commit_log)


class TestQuorumDigestConsistency(unittest.TestCase):
    """_check_prepare_quorum must verify all prepares share the PRE-PREPARE digest."""

    def test_quorum_filters_mismatched_digests(self):
        bft = _make_bft()
        correct_digest = "correct-digest"
        wrong_digest = "wrong-digest"

        # Set up PRE-PREPARE
        pre_prepare = ConsensusMessage(
            msg_type=MessageType.PRE_PREPARE.value,
            view=0,
            epoch=1,
            digest=correct_digest,
            node_id=bft.get_leader(0),
            signature="sig",
            timestamp=int(time.time()),
        )
        bft.pre_prepare_log[1] = pre_prepare

        # Manually inject prepares with mixed digests (simulating race condition)
        ts = int(time.time())
        for nid, dig in [("node-1", correct_digest), ("node-2", wrong_digest), ("node-3", correct_digest)]:
            sign_data = f"{MessageType.PREPARE.value}:0:1:{dig}:{ts}"
            sig = bft._sign_message(sign_data)
            bft.prepare_log[1] = bft.prepare_log.get(1, {})
            bft.prepare_log[1][nid] = ConsensusMessage(
                msg_type=MessageType.PREPARE.value,
                view=0, epoch=1, digest=dig,
                node_id=nid, signature=sig, timestamp=ts,
            )

        bft.phase = ConsensusPhase.PREPARE
        bft._check_prepare_quorum(1)

        # The wrong-digest prepare should have been filtered out
        self.assertNotIn("node-2", bft.prepare_log[1])
        # 2 valid prepares remain. With 3 total nodes, quorum = (2*3+2)//3 = 2,
        # so quorum IS reached and phase transitions to COMMIT.
        self.assertEqual(bft.phase, ConsensusPhase.COMMIT)

    def test_quorum_prevents_commit_when_digests_filtered(self):
        """With more peers, filtering mismatched digests should prevent quorum."""
        bft = _make_bft()
        # Add 2 more peers to get 6 total nodes → quorum = (2*6+2)//3 = 4
        bft.register_peer("node-4", "http://127.0.0.1:9003")
        bft.register_peer("node-5", "http://127.0.0.1:9004")

        correct_digest = "correct-digest"
        wrong_digest = "wrong-digest"

        pre_prepare = ConsensusMessage(
            msg_type=MessageType.PRE_PREPARE.value,
            view=0,
            epoch=1,
            digest=correct_digest,
            node_id=bft.get_leader(0),
            signature="sig",
            timestamp=int(time.time()),
        )
        bft.pre_prepare_log[1] = pre_prepare

        # 3 correct + 1 wrong = 4 total, but after filtering only 3 remain
        ts = int(time.time())
        for nid, dig in [("node-1", correct_digest), ("node-2", wrong_digest),
                          ("node-3", correct_digest), ("node-4", correct_digest)]:
            sign_data = f"{MessageType.PREPARE.value}:0:1:{dig}:{ts}"
            sig = bft._sign_message(sign_data)
            bft.prepare_log[1] = bft.prepare_log.get(1, {})
            bft.prepare_log[1][nid] = ConsensusMessage(
                msg_type=MessageType.PREPARE.value,
                view=0, epoch=1, digest=dig,
                node_id=nid, signature=sig, timestamp=ts,
            )

        bft.phase = ConsensusPhase.PREPARE
        bft._check_prepare_quorum(1)

        # After filtering: 3 valid prepares, but quorum = 4 → no COMMIT
        self.assertNotIn("node-2", bft.prepare_log[1])
        self.assertEqual(len(bft.prepare_log[1]), 3)
        self.assertEqual(bft.phase, ConsensusPhase.PREPARE)


if __name__ == "__main__":
    unittest.main()
