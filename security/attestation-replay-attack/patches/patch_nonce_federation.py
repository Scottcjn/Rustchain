#!/usr/bin/env python3
"""
Patch: Challenge Nonce Federation

Mitigates cross-node nonce isolation by:
1. Embedding node_id in challenge nonces
2. Broadcasting used nonce hashes to peers
3. Rejecting nonces from other nodes

Apply to: node/rustchain_v2_integrated_v2.2.1_rip200.py
"""

import hashlib
import json
import os
import secrets
import time
from typing import Tuple, Optional

THIS_NODE_ID = os.environ.get("RUSTCHAIN_NODE_ID", "node-unknown")
NONCE_PREFIX = f"n{hashlib.sha256(THIS_NODE_ID.encode()).hexdigest()[:8]}"


def generate_federated_nonce(node_id: str = None) -> Tuple[str, int]:
    """
    Generate a challenge nonce that encodes the issuing node.
    
    Format: {node_prefix}_{random_hex}_{timestamp_hex}
    """
    node_id = node_id or THIS_NODE_ID
    prefix = hashlib.sha256(node_id.encode()).hexdigest()[:8]
    random_part = secrets.token_hex(24)
    ts_hex = hex(int(time.time()))[2:]
    nonce = f"n{prefix}_{random_part}_{ts_hex}"
    expires = int(time.time()) + 300
    return nonce, expires


def validate_nonce_origin(nonce: str, expected_node_id: str = None) -> Tuple[bool, str]:
    """
    Check that a nonce was issued by this node.
    
    Prevents cross-node nonce reuse: a nonce from Node 1
    cannot be used on Node 2.
    """
    expected_node_id = expected_node_id or THIS_NODE_ID
    expected_prefix = f"n{hashlib.sha256(expected_node_id.encode()).hexdigest()[:8]}"

    if not nonce:
        return False, "empty_nonce"

    # Federated nonces have format: n{prefix}_{random}_{ts}
    if nonce.startswith("n") and "_" in nonce:
        actual_prefix = nonce.split("_")[0]
        if actual_prefix != expected_prefix:
            return False, "wrong_node_nonce"
        return True, "valid_federated"

    # Legacy nonces (64-char hex) — allow during transition
    if len(nonce) == 64 and all(c in "0123456789abcdef" for c in nonce):
        return True, "legacy_nonce"

    return False, "invalid_format"


def hash_used_nonce(nonce: str) -> str:
    """Hash a nonce for gossip (don't leak actual nonce values)."""
    return hashlib.sha256(nonce.encode()).hexdigest()[:32]


def broadcast_used_nonce(nonce_hash: str, node_id: str, peers: list):
    """Broadcast used nonce hash to peers for dedup."""
    import threading

    payload = json.dumps({
        "nonce_hash": nonce_hash,
        "node_id": node_id,
        "timestamp": int(time.time()),
    }).encode()

    def _send(peer_url):
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{peer_url}/internal/nonce-used",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    for peer in peers:
        if node_id not in peer:
            threading.Thread(target=_send, args=(peer,), daemon=True).start()


# ── Patched challenge endpoint ────────────────────────────────────

PATCHED_CHALLENGE = '''
@app.route('/attest/challenge', methods=['POST'])
def get_challenge():
    """Issue challenge with node-bound nonce."""
    nonce, expires = generate_federated_nonce(THIS_NODE_ID)
    
    with sqlite3.connect(DB_PATH) as c:
        c.execute("INSERT INTO nonces (nonce, expires_at) VALUES (?, ?)", 
                  (nonce, expires))
    
    return jsonify({
        "nonce": nonce,
        "expires_at": expires,
        "server_time": int(time.time()),
        "node_id": THIS_NODE_ID,
    })
'''

PATCHED_VALIDATE = '''
# Add at start of nonce validation in _submit_attestation_impl():

# SECURITY: Verify nonce was issued by THIS node
nonce_ok, nonce_origin = validate_nonce_origin(nonce, THIS_NODE_ID)
if not nonce_ok:
    return jsonify({
        "ok": False,
        "error": "wrong_node_nonce",
        "message": "This challenge nonce was issued by a different node",
        "code": "WRONG_NODE_NONCE"
    }), 403
'''


if __name__ == "__main__":
    print("Patch: Challenge Nonce Federation")
    print(f"  Node ID: {THIS_NODE_ID}")
    print(f"  Nonce prefix: {NONCE_PREFIX}")

    nonce, expires = generate_federated_nonce()
    print(f"  Sample nonce: {nonce}")
    print(f"  Expires: {expires}")

    ok, reason = validate_nonce_origin(nonce)
    print(f"  Validates: {ok} ({reason})")

    # Cross-node nonce should fail
    fake_nonce, _ = generate_federated_nonce("other-node")
    ok2, reason2 = validate_nonce_origin(fake_nonce)
    print(f"  Cross-node nonce: {ok2} ({reason2})")
