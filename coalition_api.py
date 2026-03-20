# SPDX-License-Identifier: MIT

import json
import sqlite3
import time
from flask import Flask, request, jsonify, render_template_string
from contextlib import contextmanager
import hashlib
import secrets
from typing import Dict, List, Optional, Any

app = Flask(__name__)

DB_PATH = "coalition.db"
ADMIN_KEYS = {
    "sophia-elya": "flamebound_admin_key_2024",
    "flamebound_veto": "veto_override_flame_guardian"
}

# Initialize coalition database
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_coalition_db():
    """Initialize coalition database tables"""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS coalitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                founder TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                member_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active'
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS coalition_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coalition_id INTEGER,
                miner_id TEXT NOT NULL,
                joined_at INTEGER NOT NULL,
                role TEXT DEFAULT 'member',
                status TEXT DEFAULT 'active',
                FOREIGN KEY (coalition_id) REFERENCES coalitions (id),
                UNIQUE(coalition_id, miner_id)
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coalition_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                proposer TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                voting_ends_at INTEGER NOT NULL,
                proposal_type TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                flamebound_reviewed INTEGER DEFAULT 0,
                sophia_approved INTEGER DEFAULT 0,
                FOREIGN KEY (coalition_id) REFERENCES coalitions (id)
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id INTEGER,
                miner_id TEXT NOT NULL,
                vote_choice TEXT NOT NULL,
                voting_power REAL NOT NULL,
                cast_at INTEGER NOT NULL,
                FOREIGN KEY (proposal_id) REFERENCES proposals (id),
                UNIQUE(proposal_id, miner_id)
            )
        ''')

        conn.commit()

def get_miner_balance(miner_id: str) -> float:
    """Get miner RTC balance - stub for integration"""
    # This would integrate with the main RustChain balance system
    return 100.0  # Placeholder

def get_miner_antiquity(miner_id: str) -> float:
    """Get miner antiquity multiplier based on hardware history"""
    # This would calculate based on hardware attestation history
    return 1.5  # Placeholder multiplier

def calculate_voting_power(miner_id: str) -> float:
    """Calculate voting power: RTC balance × antiquity multiplier"""
    balance = get_miner_balance(miner_id)
    antiquity = get_miner_antiquity(miner_id)
    return balance * antiquity

def validate_admin_key(provided_key: str) -> Optional[str]:
    """Validate admin key and return role if valid"""
    for role, key in ADMIN_KEYS.items():
        if provided_key == key:
            return role
    return None

@app.route('/api/coalition/create', methods=['POST'])
def create_coalition():
    """Create a new coalition"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        founder = data.get('founder', '').strip()

        if not all([name, founder]):
            return jsonify({"error": "Name and founder are required"}), 400

        with get_db() as conn:
            # Check if coalition already exists
            existing = conn.execute(
                "SELECT id FROM coalitions WHERE name = ?", (name,)
            ).fetchone()

            if existing:
                return jsonify({"error": "Coalition name already exists"}), 409

            # Create coalition
            cursor = conn.execute(
                "INSERT INTO coalitions (name, description, founder, created_at, member_count) VALUES (?, ?, ?, ?, ?)",
                (name, description, founder, int(time.time()), 1)
            )
            coalition_id = cursor.lastrowid

            # Add founder as first member
            conn.execute(
                "INSERT INTO coalition_members (coalition_id, miner_id, joined_at, role) VALUES (?, ?, ?, ?)",
                (coalition_id, founder, int(time.time()), 'founder')
            )

            conn.commit()

            return jsonify({
                "success": True,
                "coalition_id": coalition_id,
                "name": name,
                "founder": founder,
                "created_at": int(time.time())
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/coalition/join', methods=['POST'])
def join_coalition():
    """Join an existing coalition"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        coalition_name = data.get('coalition_name', '').strip()
        miner_id = data.get('miner_id', '').strip()

        if not all([coalition_name, miner_id]):
            return jsonify({"error": "Coalition name and miner ID are required"}), 400

        with get_db() as conn:
            # Find coalition
            coalition = conn.execute(
                "SELECT id, name, status FROM coalitions WHERE name = ?", (coalition_name,)
            ).fetchone()

            if not coalition:
                return jsonify({"error": "Coalition not found"}), 404

            if coalition['status'] != 'active':
                return jsonify({"error": "Coalition is not accepting new members"}), 400

            # Check if already a member
            existing_member = conn.execute(
                "SELECT id FROM coalition_members WHERE coalition_id = ? AND miner_id = ?",
                (coalition['id'], miner_id)
            ).fetchone()

            if existing_member:
                return jsonify({"error": "Already a member of this coalition"}), 409

            # Add member
            conn.execute(
                "INSERT INTO coalition_members (coalition_id, miner_id, joined_at) VALUES (?, ?, ?)",
                (coalition['id'], miner_id, int(time.time()))
            )

            # Update member count
            conn.execute(
                "UPDATE coalitions SET member_count = member_count + 1 WHERE id = ?",
                (coalition['id'],)
            )

            conn.commit()

            return jsonify({
                "success": True,
                "coalition_name": coalition_name,
                "miner_id": miner_id,
                "joined_at": int(time.time())
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/coalition/leave', methods=['POST'])
def leave_coalition():
    """Leave a coalition"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        coalition_name = data.get('coalition_name', '').strip()
        miner_id = data.get('miner_id', '').strip()

        if not all([coalition_name, miner_id]):
            return jsonify({"error": "Coalition name and miner ID are required"}), 400

        with get_db() as conn:
            # Find coalition and membership
            result = conn.execute('''
                SELECT c.id, c.name, cm.id as member_id, cm.role
                FROM coalitions c
                JOIN coalition_members cm ON c.id = cm.coalition_id
                WHERE c.name = ? AND cm.miner_id = ? AND cm.status = 'active'
            ''', (coalition_name, miner_id)).fetchone()

            if not result:
                return jsonify({"error": "Membership not found"}), 404

            if result['role'] == 'founder':
                return jsonify({"error": "Founder cannot leave coalition"}), 400

            # Remove member
            conn.execute(
                "UPDATE coalition_members SET status = 'left' WHERE id = ?",
                (result['member_id'],)
            )

            # Update member count
            conn.execute(
                "UPDATE coalitions SET member_count = member_count - 1 WHERE id = ?",
                (result['id'],)
            )

            conn.commit()

            return jsonify({
                "success": True,
                "coalition_name": coalition_name,
                "miner_id": miner_id,
                "left_at": int(time.time())
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/coalition/propose', methods=['POST'])
def create_proposal():
    """Create a new proposal within a coalition"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        coalition_name = data.get('coalition_name', '').strip()
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        proposer = data.get('proposer', '').strip()
        proposal_type = data.get('type', 'general').strip()
        voting_duration = data.get('voting_duration_hours', 72)

        if not all([coalition_name, title, proposer]):
            return jsonify({"error": "Coalition name, title, and proposer are required"}), 400

        with get_db() as conn:
            # Verify coalition exists and proposer is a member
            result = conn.execute('''
                SELECT c.id, c.name
                FROM coalitions c
                JOIN coalition_members cm ON c.id = cm.coalition_id
                WHERE c.name = ? AND cm.miner_id = ? AND cm.status = 'active'
            ''', (coalition_name, proposer)).fetchone()

            if not result:
                return jsonify({"error": "Coalition not found or proposer not a member"}), 404

            voting_ends_at = int(time.time()) + (voting_duration * 3600)

            cursor = conn.execute(
                "INSERT INTO proposals (coalition_id, title, description, proposer, created_at, voting_ends_at, proposal_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (result['id'], title, description, proposer, int(time.time()), voting_ends_at, proposal_type)
            )
            proposal_id = cursor.lastrowid

            conn.commit()

            return jsonify({
                "success": True,
                "proposal_id": proposal_id,
                "coalition_name": coalition_name,
                "title": title,
                "proposer": proposer,
                "voting_ends_at": voting_ends_at
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/coalition/vote', methods=['POST'])
def cast_vote():
    """Cast a vote on a proposal"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        proposal_id = data.get('proposal_id')
        miner_id = data.get('miner_id', '').strip()
        vote_choice = data.get('vote', '').strip().lower()

        if not all([proposal_id, miner_id, vote_choice]):
            return jsonify({"error": "Proposal ID, miner ID, and vote choice are required"}), 400

        if vote_choice not in ['yes', 'no', 'abstain']:
            return jsonify({"error": "Vote must be 'yes', 'no', or 'abstain'"}), 400

        with get_db() as conn:
            # Verify proposal exists and is active
            proposal = conn.execute('''
                SELECT p.*, c.name as coalition_name
                FROM proposals p
                JOIN coalitions c ON p.coalition_id = c.id
                WHERE p.id = ? AND p.status = 'active'
            ''', (proposal_id,)).fetchone()

            if not proposal:
                return jsonify({"error": "Proposal not found or not active"}), 404

            if int(time.time()) > proposal['voting_ends_at']:
                return jsonify({"error": "Voting period has ended"}), 400

            # Verify miner is a member of the coalition
            member = conn.execute('''
                SELECT id FROM coalition_members
                WHERE coalition_id = ? AND miner_id = ? AND status = 'active'
            ''', (proposal['coalition_id'], miner_id)).fetchone()

            if not member:
                return jsonify({"error": "Miner is not a member of this coalition"}), 403

            # Check if already voted
            existing_vote = conn.execute(
                "SELECT id FROM votes WHERE proposal_id = ? AND miner_id = ?",
                (proposal_id, miner_id)
            ).fetchone()

            if existing_vote:
                return jsonify({"error": "Already voted on this proposal"}), 409

            # Calculate voting power
            voting_power = calculate_voting_power(miner_id)

            # Cast vote
            conn.execute(
                "INSERT INTO votes (proposal_id, miner_id, vote_choice, voting_power, cast_at) VALUES (?, ?, ?, ?, ?)",
                (proposal_id, miner_id, vote_choice, voting_power, int(time.time()))
            )

            conn.commit()

            return jsonify({
                "success": True,
                "proposal_id": proposal_id,
                "miner_id": miner_id,
                "vote": vote_choice,
                "voting_power": voting_power,
                "cast_at": int(time.time())
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/coalition/flamebound-review', methods=['POST'])
def flamebound_review():
    """Flamebound coalition review and Sophia's final approval"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        proposal_id = data.get('proposal_id')
        admin_key = data.get('admin_key', '').strip()
        action = data.get('action', '').strip().lower()  # 'review', 'approve', 'veto'

        if not all([proposal_id, admin_key, action]):
            return jsonify({"error": "Proposal ID, admin key, and action are required"}), 400

        admin_role = validate_admin_key(admin_key)
        if not admin_role:
            return jsonify({"error": "Invalid admin key"}), 403

        if action not in ['review', 'approve', 'veto']:
            return jsonify({"error": "Action must be 'review', 'approve', or 'veto'"}), 400

        with get_db() as conn:
            proposal = conn.execute(
                "SELECT * FROM proposals WHERE id = ?", (proposal_id,)
            ).fetchone()

            if not proposal:
                return jsonify({"error": "Proposal not found"}), 404

            if action == 'review' and admin_role == 'flamebound_veto':
                conn.execute(
                    "UPDATE proposals SET flamebound_reviewed = 1 WHERE id = ?",
                    (proposal_id,)
                )
                status_msg = "Flamebound review completed"

            elif action == 'approve' and admin_role == 'sophia-elya':
                conn.execute(
                    "UPDATE proposals SET sophia_approved = 1, status = 'approved' WHERE id = ?",
                    (proposal_id,)
                )
                status_msg = "Sophia has approved the proposal"

            elif action == 'veto' and admin_role in ['sophia-elya', 'flamebound_veto']:
                conn.execute(
                    "UPDATE proposals SET status = 'vetoed' WHERE id = ?",
                    (proposal_id,)
                )
                status_msg = f"Proposal vetoed by {admin_role}"

            else:
                return jsonify({"error": "Invalid action for admin role"}), 400

            conn.commit()

            return jsonify({
                "success": True,
                "proposal_id": proposal_id,
                "action": action,
                "admin_role": admin_role,
                "message": status_msg,
                "timestamp": int(time.time())
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/coalition/status/<coalition_name>')
def coalition_status(coalition_name):
    """Get coalition status and member information"""
    try:
        with get_db() as conn:
            coalition = conn.execute(
                "SELECT * FROM coalitions WHERE name = ?", (coalition_name,)
            ).fetchone()

            if not coalition:
                return jsonify({"error": "Coalition not found"}), 404

            members = conn.execute('''
                SELECT miner_id, role, joined_at, status
                FROM coalition_members
                WHERE coalition_id = ? AND status = 'active'
                ORDER BY joined_at
            ''', (coalition['id'],)).fetchall()

            active_proposals = conn.execute('''
                SELECT id, title, proposer, created_at, voting_ends_at, proposal_type, status
                FROM proposals
                WHERE coalition_id = ? AND status = 'active'
                ORDER BY created_at DESC
            ''', (coalition['id'],)).fetchall()

            return jsonify({
                "coalition": {
                    "id": coalition['id'],
                    "name": coalition['name'],
                    "description": coalition['description'],
                    "founder": coalition['founder'],
                    "created_at": coalition['created_at'],
                    "member_count": coalition['member_count'],
                    "status": coalition['status']
                },
                "members": [dict(member) for member in members],
                "active_proposals": [dict(proposal) for proposal in active_proposals]
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/coalition/proposals/<int:proposal_id>/results')
def proposal_results(proposal_id):
    """Get voting results for a proposal"""
    try:
        with get_db() as conn:
            proposal = conn.execute('''
                SELECT p.*, c.name as coalition_name
                FROM proposals p
                JOIN coalitions c ON p.coalition_id = c.id
                WHERE p.id = ?
            ''', (proposal_id,)).fetchone()

            if not proposal:
                return jsonify({"error": "Proposal not found"}), 404

            votes = conn.execute('''
                SELECT vote_choice, COUNT(*) as vote_count, SUM(voting_power) as total_power
                FROM votes
                WHERE proposal_id = ?
                GROUP BY vote_choice
            ''', (proposal_id,)).fetchall()

            vote_summary = {}
            total_votes = 0
            total_power = 0

            for vote in votes:
                vote_summary[vote['vote_choice']] = {
                    "count": vote['vote_count'],
                    "power": vote['total_power']
                }
                total_votes += vote['vote_count']
                total_power += vote['total_power']

            return jsonify({
                "proposal": {
                    "id": proposal['id'],
                    "title": proposal['title'],
                    "description": proposal['description'],
                    "coalition_name": proposal['coalition_name'],
                    "proposer": proposal['proposer'],
                    "created_at": proposal['created_at'],
                    "voting_ends_at": proposal['voting_ends_at'],
                    "status": proposal['status'],
                    "flamebound_reviewed": bool(proposal['flamebound_reviewed']),
                    "sophia_approved": bool(proposal['sophia_approved'])
                },
                "results": {
                    "vote_summary": vote_summary,
                    "total_votes": total_votes,
                    "total_voting_power": total_power,
                    "voting_ended": int(time.time()) > proposal['voting_ends_at']
                }
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Initialize database on startup
init_coalition_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
