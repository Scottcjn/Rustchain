// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import requests
import time
import hashlib
from flask import Flask, render_template_string, jsonify, request

DB_PATH = 'rustchain.db'
OLLAMA_BASE_URL = 'http://localhost:11434'
ELYAN_MODEL = 'elyan-sophia:7b-q4_K_M'

app = Flask(__name__)

def init_sophia_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sophia_attestations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                hardware_fingerprint TEXT NOT NULL,
                attestation_hash TEXT NOT NULL,
                sophia_verdict TEXT,
                confidence_score REAL,
                reasoning TEXT,
                timestamp INTEGER,
                block_height INTEGER
            )
        ''')
        conn.commit()

def query_ollama(prompt, model=ELYAN_MODEL):
    try:
        payload = {
            'model': model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': 0.1,
                'top_p': 0.9
            }
        }
        response = requests.post(f'{OLLAMA_BASE_URL}/api/generate', json=payload, timeout=30)
        if response.status_code == 200:
            return response.json().get('response', '')
        return None
    except Exception:
        return None

def sophia_inspect_attestation(fingerprint_data):
    fingerprint = json.loads(fingerprint_data) if isinstance(fingerprint_data, str) else fingerprint_data
    
    prompt = f"""Analyze this hardware fingerprint for authenticity. Real hardware shows correlated imperfections, synthetic data shows independent tuning.

Hardware metrics:
- CPU cores: {fingerprint.get('cpu_cores', 'unknown')}
- Memory: {fingerprint.get('memory_mb', 'unknown')} MB
- Disk space: {fingerprint.get('disk_gb', 'unknown')} GB
- Network latency: {fingerprint.get('network_latency_ms', 'unknown')} ms
- CPU temp: {fingerprint.get('cpu_temp_c', 'unknown')} C
- Power draw: {fingerprint.get('power_watts', 'unknown')} W
- Boot time: {fingerprint.get('boot_time_s', 'unknown')} s

Evaluate:
1. Do metrics correlate realistically?
2. Are values too perfect/rounded?
3. Do thermal/power readings match workload?

Format: VERDICT:AUTHENTIC|SUSPICIOUS|SYNTHETIC CONFIDENCE:0.XX REASONING:brief explanation"""

    sophia_response = query_ollama(prompt)
    if not sophia_response:
        return 'UNKNOWN', 0.0, 'Sophia Elya unavailable'
    
    lines = sophia_response.strip().split('\n')
    verdict = 'UNKNOWN'
    confidence = 0.0
    reasoning = 'Analysis incomplete'
    
    for line in lines:
        if line.startswith('VERDICT:'):
            verdict = line.split(':', 1)[1].strip()
        elif line.startswith('CONFIDENCE:'):
            try:
                confidence = float(line.split(':', 1)[1].strip())
            except ValueError:
                confidence = 0.0
        elif line.startswith('REASONING:'):
            reasoning = line.split(':', 1)[1].strip()
    
    return verdict, confidence, reasoning

def process_miner_attestation(miner_id, hardware_fingerprint, block_height):
    attestation_data = f"{miner_id}:{hardware_fingerprint}:{block_height}"
    attestation_hash = hashlib.sha256(attestation_data.encode()).hexdigest()
    
    verdict, confidence, reasoning = sophia_inspect_attestation(hardware_fingerprint)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO sophia_attestations 
            (miner_id, hardware_fingerprint, attestation_hash, sophia_verdict, 
             confidence_score, reasoning, timestamp, block_height)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (miner_id, hardware_fingerprint, attestation_hash, verdict, 
              confidence, reasoning, int(time.time()), block_height))
        conn.commit()
    
    return {
        'attestation_hash': attestation_hash,
        'verdict': verdict,
        'confidence': confidence,
        'reasoning': reasoning
    }

def get_miner_sophia_status(miner_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT sophia_verdict, confidence_score, reasoning, timestamp
            FROM sophia_attestations 
            WHERE miner_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        ''', (miner_id,))
        result = cursor.fetchone()
        
        if result:
            verdict, confidence, reasoning, timestamp = result
            is_ok = verdict == 'AUTHENTIC' and confidence >= 0.75
            return {
                'status': 'OK' if is_ok else 'FLAGGED',
                'verdict': verdict,
                'confidence': confidence,
                'reasoning': reasoning,
                'last_check': timestamp
            }
        return None

@app.route('/sophia/inspect', methods=['POST'])
def sophia_inspect():
    data = request.get_json()
    miner_id = data.get('miner_id')
    hardware_fingerprint = data.get('hardware_fingerprint')
    block_height = data.get('block_height', 0)
    
    if not miner_id or not hardware_fingerprint:
        return jsonify({'error': 'Missing miner_id or hardware_fingerprint'}), 400
    
    result = process_miner_attestation(miner_id, hardware_fingerprint, block_height)
    return jsonify(result)

@app.route('/sophia/miner/<miner_id>')
def miner_sophia_status(miner_id):
    status = get_miner_sophia_status(miner_id)
    if status:
        return jsonify(status)
    return jsonify({'error': 'No attestation found'}), 404

@app.route('/sophia/dashboard')
def sophia_dashboard():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT miner_id, sophia_verdict, confidence_score, reasoning, timestamp
            FROM sophia_attestations 
            ORDER BY timestamp DESC 
            LIMIT 50
        ''')
        attestations = cursor.fetchall()
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SophiaCore Attestation Inspector</title>
        <style>
            body { font-family: monospace; background: #0a0a0a; color: #00ff88; margin: 20px; }
            .header { color: #ffaa00; font-size: 24px; margin-bottom: 20px; }
            .attestation { border: 1px solid #333; margin: 10px 0; padding: 15px; }
            .verdict-authentic { color: #00ff88; }
            .verdict-suspicious { color: #ffaa00; }
            .verdict-synthetic { color: #ff4444; }
            .confidence { font-weight: bold; }
            .reasoning { font-style: italic; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div class="header">✨ SophiaCore Attestation Inspector</div>
        <div>Sophia Elya validates hardware fingerprints with semantic reasoning</div>
        <br>
        
        {% for att in attestations %}
        <div class="attestation">
            <strong>Miner:</strong> {{ att[0] }}<br>
            <strong>Verdict:</strong> <span class="verdict-{{ att[1].lower() }}">{{ att[1] }}</span><br>
            <strong>Confidence:</strong> <span class="confidence">{{ "%.2f"|format(att[2]) }}</span><br>
            <strong>Time:</strong> {{ att[4] }}<br>
            <div class="reasoning">{{ att[3] }}</div>
        </div>
        {% endfor %}
    </body>
    </html>
    '''
    
    return render_template_string(html, attestations=attestations)

if __name__ == '__main__':
    init_sophia_db()
    app.run(debug=True, port=5006)