#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Security Finding: EPOCH_COMMIT gossip never applied on receiving nodes

Severity: Medium (25 RTC)
Bounty: #2867

Root Cause
----------
handle_message() has no case for MessageType.EPOCH_COMMIT. When the epoch-quorum
originator broadcasts a commit, every other node receives it, validates the
signature, deduplicates, then falls through to the TTL-forward block — which
re-broadcasts the message but never calls epoch_crdt.add(). The originator is
the only node that ever marks the epoch as finalized. All other nodes remain
permanently stale.

Consequence
-----------
- epoch_crdt.contains(epoch) returns False on every non-originating node
- PING responses report settled_epochs=0 across the network
- INV_EPOCH exchanges silently report need_data=True (stale) on all peers
- STATE sync carries the gap forward to newly-joining nodes

Fix
---
Add _handle_epoch_commit() that validates and applies epoch_crdt.add(), then
wire it into the handle_message() dispatch table.

This test imports and exercises the real GossipLayer from node/rustchain_p2p_gossip.py.
No re-implementations — the bug is reproduced on the actual production code path.
"""
import os
import sys
import tempfile

# Provide the required HMAC secret before any import of the gossip module
os.environ.setdefault("RC_P2P_SECRET", "a" * 64)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "node"))
from rustchain_p2p_gossip import GossipLayer, MessageType


def _make_node(node_id: str, peers: dict) -> GossipLayer:
    db = tempfile.mktemp(suffix=".db")
    return GossipLayer(node_id=node_id, peers=peers, db_path=db)


class TestEpochCommitHandler:
    """EPOCH_COMMIT must be applied to local epoch_crdt on every receiving node."""

    def test_receiving_node_marks_epoch_finalized(self):
        """Node B receives an EPOCH_COMMIT from A and should settle the epoch."""
        node_a = _make_node("node-A", {"node-B": "http://localhost:9001"})
        node_b = _make_node("node-B", {"node-A": "http://localhost:9000"})

        epoch = 42
        proposal_hash = "abc123def456"

        # A reaches quorum and broadcasts EPOCH_COMMIT (this also updates A's crdt)
        commit_msg = node_a.create_message(
            MessageType.EPOCH_COMMIT,
            {"epoch": epoch, "proposal_hash": proposal_hash, "accept_count": 3, "voters": ["node-A"]},
        )
        node_a.epoch_crdt.add(epoch, {"proposal_hash": proposal_hash, "finalized": True})

        # B must not yet know about this epoch
        assert not node_b.epoch_crdt.contains(epoch), \
            "node-B should not have epoch before receiving commit"

        # B receives and handles the commit
        result = node_b.handle_message(commit_msg)

        assert result.get("status") == "committed", f"expected 'committed', got {result}"
        assert node_b.epoch_crdt.contains(epoch), \
            "node-B epoch_crdt must contain epoch after handling EPOCH_COMMIT"

        meta = node_b.epoch_crdt.metadata.get(epoch, {})
        assert meta.get("finalized") is True
        assert meta.get("proposal_hash") == proposal_hash

    def test_idempotent_double_commit(self):
        """Receiving the same EPOCH_COMMIT twice must not corrupt state."""
        node_a = _make_node("node-A", {"node-B": "http://localhost:9001"})
        node_b = _make_node("node-B", {"node-A": "http://localhost:9000"})

        commit_msg = node_a.create_message(
            MessageType.EPOCH_COMMIT,
            {"epoch": 7, "proposal_hash": "deadbeef", "accept_count": 3, "voters": []},
        )

        r1 = node_b.handle_message(commit_msg)
        assert r1.get("status") == "committed"

        # Second delivery (replay / network duplicate) — msg_id already seen → dedup
        r2 = node_b.handle_message(commit_msg)
        assert r2.get("status") == "duplicate"

        assert node_b.epoch_crdt.contains(7)

    def test_missing_fields_rejected(self):
        """EPOCH_COMMIT with missing epoch or proposal_hash must be rejected cleanly."""
        # Create two nodes sharing the same secret (same process env) so signatures verify.
        node_a = _make_node("node-A", {"node-B": "http://localhost:9001"})
        node_b = _make_node("node-B", {"node-A": "http://localhost:9000"})

        bad_msg = node_a.create_message(
            MessageType.EPOCH_COMMIT,
            {"accept_count": 3},  # no epoch, no proposal_hash
        )

        result = node_b.handle_message(bad_msg)
        # Valid signature — hits handler, rejected for missing fields
        assert result.get("status") == "invalid", \
            f"expected 'invalid' for missing fields, got {result}"

    def test_multi_hop_all_nodes_converge(self):
        """
        Three-node chain: A commits → B receives → C receives from B.
        All nodes must end with epoch settled after the commit propagates.
        This is the primary consensus-convergence invariant.
        """
        node_a = _make_node("node-A", {"node-B": "http://localhost:9001"})
        node_b = _make_node("node-B", {"node-A": "http://localhost:9000", "node-C": "http://localhost:9002"})
        node_c = _make_node("node-C", {"node-B": "http://localhost:9001"})

        epoch = 99
        proposal_hash = "finalproposal"

        commit_msg = node_a.create_message(
            MessageType.EPOCH_COMMIT,
            {"epoch": epoch, "proposal_hash": proposal_hash, "accept_count": 3, "voters": []},
        )
        node_a.epoch_crdt.add(epoch, {"proposal_hash": proposal_hash, "finalized": True})

        # B receives from A
        rb = node_b.handle_message(commit_msg)
        assert rb.get("status") == "committed"
        assert node_b.epoch_crdt.contains(epoch)

        # C receives from B (same commit_msg — real network would re-sign, but the
        # dedup key differs per re-broadcast; simulate with a fresh seen_messages on C)
        node_c.seen_messages.clear()
        rc = node_c.handle_message(commit_msg)
        assert rc.get("status") in ("committed", "duplicate")
        assert node_c.epoch_crdt.contains(epoch), \
            "node-C must converge to finalized epoch after multi-hop commit"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
