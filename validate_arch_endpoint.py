// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify
import sqlite3
import json
import hashlib
import time
import os

DB_PATH = "rustchain.db"

app = Flask(__name__)

def init_validation_db():
    """Initialize architecture validation tables if they don't exist"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS arch_validations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                target_node TEXT NOT NULL,
                validation_hash TEXT NOT NULL,
                arch_data TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                timestamp INTEGER NOT NULL,
                response_data TEXT
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS validation_consensus (
                validation_hash TEXT PRIMARY KEY,
                total_validators INTEGER DEFAULT 0,
                consensus_score REAL DEFAULT 0.0,
                final_result TEXT,
                created_at INTEGER NOT NULL
            )
        ''')

def calculate_arch_hash(arch_data):
    """Calculate deterministic hash for architecture data"""
    sorted_data = json.dumps(arch_data, sort_keys=True)
    return hashlib.sha256(sorted_data.encode()).hexdigest()

def extract_arch_fingerprint(node_data):
    """Extract architecture fingerprint from node attestation data"""
    fingerprint = {}

    if 'hardware' in node_data:
        hw = node_data['hardware']
        fingerprint['cpu_arch'] = hw.get('cpu_arch', 'unknown')
        fingerprint['cpu_model'] = hw.get('cpu_model', 'unknown')
        fingerprint['platform'] = hw.get('platform', 'unknown')

    if 'system' in node_data:
        sys = node_data['system']
        fingerprint['os_name'] = sys.get('os_name', 'unknown')
        fingerprint['kernel_version'] = sys.get('kernel_version', 'unknown')

    if 'vintage_checks' in node_data:
        vc = node_data['vintage_checks']
        fingerprint['vintage_score'] = vc.get('total_score', 0)
        fingerprint['hardware_age'] = vc.get('estimated_age', 0)

    return fingerprint

@app.route('/api/validate/architecture', methods=['POST'])
def validate_architecture():
    """Main endpoint for architecture cross-validation requests"""
    try:
        data = request.get_json()

        if not data or 'node_id' not in data or 'target_nodes' not in data:
            return jsonify({'error': 'Missing required fields: node_id, target_nodes'}), 400

        node_id = data['node_id']
        target_nodes = data['target_nodes']

        # Get node's current attestation data
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                'SELECT attestation_data FROM nodes WHERE node_id = ? AND status = "active"',
                (node_id,)
            )
            result = cursor.fetchone()

            if not result:
                return jsonify({'error': 'Node not found or inactive'}), 404

            attestation_data = json.loads(result[0])

        # Extract architecture fingerprint
        arch_fingerprint = extract_arch_fingerprint(attestation_data)
        validation_hash = calculate_arch_hash(arch_fingerprint)

        # Create validation entries for each target node
        validation_ids = []
        timestamp = int(time.time())

        with sqlite3.connect(DB_PATH) as conn:
            for target in target_nodes:
                conn.execute('''
                    INSERT INTO arch_validations
                    (node_id, target_node, validation_hash, arch_data, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (node_id, target, validation_hash, json.dumps(arch_fingerprint), timestamp))

                validation_ids.append(conn.lastrowid)

        return jsonify({
            'validation_hash': validation_hash,
            'validation_ids': validation_ids,
            'target_nodes': target_nodes,
            'status': 'validation_requested'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/validate/respond', methods=['POST'])
def validation_response():
    """Endpoint for nodes to respond to validation requests"""
    try:
        data = request.get_json()

        if not data or 'validation_hash' not in data or 'node_id' not in data:
            return jsonify({'error': 'Missing validation_hash or node_id'}), 400

        validation_hash = data['validation_hash']
        responding_node = data['node_id']
        validation_result = data.get('validation_result', {})

        # Update validation with response
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                UPDATE arch_validations
                SET status = 'completed', response_data = ?
                WHERE validation_hash = ? AND target_node = ?
            ''', (json.dumps(validation_result), validation_hash, responding_node))

            # Check if all validations are complete
            cursor = conn.execute(
                'SELECT COUNT(*) FROM arch_validations WHERE validation_hash = ? AND status = "pending"',
                (validation_hash,)
            )
            pending_count = cursor.fetchone()[0]

            if pending_count == 0:
                # Calculate consensus
                cursor = conn.execute('''
                    SELECT response_data FROM arch_validations
                    WHERE validation_hash = ? AND status = "completed"
                ''', (validation_hash,))

                responses = [json.loads(row[0]) for row in cursor.fetchall()]
                consensus_score = calculate_consensus(responses)

                # Store consensus result
                conn.execute('''
                    INSERT OR REPLACE INTO validation_consensus
                    (validation_hash, total_validators, consensus_score, final_result, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (validation_hash, len(responses), consensus_score,
                      json.dumps({'consensus': consensus_score >= 0.7}), int(time.time())))

        return jsonify({
            'status': 'response_recorded',
            'validation_hash': validation_hash,
            'pending_validations': pending_count
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def calculate_consensus(responses):
    """Calculate consensus score from validation responses"""
    if not responses:
        return 0.0

    # Simple majority consensus for now
    valid_count = sum(1 for r in responses if r.get('is_valid', False))
    return valid_count / len(responses)

@app.route('/api/validate/status/<validation_hash>', methods=['GET'])
def validation_status(validation_hash):
    """Get status of a validation request"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Get validation details
            cursor = conn.execute('''
                SELECT node_id, target_node, status, response_data, timestamp
                FROM arch_validations WHERE validation_hash = ?
            ''', (validation_hash,))

            validations = []
            for row in cursor.fetchall():
                validations.append({
                    'node_id': row[0],
                    'target_node': row[1],
                    'status': row[2],
                    'response': json.loads(row[3]) if row[3] else None,
                    'timestamp': row[4]
                })

            # Get consensus if available
            cursor = conn.execute(
                'SELECT total_validators, consensus_score, final_result FROM validation_consensus WHERE validation_hash = ?',
                (validation_hash,)
            )
            consensus_row = cursor.fetchone()

            consensus = None
            if consensus_row:
                consensus = {
                    'total_validators': consensus_row[0],
                    'consensus_score': consensus_row[1],
                    'final_result': json.loads(consensus_row[2])
                }

        return jsonify({
            'validation_hash': validation_hash,
            'validations': validations,
            'consensus': consensus
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/validate/pending/<node_id>', methods=['GET'])
def pending_validations(node_id):
    """Get pending validation requests for a node"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT validation_hash, node_id, arch_data, timestamp
                FROM arch_validations
                WHERE target_node = ? AND status = "pending"
                ORDER BY timestamp DESC
            ''', (node_id,))

            pending = []
            for row in cursor.fetchall():
                pending.append({
                    'validation_hash': row[0],
                    'requesting_node': row[1],
                    'arch_data': json.loads(row[2]),
                    'timestamp': row[3]
                })

        return jsonify({
            'node_id': node_id,
            'pending_validations': pending
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_validation_db()
    app.run(debug=True, host='0.0.0.0', port=5001)
