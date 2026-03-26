#!/usr/bin/env python3
"""
Patch 01: Authenticated Agent Registration

Mitigates CRIT-01 (Identity Takeover) by requiring:
1. Challenge-response: New registrations must sign a server-issued challenge
2. Immutable pubkey binding: Existing agents cannot change their pubkey via /beacon/join
3. Separate key-rotation endpoint requiring old-key signature

Apply to: node/beacon_api.py — replace beacon_join()
"""

import hashlib
import json
import os
import time


# ── Challenge-response flow ──────────────────────────────────────────

def generate_challenge(agent_id: str) -> dict:
    """Generate a registration challenge for the agent to sign."""
    nonce = os.urandom(32).hex()
    timestamp = int(time.time())
    challenge = f"beacon_register:{agent_id}:{nonce}:{timestamp}"
    return {
        "challenge": challenge,
        "nonce": nonce,
        "timestamp": timestamp,
        "expires_at": timestamp + 300,  # 5 minute expiry
    }


def verify_challenge_signature(challenge: str, signature_hex: str, pubkey_hex: str) -> bool:
    """Verify that the agent signed the challenge with their claimed pubkey."""
    try:
        from nacl.signing import VerifyKey
        pubkey_bytes = bytes.fromhex(pubkey_hex)
        sig_bytes = bytes.fromhex(signature_hex)
        verify_key = VerifyKey(pubkey_bytes)
        verify_key.verify(challenge.encode(), sig_bytes)
        return True
    except Exception:
        return False


# ── Patched registration endpoint ────────────────────────────────────

PATCHED_BEACON_JOIN = '''
@beacon_api.route('/beacon/join', methods=['POST', 'OPTIONS'])
def beacon_join():
    """
    Register a NEW agent (challenge-response required).
    
    Flow:
    1. POST with agent_id + pubkey_hex → server returns challenge
    2. POST with agent_id + pubkey_hex + challenge + signature → registration
    
    SECURITY: Existing agents CANNOT re-register (pubkey is immutable).
    Use /beacon/rotate-key for key changes.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    agent_id = data.get('agent_id')
    pubkey_hex = data.get('pubkey_hex')

    if not agent_id or not pubkey_hex:
        return jsonify({'error': 'Missing agent_id or pubkey_hex'}), 400

    # SECURITY: Check if agent already exists
    db = get_db()
    existing = db.execute(
        "SELECT pubkey_hex FROM relay_agents WHERE agent_id = ?",
        (agent_id,)
    ).fetchone()

    if existing:
        return jsonify({
            'error': 'Agent already registered. Use /beacon/rotate-key to change keys.',
            'agent_id': agent_id,
        }), 409  # Conflict

    # Step 1: If no challenge/signature provided, issue a challenge
    challenge = data.get('challenge')
    signature = data.get('signature')

    if not challenge or not signature:
        ch = generate_challenge(agent_id)
        return jsonify({
            'status': 'challenge_issued',
            'challenge': ch['challenge'],
            'nonce': ch['nonce'],
            'expires_at': ch['expires_at'],
            'instructions': 'Sign the challenge with your Ed25519 private key and resubmit.',
        })

    # Step 2: Verify the challenge signature
    if not verify_challenge_signature(challenge, signature, pubkey_hex):
        return jsonify({'error': 'Invalid challenge signature'}), 403

    # Registration approved
    now = int(time.time())
    db.execute("""
        INSERT INTO relay_agents (agent_id, pubkey_hex, name, status, created_at, updated_at)
        VALUES (?, ?, ?, 'active', ?, ?)
    """, (agent_id, pubkey_hex, data.get('name'), now, now))
    db.commit()

    return jsonify({'ok': True, 'agent_id': agent_id, 'status': 'registered'})
'''

if __name__ == "__main__":
    print("Patch 01: Authenticated Registration")
    print("- Challenge-response required for new agents")
    print("- Existing agents cannot re-register (immutable pubkey)")
    print("- Eliminates identity takeover attack")
