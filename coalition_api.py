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

def init_db():
    """Initialize coalition database tables - added for test compatibility"""
    init_coalition_db()

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
                status TEXT DEFAULT 'active',
                votes_for INTEGER DEFAULT 0,
                votes_against INTEGER DEFAULT 0,
                FOREIGN KEY (coalition_id) REFERENCES coalitions (id)
            )
        ''')
        conn.commit()

def get_coalition_members(coalition_id: int) -> List[Dict]:
    """Get all members of a coalition"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM coalition_members WHERE coalition_id = ? AND status = 'active'",
            (coalition_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

def get_voting_power(miner_id: str, coalition_id: int = None) -> float:
    """Calculate voting power for a miner"""
    # Simple voting power calculation - can be enhanced
    base_power = 1.0

    # Add antiquity multiplier
    antiquity_mult = calculate_antiquity_multiplier(miner_id)

    return base_power * antiquity_mult

def calculate_antiquity_multiplier(miner_id: str) -> float:
    """Calculate antiquity multiplier based on miner history"""
    # Simple antiquity calculation - days since first seen
    # This would need actual miner data in production
    base_multiplier = 1.0

    # Placeholder calculation
    if miner_id == "sophia-elya":
        return 2.0  # Flamebound founder gets higher multiplier

    return base_multiplier

@app.route('/api/coalitions', methods=['GET'])
def list_coalitions():
    """List all active coalitions"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM coalitions WHERE status = 'active' ORDER BY created_at DESC"
        )
        coalitions = [dict(row) for row in cursor.fetchall()]

    return jsonify({
        "success": True,
        "coalitions": coalitions
    })

@app.route('/api/coalitions', methods=['POST'])
def create_coalition():
    """Create a new coalition"""
    data = request.get_json()

    if not data or not data.get('name') or not data.get('founder'):
        return jsonify({"error": "Name and founder required"}), 400

    try:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO coalitions (name, description, founder, created_at) VALUES (?, ?, ?, ?)",
                (data['name'], data.get('description', ''), data['founder'], int(time.time()))
            )
            coalition_id = cursor.lastrowid

            # Add founder as first member
            conn.execute(
                "INSERT INTO coalition_members (coalition_id, miner_id, joined_at, role) VALUES (?, ?, ?, 'leader')",
                (coalition_id, data['founder'], int(time.time()))
            )

            conn.commit()

        return jsonify({
            "success": True,
            "coalition_id": coalition_id,
            "message": "Coalition created successfully"
        })

    except sqlite3.IntegrityError:
        return jsonify({"error": "Coalition name already exists"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/coalitions/<int:coalition_id>/members', methods=['GET'])
def get_members(coalition_id):
    """Get coalition members"""
    members = get_coalition_members(coalition_id)

    return jsonify({
        "success": True,
        "members": members
    })

@app.route('/api/coalitions/<int:coalition_id>/join', methods=['POST'])
def join_coalition(coalition_id):
    """Join a coalition"""
    data = request.get_json()
    miner_id = data.get('miner_id')

    if not miner_id:
        return jsonify({"error": "miner_id required"}), 400

    try:
        with get_db() as conn:
            # Check if coalition exists
            cursor = conn.execute("SELECT id FROM coalitions WHERE id = ? AND status = 'active'", (coalition_id,))
            if not cursor.fetchone():
                return jsonify({"error": "Coalition not found or inactive"}), 404

            # Add member
            conn.execute(
                "INSERT INTO coalition_members (coalition_id, miner_id, joined_at) VALUES (?, ?, ?)",
                (coalition_id, miner_id, int(time.time()))
            )

            # Update member count
            conn.execute(
                "UPDATE coalitions SET member_count = member_count + 1 WHERE id = ?",
                (coalition_id,)
            )

            conn.commit()

        return jsonify({
            "success": True,
            "message": "Successfully joined coalition"
        })

    except sqlite3.IntegrityError:
        return jsonify({"error": "Already a member of this coalition"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_coalition_db()
    app.run(debug=True)
