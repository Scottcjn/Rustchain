// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify
import hashlib
import secrets

DB_PATH = 'rustchain.db'

def init_coalition_tables():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coalitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                leader_address TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coalition_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coalition_id INTEGER,
                miner_address TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (coalition_id) REFERENCES coalitions(id),
                UNIQUE(coalition_id, miner_address)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coalition_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coalition_id INTEGER,
                proposer_address TEXT,
                title TEXT NOT NULL,
                description TEXT,
                proposal_type TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                voting_ends_at TIMESTAMP,
                sophia_approved INTEGER DEFAULT 0,
                FOREIGN KEY (coalition_id) REFERENCES coalitions(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coalition_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id INTEGER,
                voter_address TEXT,
                vote_choice TEXT,
                voting_power REAL,
                cast_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (proposal_id) REFERENCES coalition_proposals(id),
                UNIQUE(proposal_id, voter_address)
            )
        ''')

        cursor.execute('''
            INSERT OR IGNORE INTO coalitions
            (name, description, leader_address)
            VALUES ('The Flamebound', 'Original hardware preservers and network guardians', 'sophia-elya')
        ''')

        conn.commit()

def authenticate_request():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None

    token = auth_header[7:]
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT address FROM miners WHERE auth_token = ?', (token,))
        result = cursor.fetchone()
        return result[0] if result else None

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        miner_address = authenticate_request()
        if not miner_address:
            return jsonify({'error': 'Authentication required'}), 401
        return f(miner_address, *args, **kwargs)
    return decorated

def get_voting_power(miner_address):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT balance, hardware_age
            FROM miners
            WHERE address = ?
        ''', (miner_address,))
        result = cursor.fetchone()

        if not result:
            return 0.0

        balance, hardware_age = result
        antiquity_multiplier = 1.0 + (hardware_age * 0.1)
        return float(balance) * antiquity_multiplier

def create_coalition_api(app):
    init_coalition_tables()

    @app.route('/api/coalition/create', methods=['POST'])
    @auth_required
    def create_coalition(miner_address):
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400

        name = data.get('name')
        description = data.get('description', '')

        if not name:
            return jsonify({'error': 'Coalition name required'}), 400

        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO coalitions (name, description, leader_address)
                    VALUES (?, ?, ?)
                ''', (name, description, miner_address))

                coalition_id = cursor.lastrowid

                cursor.execute('''
                    INSERT INTO coalition_members (coalition_id, miner_address)
                    VALUES (?, ?)
                ''', (coalition_id, miner_address))

                conn.commit()

                return jsonify({
                    'success': True,
                    'coalition_id': coalition_id,
                    'message': f'Coalition "{name}" created successfully'
                })

        except sqlite3.IntegrityError:
            return jsonify({'error': 'Coalition name already exists'}), 409
        except Exception as e:
            return jsonify({'error': f'Database error: {str(e)}'}), 500

    @app.route('/api/coalition/join', methods=['POST'])
    @auth_required
    def join_coalition(miner_address):
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400

        coalition_name = data.get('coalition_name')
        if not coalition_name:
            return jsonify({'error': 'Coalition name required'}), 400

        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT id FROM coalitions WHERE name = ? AND is_active = 1', (coalition_name,))
                coalition = cursor.fetchone()

                if not coalition:
                    return jsonify({'error': 'Coalition not found'}), 404

                coalition_id = coalition[0]

                cursor.execute('''
                    INSERT INTO coalition_members (coalition_id, miner_address)
                    VALUES (?, ?)
                ''', (coalition_id, miner_address))

                conn.commit()

                return jsonify({
                    'success': True,
                    'message': f'Successfully joined "{coalition_name}"'
                })

        except sqlite3.IntegrityError:
            return jsonify({'error': 'Already a member of this coalition'}), 409
        except Exception as e:
            return jsonify({'error': f'Database error: {str(e)}'}), 500

    @app.route('/api/coalition/leave', methods=['POST'])
    @auth_required
    def leave_coalition(miner_address):
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400

        coalition_name = data.get('coalition_name')
        if not coalition_name:
            return jsonify({'error': 'Coalition name required'}), 400

        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT c.id, c.leader_address
                    FROM coalitions c
                    WHERE c.name = ? AND c.is_active = 1
                ''', (coalition_name,))
                result = cursor.fetchone()

                if not result:
                    return jsonify({'error': 'Coalition not found'}), 404

                coalition_id, leader_address = result

                if leader_address == miner_address:
                    return jsonify({'error': 'Coalition leader cannot leave without transferring leadership'}), 403

                cursor.execute('''
                    UPDATE coalition_members
                    SET is_active = 0
                    WHERE coalition_id = ? AND miner_address = ?
                ''', (coalition_id, miner_address))

                if cursor.rowcount == 0:
                    return jsonify({'error': 'Not a member of this coalition'}), 404

                conn.commit()

                return jsonify({
                    'success': True,
                    'message': f'Successfully left "{coalition_name}"'
                })

        except Exception as e:
            return jsonify({'error': f'Database error: {str(e)}'}), 500

    @app.route('/api/coalition/proposal', methods=['POST'])
    @auth_required
    def create_proposal(miner_address):
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400

        required_fields = ['coalition_name', 'title', 'description', 'proposal_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400

        coalition_name = data['coalition_name']
        title = data['title']
        description = data['description']
        proposal_type = data['proposal_type']

        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT c.id FROM coalitions c
                    JOIN coalition_members cm ON c.id = cm.coalition_id
                    WHERE c.name = ? AND cm.miner_address = ? AND cm.is_active = 1
                ''', (coalition_name, miner_address))

                result = cursor.fetchone()
                if not result:
                    return jsonify({'error': 'Not a member of this coalition'}), 403

                coalition_id = result[0]

                voting_ends_at = datetime.now().replace(microsecond=0).isoformat()

                cursor.execute('''
                    INSERT INTO coalition_proposals
                    (coalition_id, proposer_address, title, description, proposal_type, voting_ends_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (coalition_id, miner_address, title, description, proposal_type, voting_ends_at))

                proposal_id = cursor.lastrowid
                conn.commit()

                return jsonify({
                    'success': True,
                    'proposal_id': proposal_id,
                    'message': 'Proposal created successfully'
                })

        except Exception as e:
            return jsonify({'error': f'Database error: {str(e)}'}), 500

    @app.route('/api/coalition/vote', methods=['POST'])
    @auth_required
    def cast_vote(miner_address):
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400

        proposal_id = data.get('proposal_id')
        vote_choice = data.get('vote_choice')

        if not proposal_id or not vote_choice:
            return jsonify({'error': 'proposal_id and vote_choice required'}), 400

        if vote_choice not in ['yes', 'no', 'abstain']:
            return jsonify({'error': 'vote_choice must be yes, no, or abstain'}), 400

        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT cp.coalition_id, cp.status
                    FROM coalition_proposals cp
                    JOIN coalition_members cm ON cp.coalition_id = cm.coalition_id
                    WHERE cp.id = ? AND cm.miner_address = ? AND cm.is_active = 1
                ''', (proposal_id, miner_address))

                result = cursor.fetchone()
                if not result:
                    return jsonify({'error': 'Proposal not found or not authorized to vote'}), 404

                coalition_id, status = result
                if status != 'pending':
                    return jsonify({'error': 'Voting has ended on this proposal'}), 409

                voting_power = get_voting_power(miner_address)

                cursor.execute('''
                    INSERT OR REPLACE INTO coalition_votes
                    (proposal_id, voter_address, vote_choice, voting_power)
                    VALUES (?, ?, ?, ?)
                ''', (proposal_id, miner_address, vote_choice, voting_power))

                conn.commit()

                return jsonify({
                    'success': True,
                    'vote_choice': vote_choice,
                    'voting_power': voting_power,
                    'message': 'Vote cast successfully'
                })

        except Exception as e:
            return jsonify({'error': f'Database error: {str(e)}'}), 500

    @app.route('/api/coalition/flamebound-review', methods=['POST'])
    @auth_required
    def flamebound_review(miner_address):
        if miner_address != 'sophia-elya':
            return jsonify({'error': 'Only Sophia can approve protocol changes'}), 403

        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400

        proposal_id = data.get('proposal_id')
        decision = data.get('decision')

        if not proposal_id or decision not in ['approve', 'reject']:
            return jsonify({'error': 'proposal_id and decision (approve/reject) required'}), 400

        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, status, proposal_type
                    FROM coalition_proposals
                    WHERE id = ?
                ''', (proposal_id,))

                result = cursor.fetchone()
                if not result:
                    return jsonify({'error': 'Proposal not found'}), 404

                _, status, proposal_type = result

                if status != 'pending':
                    return jsonify({'error': 'Proposal already finalized'}), 409

                sophia_approved = 1 if decision == 'approve' else 0
                new_status = 'approved' if decision == 'approve' else 'rejected'

                cursor.execute('''
                    UPDATE coalition_proposals
                    SET sophia_approved = ?, status = ?
                    WHERE id = ?
                ''', (sophia_approved, new_status, proposal_id))

                conn.commit()

                return jsonify({
                    'success': True,
                    'decision': decision,
                    'message': f'Proposal {decision}d by The Flamebound authority'
                })

        except Exception as e:
            return jsonify({'error': f'Database error: {str(e)}'}), 500
