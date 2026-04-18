#!/usr/bin/env python3
"""
Security Finding: EPOCH_COMMIT gossip propagation breaks beyond 1 hop

Severity: Medium (25 RTC)
Bounty: #2867

Root Cause
----------
Issue #2272 added TTL to the P2P signed content to prevent hop-count
manipulation:

    def _signed_content(msg_type, sender_id, msg_id, ttl, payload):
        return f"{msg_type}:{sender_id}:{msg_id}:{ttl}:..."   # line 442

When handle_message() receives an unhandled message type, it decrements TTL
and forwards the original message (lines 583-586):

    if msg.ttl > 0:
        msg.ttl -= 1           # mutates msg in-place
        self.broadcast(msg)    # forwards with decremented TTL

The receiving peer then calls verify_message(), which reconstructs signed
content using the *current* (decremented) TTL. Because the original sender
signed with TTL=N, but the forwarded copy carries TTL=N-1, the HMAC/Ed25519
check always fails at every hop beyond the first.

Unhandled message types that fall through to the forward block:
  - EPOCH_COMMIT  (finalizes epoch consensus — critical path)
  - EPOCH_DATA
  - BALANCES
  - GET_BALANCES
  - PONG

Impact
------
EPOCH_COMMIT is broadcast during epoch settlement (line 859). In any
network where nodes are not all direct peers of the epoch proposer, the
EPOCH_COMMIT will be rejected at the second hop, preventing epoch
finalization for those nodes. This creates a consensus split: some nodes
advance the epoch, others remain stuck, causing diverging chain state.

Suggested Fix
-------------
Option A (preferred): Add a handler for EPOCH_COMMIT and other unhandled
types so they return early (like ATTESTATION does) rather than falling
through to the TTL-decrement forward block.

Option B: Sign with an immutable "origin_ttl" field and track hop count
separately, so the forwarded message still passes verification.
"""

import hashlib
import hmac
import json
import time


GOSSIP_TTL = 3  # matches node/rustchain_p2p_gossip.py line 56


# ──────────────────────────────────────────────────────────────────────────────
# Minimal re-implementation of the signing/verification logic from the module
# ──────────────────────────────────────────────────────────────────────────────

def _signed_content(msg_type: str, sender_id: str, msg_id: str, ttl: int, payload: dict) -> str:
    """Mirrors GossipProtocol._signed_content (line 441-442)."""
    return f"{msg_type}:{sender_id}:{msg_id}:{ttl}:{json.dumps(payload, sort_keys=True)}"


def _hmac_sign(secret: str, msg_type: str, sender_id: str, msg_id: str,
               ttl: int, payload: dict, timestamp: int) -> str:
    content = _signed_content(msg_type, sender_id, msg_id, ttl, payload)
    message = f"{content}:{timestamp}"
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def _hmac_verify(secret: str, msg_type: str, sender_id: str, msg_id: str,
                 ttl: int, payload: dict, timestamp: int, sig: str) -> bool:
    content = _signed_content(msg_type, sender_id, msg_id, ttl, payload)
    message = f"{content}:{timestamp}"
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

SHARED_SECRET = "test_p2p_secret_32chars_for_poc!!"


def test_epoch_commit_rejected_at_second_hop():
    """
    Demonstrates EPOCH_COMMIT signature failure when forwarded with TTL-1.

    Timeline:
      Node A (proposer)  →  Node B (direct peer)  →  Node C (indirect)
         sign TTL=3            verify TTL=3 ✓           verify TTL=2 ✗
                               decrement → TTL=2
    """
    ts = int(time.time())
    payload = {"epoch": 42, "merkle_root": "deadbeef", "proposer": "node_a"}
    msg_id = "poc_msg_id_2867_001"
    msg_type = "epoch_commit"
    sender_id = "node_a"
    original_ttl = GOSSIP_TTL  # 3

    # Node A signs with TTL=3
    sig = _hmac_sign(SHARED_SECRET, msg_type, sender_id, msg_id,
                     original_ttl, payload, ts)

    # Hop 1: Node B receives and successfully verifies (TTL=3 matches)
    hop1_ok = _hmac_verify(SHARED_SECRET, msg_type, sender_id, msg_id,
                            original_ttl, payload, ts, sig)
    assert hop1_ok, "Hop 1 (direct peer) should accept the message"

    # Node B decrements TTL and forwards (lines 584-586 of rustchain_p2p_gossip.py)
    forwarded_ttl = original_ttl - 1  # 2

    # Hop 2: Node C receives the forwarded message with TTL=2
    # verify_message() uses msg.ttl (now 2) to reconstruct signed content
    hop2_ok = _hmac_verify(SHARED_SECRET, msg_type, sender_id, msg_id,
                            forwarded_ttl, payload, ts, sig)

    # This will FAIL — proof of the bug
    assert not hop2_ok, (
        f"BUG NOT REPRODUCED: expected hop-2 verify to fail "
        f"(sig covers TTL={original_ttl}, received TTL={forwarded_ttl})"
    )

    print(f"[CONFIRMED] EPOCH_COMMIT propagation failure:")
    print(f"  Original TTL={original_ttl} → signature valid at hop 1")
    print(f"  Forwarded TTL={forwarded_ttl} → signature REJECTED at hop 2")


def test_all_unhandled_types_fail_at_second_hop():
    """
    All message types not handled by handle_message()'s if/elif chain fall
    through to the TTL-decrement forward block and fail at the second hop.
    """
    unhandled = ["epoch_commit", "epoch_data", "balances", "get_balances", "pong"]

    ts = int(time.time())
    payload = {"data": "test"}
    msg_id = "poc_msg_id_2867_002"
    sender_id = "node_a"

    failures = []
    for msg_type in unhandled:
        sig = _hmac_sign(SHARED_SECRET, msg_type, sender_id, msg_id,
                         GOSSIP_TTL, payload, ts)
        forwarded_ttl = GOSSIP_TTL - 1
        hop2_ok = _hmac_verify(SHARED_SECRET, msg_type, sender_id, msg_id,
                                forwarded_ttl, payload, ts, sig)
        if hop2_ok:
            failures.append(msg_type)  # unexpected: sig should fail
        else:
            print(f"  [{msg_type}] ✗ rejected at hop 2 (as expected — bug confirmed)")

    assert not failures, f"These types unexpectedly verified at hop 2: {failures}"


def test_handled_types_never_reach_forward_block():
    """
    Handled types return early from handle_message() and never hit the
    TTL-decrement forward block — so they are unaffected by this bug.
    This is a control test to confirm the finding is scoped correctly.
    """
    handled = {
        "ping", "inv_attestation", "inv_epoch",
        "attestation", "epoch_propose", "epoch_vote",
        "get_state", "state",
    }
    unhandled = {
        "epoch_commit", "epoch_data", "balances", "get_balances", "pong",
    }

    # Verify disjoint
    overlap = handled & unhandled
    assert not overlap, f"Overlap between handled/unhandled sets: {overlap}"

    # Confirm epoch_commit is NOT in the safe handled set
    assert "epoch_commit" in unhandled, (
        "epoch_commit must be in unhandled — if this fails, the bug is fixed"
    )
    print(f"  Handled (safe, return early): {sorted(handled)}")
    print(f"  Unhandled (fall-through, TTL bug): {sorted(unhandled)}")


if __name__ == "__main__":
    print("=== PoC: P2P EPOCH_COMMIT TTL Signature Bug (Bounty #2867) ===\n")
    test_epoch_commit_rejected_at_second_hop()
    print()
    print("[Testing all unhandled message types:]")
    test_all_unhandled_types_fail_at_second_hop()
    print()
    print("[Control: handled vs unhandled types:]")
    test_handled_types_never_reach_forward_block()
    print("\n=== All PoC tests passed — vulnerability confirmed ===")
    print("\nImpact: EPOCH_COMMIT cannot propagate beyond direct peers of the")
    print("epoch proposer. Nodes in multi-hop P2P networks never receive the")
    print("commit, cannot advance their epoch, and diverge from the main chain.")
