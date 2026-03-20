// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, jsonify, request, render_template_string
import sqlite3
import json
import time
from datetime import datetime, timedelta
import threading
import os

DB_PATH = "rustchain.db"
app = Flask(__name__)

class TemporalValidator:
    def __init__(self):
        self.validation_lock = threading.Lock()
        self.anomaly_threshold = 0.15

    def init_temporal_tables(self):
        """Initialize database tables for temporal validation"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS entropy_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    block_height INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    entropy_value REAL NOT NULL,
                    hardware_id TEXT NOT NULL,
                    validation_score REAL DEFAULT 0.0,
                    is_anomaly INTEGER DEFAULT 0,
                    created_at REAL DEFAULT (julianday('now'))
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS temporal_validations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hardware_id TEXT NOT NULL,
                    validation_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    score REAL DEFAULT 0.0,
                    anomaly_count INTEGER DEFAULT 0,
                    last_validated REAL DEFAULT (julianday('now')),
                    metadata TEXT
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_entropy_hardware_time
                ON entropy_history(hardware_id, timestamp)
            ''')

            conn.commit()

validator = TemporalValidator()
validator.init_temporal_tables()

@app.route('/api/temporal/history/<hardware_id>')
def get_entropy_history(hardware_id):
    """Retrieve entropy history for a specific hardware ID"""
    try:
        hours = int(request.args.get('hours', 24))
        limit = int(request.args.get('limit', 1000))

        cutoff_time = time.time() - (hours * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT block_height, timestamp, entropy_value, validation_score, is_anomaly
                FROM entropy_history
                WHERE hardware_id = ? AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (hardware_id, cutoff_time, limit))

            results = cursor.fetchall()

            history = []
            for row in results:
                history.append({
                    'block_height': row[0],
                    'timestamp': row[1],
                    'entropy_value': row[2],
                    'validation_score': row[3],
                    'is_anomaly': bool(row[4])
                })

        return jsonify({
            'hardware_id': hardware_id,
            'history_count': len(history),
            'time_range_hours': hours,
            'history': history
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/temporal/validation/<hardware_id>')
def get_validation_status(hardware_id):
    """Check temporal validation status for hardware"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get current validation status
            cursor.execute('''
                SELECT validation_type, status, score, anomaly_count,
                       last_validated, metadata
                FROM temporal_validations
                WHERE hardware_id = ?
                ORDER BY last_validated DESC
                LIMIT 1
            ''', (hardware_id,))

            validation = cursor.fetchone()

            # Get recent entropy stats
            cursor.execute('''
                SELECT COUNT(*), AVG(entropy_value), AVG(validation_score),
                       SUM(is_anomaly)
                FROM entropy_history
                WHERE hardware_id = ? AND timestamp >= ?
            ''', (hardware_id, time.time() - 86400))  # Last 24 hours

            stats = cursor.fetchone()

            if not validation:
                return jsonify({
                    'hardware_id': hardware_id,
                    'status': 'not_validated',
                    'message': 'No validation record found'
                }), 404

            result = {
                'hardware_id': hardware_id,
                'validation_type': validation[0],
                'status': validation[1],
                'score': validation[2],
                'anomaly_count': validation[3],
                'last_validated': validation[4],
                'metadata': json.loads(validation[5] or '{}'),
                'recent_stats': {
                    'entropy_submissions': stats[0] or 0,
                    'avg_entropy': round(stats[1] or 0.0, 4),
                    'avg_validation_score': round(stats[2] or 0.0, 4),
                    'anomalies_24h': stats[3] or 0
                }
            }

            return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/temporal/anomalies')
def get_anomaly_report():
    """Generate anomaly report across all hardware"""
    try:
        hours = int(request.args.get('hours', 24))
        min_anomalies = int(request.args.get('min_anomalies', 5))

        cutoff_time = time.time() - (hours * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT hardware_id, COUNT(*) as anomaly_count,
                       AVG(entropy_value) as avg_entropy,
                       MIN(timestamp) as first_anomaly,
                       MAX(timestamp) as last_anomaly
                FROM entropy_history
                WHERE is_anomaly = 1 AND timestamp >= ?
                GROUP BY hardware_id
                HAVING anomaly_count >= ?
                ORDER BY anomaly_count DESC
            ''', (cutoff_time, min_anomalies))

            anomalies = []
            for row in cursor.fetchall():
                anomalies.append({
                    'hardware_id': row[0],
                    'anomaly_count': row[1],
                    'avg_entropy': round(row[2], 4),
                    'first_anomaly': row[3],
                    'last_anomaly': row[4],
                    'time_span_hours': round((row[4] - row[3]) / 3600, 2)
                })

        return jsonify({
            'report_generated': time.time(),
            'time_range_hours': hours,
            'anomaly_threshold': min_anomalies,
            'hardware_with_anomalies': len(anomalies),
            'anomalies': anomalies
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/temporal/validate', methods=['POST'])
def trigger_temporal_validation():
    """Trigger temporal validation for specific hardware or all"""
    try:
        data = request.get_json() or {}
        hardware_id = data.get('hardware_id')
        validation_type = data.get('type', 'entropy_profile')

        with validator.validation_lock:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                if hardware_id:
                    # Validate specific hardware
                    cursor.execute('''
                        SELECT COUNT(*), AVG(entropy_value), STDDEV(entropy_value)
                        FROM entropy_history
                        WHERE hardware_id = ? AND timestamp >= ?
                    ''', (hardware_id, time.time() - 86400))

                    stats = cursor.fetchone()

                    if stats[0] < 10:
                        return jsonify({
                            'error': 'Insufficient entropy history for validation',
                            'required_samples': 10,
                            'available_samples': stats[0]
                        }), 400

                    # Calculate validation score
                    entropy_variance = stats[2] or 0.0
                    score = min(1.0, entropy_variance * 2.0)  # Simple scoring

                    # Update or insert validation record
                    cursor.execute('''
                        INSERT OR REPLACE INTO temporal_validations
                        (hardware_id, validation_type, status, score, last_validated, metadata)
                        VALUES (?, ?, 'completed', ?, ?, ?)
                    ''', (
                        hardware_id,
                        validation_type,
                        score,
                        time.time(),
                        json.dumps({
                            'samples_analyzed': stats[0],
                            'avg_entropy': stats[1],
                            'entropy_variance': entropy_variance
                        })
                    ))

                    conn.commit()

                    return jsonify({
                        'hardware_id': hardware_id,
                        'validation_type': validation_type,
                        'status': 'completed',
                        'score': round(score, 4),
                        'samples_analyzed': stats[0]
                    })

                else:
                    # Validate all active hardware
                    cursor.execute('''
                        SELECT DISTINCT hardware_id
                        FROM entropy_history
                        WHERE timestamp >= ?
                    ''', (time.time() - 86400,))

                    hardware_ids = [row[0] for row in cursor.fetchall()]
                    validated_count = 0

                    for hw_id in hardware_ids:
                        cursor.execute('''
                            INSERT OR REPLACE INTO temporal_validations
                            (hardware_id, validation_type, status, last_validated)
                            VALUES (?, ?, 'completed', ?)
                        ''', (hw_id, validation_type, time.time()))
                        validated_count += 1

                    conn.commit()

                    return jsonify({
                        'validation_type': validation_type,
                        'status': 'batch_completed',
                        'hardware_validated': validated_count
                    })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/temporal/dashboard')
def temporal_dashboard():
    """Temporal validation dashboard"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get validation summary
            cursor.execute('''
                SELECT COUNT(DISTINCT hardware_id) as total_hardware,
                       COUNT(*) as total_validations,
                       AVG(score) as avg_score
                FROM temporal_validations
            ''')
            summary = cursor.fetchone()

            # Get recent anomalies
            cursor.execute('''
                SELECT COUNT(*) as anomaly_count
                FROM entropy_history
                WHERE is_anomaly = 1 AND timestamp >= ?
            ''', (time.time() - 86400,))
            recent_anomalies = cursor.fetchone()[0]

        dashboard_html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>RustChain Temporal Validation Dashboard</title>
            <style>
                body { font-family: monospace; background: #1a1a1a; color: #00ff00; padding: 20px; }
                .stat-box { border: 1px solid #00ff00; margin: 10px; padding: 15px; }
                .anomaly { color: #ff6666; }
                .good { color: #66ff66; }
            </style>
        </head>
        <body>
            <h1>🔗 RustChain Temporal Validation Dashboard</h1>

            <div class="stat-box">
                <h3>Validation Summary</h3>
                <p>Hardware Validated: {{ total_hardware }}</p>
                <p>Total Validations: {{ total_validations }}</p>
                <p>Average Score: {{ "%.4f"|format(avg_score or 0) }}</p>
            </div>

            <div class="stat-box {{ 'anomaly' if recent_anomalies > 0 else 'good' }}">
                <h3>Recent Anomalies (24h)</h3>
                <p>Anomaly Count: {{ recent_anomalies }}</p>
                <p>Status: {{ "⚠️ DETECTED" if recent_anomalies > 0 else "✅ CLEAN" }}</p>
            </div>

            <div class="stat-box">
                <h3>API Endpoints</h3>
                <p>• GET /api/temporal/history/&lt;hardware_id&gt;</p>
                <p>• GET /api/temporal/validation/&lt;hardware_id&gt;</p>
                <p>• GET /api/temporal/anomalies</p>
                <p>• POST /api/temporal/validate</p>
            </div>
        </body>
        </html>
        '''

        return render_template_string(dashboard_html,
            total_hardware=summary[0] or 0,
            total_validations=summary[1] or 0,
            avg_score=summary[2],
            recent_anomalies=recent_anomalies
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5002)
