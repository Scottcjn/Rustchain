// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import requests
import time
from flask import Flask, request, render_template_string, jsonify
import hashlib
from datetime import datetime, timedelta
import logging

DB_PATH = "rustchain.db"

class SophiaCoreInspector:
    def __init__(self):
        self.ollama_endpoints = [
            "https://sophia-nas.rustchain.net:11434",
            "https://power8.rustchain.net:11434",
            "http://localhost:11434"
        ]
        self.model_name = "elyan-sophia:7b-q4_K_M"
        self.confidence_cache = {}
        self.cache_ttl = 1800  # 30 minutes
        
    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sophia_attestations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner_id TEXT NOT NULL,
                    fingerprint_hash TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    verdict TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    attestation_data TEXT NOT NULL
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sophia_miner ON sophia_attestations(miner_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sophia_hash ON sophia_attestations(fingerprint_hash)')

    def call_sophia_ollama(self, prompt):
        for endpoint in self.ollama_endpoints:
            try:
                response = requests.post(
                    f"{endpoint}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "top_p": 0.8,
                            "num_ctx": 4096
                        }
                    },
                    timeout=30
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "")
            except Exception as e:
                logging.warning(f"Sophia endpoint {endpoint} failed: {e}")
                continue
        return None

    def analyze_hardware_fingerprint(self, fingerprint_data):
        cache_key = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True).encode()).hexdigest()
        
        if cache_key in self.confidence_cache:
            cached_entry = self.confidence_cache[cache_key]
            if datetime.now() - cached_entry["timestamp"] < timedelta(seconds=self.cache_ttl):
                return cached_entry["result"]

        prompt = f"""Sophia Elya hardware attestation analysis:

FINGERPRINT DATA:
{json.dumps(fingerprint_data, indent=2)}

Analyze this hardware fingerprint for authenticity. Real hardware exhibits correlated imperfections and natural variation patterns. Synthetic data shows independently tuned values and perfect distributions.

Evaluate:
1. Cross-metric correlations (CPU-GPU-memory coherence)
2. Natural imperfection patterns vs artificial optimization
3. Temporal consistency markers
4. Hardware ecosystem logical relationships

Respond in JSON format:
{{
    "confidence_score": 0.85,
    "verdict": "AUTHENTIC|SUSPICIOUS|SYNTHETIC",
    "reasoning": "Brief technical explanation focusing on correlation patterns"
}}"""

        sophia_response = self.call_sophia_ollama(prompt)
        if not sophia_response:
            return {
                "confidence_score": 0.0,
                "verdict": "ERROR",
                "reasoning": "Sophia Elya inference unavailable - all endpoints failed"
            }

        try:
            result = json.loads(sophia_response.strip())
            if not all(k in result for k in ["confidence_score", "verdict", "reasoning"]):
                raise ValueError("Missing required fields")
            
            self.confidence_cache[cache_key] = {
                "result": result,
                "timestamp": datetime.now()
            }
            return result
            
        except Exception as e:
            return {
                "confidence_score": 0.0,
                "verdict": "PARSE_ERROR",
                "reasoning": f"Sophia response parsing failed: {str(e)}"
            }

    def store_attestation(self, miner_id, fingerprint_data, analysis_result):
        fingerprint_hash = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True).encode()).hexdigest()
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO sophia_attestations 
                (miner_id, fingerprint_hash, confidence_score, verdict, reasoning, attestation_data)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                miner_id,
                fingerprint_hash,
                analysis_result["confidence_score"],
                analysis_result["verdict"],
                analysis_result["reasoning"],
                json.dumps(fingerprint_data)
            ))

    def get_miner_status(self, miner_id):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT confidence_score, verdict, reasoning, timestamp
                FROM sophia_attestations 
                WHERE miner_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''', (miner_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "confidence_score": row[0],
                    "verdict": row[1],
                    "reasoning": row[2],
                    "timestamp": row[3],
                    "status": "✨ Sophia Elya Check: OK!" if row[1] == "AUTHENTIC" and row[0] > 0.7 else "⚠️ Sophia Elya Check: REVIEW"
                }
            return None

sophia_inspector = SophiaCoreInspector()

app = Flask(__name__)

@app.route('/sophia/inspect', methods=['POST'])
def sophia_inspect():
    data = request.get_json()
    if not data or 'miner_id' not in data or 'fingerprint' not in data:
        return jsonify({"error": "Missing miner_id or fingerprint data"}), 400
    
    miner_id = data['miner_id']
    fingerprint_data = data['fingerprint']
    
    analysis_result = sophia_inspector.analyze_hardware_fingerprint(fingerprint_data)
    sophia_inspector.store_attestation(miner_id, fingerprint_data, analysis_result)
    
    return jsonify({
        "miner_id": miner_id,
        "sophia_analysis": analysis_result,
        "timestamp": datetime.now().isoformat(),
        "inspector": "Sophia Elya (elyan-sophia:7b-q4_K_M)"
    })

@app.route('/sophia/status/<miner_id>')
def sophia_status(miner_id):
    status = sophia_inspector.get_miner_status(miner_id)
    if not status:
        return jsonify({"error": "No attestation found for miner"}), 404
    return jsonify(status)

@app.route('/sophia/dashboard')
def sophia_dashboard():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT miner_id, confidence_score, verdict, reasoning, timestamp
            FROM sophia_attestations 
            ORDER BY timestamp DESC 
            LIMIT 50
        ''')
        attestations = cursor.fetchall()
        
        stats_cursor = conn.execute('''
            SELECT 
                verdict,
                COUNT(*) as count,
                AVG(confidence_score) as avg_confidence
            FROM sophia_attestations 
            WHERE timestamp > datetime('now', '-24 hours')
            GROUP BY verdict
        ''')
        stats = stats_cursor.fetchall()

    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SophiaCore Attestation Inspector</title>
        <style>
            body { font-family: monospace; background: #0a0a0a; color: #00ff41; margin: 20px; }
            .header { border-bottom: 1px solid #00ff41; padding-bottom: 10px; margin-bottom: 20px; }
            .stats { display: flex; gap: 20px; margin-bottom: 20px; }
            .stat-box { border: 1px solid #00ff41; padding: 10px; min-width: 120px; }
            .attestation { border-bottom: 1px solid #333; padding: 10px 0; }
            .authentic { color: #00ff41; }
            .suspicious { color: #ffaa00; }
            .synthetic { color: #ff4444; }
            .error { color: #ff6666; }
            .confidence { font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔍 SophiaCore Attestation Inspector</h1>
            <p>Sophia Elya (elyan-sophia:7b-q4_K_M) - AI-powered hardware validation</p>
        </div>
        
        <div class="stats">
            {% for stat in stats %}
            <div class="stat-box">
                <div>{{ stat[0] }}</div>
                <div>{{ stat[1] }} attestations</div>
                <div>Avg: {{ "%.2f"|format(stat[2]) }}</div>
            </div>
            {% endfor %}
        </div>
        
        <h2>Recent Attestations</h2>
        {% for att in attestations %}
        <div class="attestation">
            <div><strong>{{ att[0] }}</strong> | {{ att[4] }}</div>
            <div class="confidence {{ att[2].lower() }}">
                {{ att[2] }} ({{ "%.3f"|format(att[1]) }})
            </div>
            <div style="color: #888; font-size: 12px;">{{ att[3] }}</div>
        </div>
        {% endfor %}
    </body>
    </html>
    '''
    
    return render_template_string(html, attestations=attestations, stats=stats)

if __name__ == '__main__':
    sophia_inspector.init_db()
    app.run(host='0.0.0.0', port=5007, debug=False)