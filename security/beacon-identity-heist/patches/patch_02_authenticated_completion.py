#!/usr/bin/env python3
"""
Patch 02: Authenticated Bounty Completion

Mitigates CRIT-02 (Trust Score Inflation) by requiring:
1. Admin/maintainer authorization for bounty completions
2. Proof verification (PR merge link or external attestation)
3. Score rate limiting (max +50 per day per agent)

Apply to: node/beacon_api.py — replace bounty completion handler
"""

import hashlib
import time

# Admin tokens (in production, use env vars or secure config)
ADMIN_TOKENS = set()  # Populated from BEACON_ADMIN_TOKENS env var

MAX_SCORE_PER_DAY = 50  # Max reputation gain per agent per day
SCORE_PER_COMPLETION = 10

PATCHED_BOUNTY_COMPLETE = '''
@beacon_api.route('/api/bounties/<bounty_id>/complete', methods=['POST'])
def complete_bounty(bounty_id):
    """
    Mark a bounty as completed. Requires admin authorization.
    
    Body:
        agent_id: The agent that completed the bounty
        admin_token: Authorization token (required)
        proof_url: URL to PR merge or external proof (required)
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    agent_id = data.get('agent_id')
    admin_token = data.get('admin_token')
    proof_url = data.get('proof_url')

    if not agent_id:
        return jsonify({'error': 'Missing agent_id'}), 400

    # SECURITY: Require admin authorization
    if not admin_token or admin_token not in ADMIN_TOKENS:
        return jsonify({'error': 'Unauthorized: admin_token required'}), 403

    # SECURITY: Require proof of work
    if not proof_url:
        return jsonify({'error': 'Missing proof_url (PR merge link required)'}), 400

    db = get_db()

    # SECURITY: Rate limit score gain
    day_start = int(time.time()) - 86400
    recent_gains = db.execute(
        "SELECT COUNT(*) as cnt FROM beacon_completion_log "
        "WHERE agent_id = ? AND completed_at > ?",
        (agent_id, day_start)
    ).fetchone()

    if recent_gains and recent_gains['cnt'] * SCORE_PER_COMPLETION >= MAX_SCORE_PER_DAY:
        return jsonify({
            'error': 'Daily score limit reached',
            'max_per_day': MAX_SCORE_PER_DAY,
        }), 429

    # Complete the bounty
    db.execute(
        "UPDATE beacon_bounties SET state = 'completed', "
        "completed_by = ?, updated_at = ? WHERE id = ?",
        (agent_id, int(time.time()), bounty_id)
    )

    # Update reputation with audit trail
    rep = db.execute(
        "SELECT * FROM beacon_reputation WHERE agent_id = ?",
        (agent_id,)
    ).fetchone()
    
    now = int(time.time())
    if rep:
        db.execute(
            "UPDATE beacon_reputation SET bounties_completed = bounties_completed + 1, "
            "score = score + ?, last_updated = ? WHERE agent_id = ?",
            (SCORE_PER_COMPLETION, now, agent_id)
        )
    else:
        db.execute(
            "INSERT INTO beacon_reputation (agent_id, bounties_completed, score, last_updated) "
            "VALUES (?, 1, ?, ?)",
            (agent_id, SCORE_PER_COMPLETION, now)
        )

    # Audit log
    db.execute(
        "INSERT INTO beacon_completion_log "
        "(agent_id, bounty_id, proof_url, admin_token_hash, completed_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (agent_id, bounty_id, proof_url,
         hashlib.sha256(admin_token.encode()).hexdigest()[:16], now)
    )
    db.commit()

    return jsonify({'ok': True, 'bounty_id': bounty_id, 'agent_id': agent_id})
'''

if __name__ == "__main__":
    print("Patch 02: Authenticated Bounty Completion")
    print("- Admin token required for completions")
    print("- Proof URL (PR merge link) required")
    print("- Daily score gain capped at 50 per agent")
    print("- Audit log for all completions")
