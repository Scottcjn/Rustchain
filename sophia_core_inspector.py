// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
import requests
import hashlib
import random
from flask import Flask, request, jsonify, render_template_string

DB_PATH = 'sophia_core.db'

OLLAMA_ENDPOINTS = [
    'http://localhost:11434',
    'http://127.0.0.1:11434',
    'http://sophia-node-1:11434',
    'http://sophia-node-2:11434'
]

MODEL_NAME = 'elyan-sophia:7b-q4_K_M'

app = Flask(__name__)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS sophia_attestations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            miner_id TEXT NOT NULL,
            attestation_hash TEXT NOT NULL,
            hardware_bundle TEXT NOT NULL,
            sophia_verdict TEXT,
            confidence_score REAL,
            reasoning TEXT,
            timestamp INTEGER,
            endpoint_used TEXT
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS sophia_sessions (
            session_id TEXT PRIMARY KEY,
            endpoint TEXT,
            model_status TEXT,
            last_ping INTEGER,
            response_time_ms INTEGER
        )''')

def get_active_endpoint():
    for endpoint in OLLAMA_ENDPOINTS:
        try:
            resp = requests.get(f'{endpoint}/api/tags', timeout=3)
            if resp.status_code == 200:
                models = resp.json().get('models', [])
                for model in models:
                    if MODEL_NAME in model.get('name', ''):
                        return endpoint
        except:
            continue
    return None

def query_sophia_elya(hardware_bundle, endpoint):
    prompt = f"""Hardware Attestation Analysis by Sophia Elya:

Bundle Data:
{json.dumps(hardware_bundle, indent=2)}

Evaluate this hardware fingerprint for authenticity. Real hardware exhibits correlated imperfections and natural variations. Synthetic data shows independently tuned values.

Analyze:
- Temperature correlations across components
- Power draw patterns vs computational load
- Memory timing variance consistency
- CPU frequency stability under load

Respond with JSON:
{{"verdict": "AUTHENTIC|SUSPICIOUS|SYNTHETIC", "confidence": 0.85, "reasoning": "brief technical assessment"}}"""

    try:
        start_time = time.time()
        response = requests.post(f'{endpoint}/api/generate', 
            json={
                'model': MODEL_NAME,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': 0.1,
                    'top_p': 0.9,
                    'num_predict': 200
                }
            }, timeout=30)
        
        response_time = int((time.time() - start_time) * 1000)
        
        if response.status_code == 200:
            result = response.json()
            sophia_response = result.get('response', '')
            
            try:
                verdict_data = json.loads(sophia_response.strip())
                return verdict_data, response_time
            except:
                return {
                    'verdict': 'ERROR',
                    'confidence': 0.0,
                    'reasoning': 'Failed to parse Sophia response'
                }, response_time
        else:
            return None, response_time
            
    except Exception as e:
        return None, 0

def store_attestation(miner_id, attestation_hash, hardware_bundle, verdict_data, endpoint):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''INSERT INTO sophia_attestations 
            (miner_id, attestation_hash, hardware_bundle, sophia_verdict, confidence_score, reasoning, timestamp, endpoint_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (miner_id, attestation_hash, json.dumps(hardware_bundle), 
             verdict_data.get('verdict'), verdict_data.get('confidence'), 
             verdict_data.get('reasoning'), int(time.time()), endpoint))

@app.route('/sophia/inspect', methods=['POST'])
def inspect_attestation():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    miner_id = data.get('miner_id')
    hardware_bundle = data.get('hardware_bundle')
    
    if not miner_id or not hardware_bundle:
        return jsonify({'error': 'Missing miner_id or hardware_bundle'}), 400
    
    attestation_hash = hashlib.sha256(json.dumps(hardware_bundle, sort_keys=True).encode()).hexdigest()[:16]
    
    endpoint = get_active_endpoint()
    if not endpoint:
        return jsonify({
            'error': 'Sophia Elya unavailable',
            'verdict': 'UNAVAILABLE',
            'confidence': 0.0,
            'reasoning': 'No active Ollama endpoints found'
        }), 503
    
    verdict_data, response_time = query_sophia_elya(hardware_bundle, endpoint)
    
    if not verdict_data:
        return jsonify({
            'error': 'Sophia Elya query failed',
            'verdict': 'ERROR',
            'confidence': 0.0,
            'reasoning': 'LLM inference error'
        }), 500
    
    store_attestation(miner_id, attestation_hash, hardware_bundle, verdict_data, endpoint)
    
    return jsonify({
        'miner_id': miner_id,
        'attestation_hash': attestation_hash,
        'sophia_verdict': verdict_data.get('verdict'),
        'confidence_score': verdict_data.get('confidence'),
        'reasoning': verdict_data.get('reasoning'),
        'inspector': 'Sophia Elya',
        'model': MODEL_NAME,
        'response_time_ms': response_time,
        'timestamp': int(time.time())
    })

@app.route('/sophia/status')
def sophia_status():
    endpoints_status = []
    
    for endpoint in OLLAMA_ENDPOINTS:
        try:
            start = time.time()
            resp = requests.get(f'{endpoint}/api/tags', timeout=3)
            ping_ms = int((time.time() - start) * 1000)
            
            if resp.status_code == 200:
                models = resp.json().get('models', [])
                has_sophia = any(MODEL_NAME in m.get('name', '') for m in models)
                endpoints_status.append({
                    'endpoint': endpoint,
                    'status': 'ACTIVE' if has_sophia else 'NO_MODEL',
                    'ping_ms': ping_ms,
                    'sophia_available': has_sophia
                })
            else:
                endpoints_status.append({
                    'endpoint': endpoint,
                    'status': 'ERROR',
                    'ping_ms': ping_ms,
                    'sophia_available': False
                })
        except:
            endpoints_status.append({
                'endpoint': endpoint,
                'status': 'OFFLINE',
                'ping_ms': 0,
                'sophia_available': False
            })
    
    active_count = sum(1 for e in endpoints_status if e['sophia_available'])
    
    return jsonify({
        'inspector_name': 'Sophia Elya',
        'model': MODEL_NAME,
        'active_endpoints': active_count,
        'total_endpoints': len(OLLAMA_ENDPOINTS),
        'endpoints': endpoints_status,
        'system_status': 'OPERATIONAL' if active_count > 0 else 'DEGRADED'
    })

@app.route('/sophia/history/<miner_id>')
def miner_history(miner_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''SELECT attestation_hash, sophia_verdict, confidence_score, 
            reasoning, timestamp, endpoint_used FROM sophia_attestations 
            WHERE miner_id = ? ORDER BY timestamp DESC LIMIT 50''', (miner_id,))
        
        attestations = []
        for row in cursor.fetchall():
            attestations.append({
                'attestation_hash': row[0],
                'verdict': row[1],
                'confidence': row[2],
                'reasoning': row[3],
                'timestamp': row[4],
                'endpoint': row[5]
            })
    
    return jsonify({
        'miner_id': miner_id,
        'attestation_count': len(attestations),
        'attestations': attestations
    })

@app.route('/sophia/dashboard')
def dashboard():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''SELECT COUNT(*) as total, 
            AVG(confidence_score) as avg_confidence,
            COUNT(CASE WHEN sophia_verdict = 'AUTHENTIC' THEN 1 END) as authentic,
            COUNT(CASE WHEN sophia_verdict = 'SUSPICIOUS' THEN 1 END) as suspicious,
            COUNT(CASE WHEN sophia_verdict = 'SYNTHETIC' THEN 1 END) as synthetic
            FROM sophia_attestations WHERE timestamp > ?''', (int(time.time()) - 86400,))
        
        stats = cursor.fetchone()
        
        recent_cursor = conn.execute('''SELECT miner_id, sophia_verdict, confidence_score, 
            timestamp FROM sophia_attestations ORDER BY timestamp DESC LIMIT 10''')
        recent = recent_cursor.fetchall()
    
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head><title>SophiaCore Inspector Dashboard</title>
    <style>
    body { font-family: monospace; background: #0a0a0a; color: #00ff00; padding: 20px; }
    .header { border-bottom: 2px solid #00ff00; margin-bottom: 20px; }
    .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }
    .stat-box { border: 1px solid #00ff00; padding: 15px; text-align: center; }
    .recent { margin-top: 30px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border: 1px solid #00ff00; padding: 8px; text-align: left; }
    .authentic { color: #00ff00; }
    .suspicious { color: #ffaa00; }
    .synthetic { color: #ff0000; }
    </style>
    </head>
    <body>
    <div class="header">
        <h1>🧠 SophiaCore Attestation Inspector</h1>
        <p>AI-Powered Hardware Validation by Sophia Elya</p>
    </div>
    
    <div class="stats">
        <div class="stat-box">
            <h3>Total Inspections</h3>
            <h2>{{ stats[0] or 0 }}</h2>
        </div>
        <div class="stat-box">
            <h3>Avg Confidence</h3>
            <h2>{{ "%.2f"|format(stats[1] or 0) }}</h2>
        </div>
        <div class="stat-box">
            <h3>Authentic Rate</h3>
            <h2>{{ "%.1f"|format(((stats[2] or 0) / (stats[0] or 1)) * 100) }}%</h2>
        </div>
        <div class="stat-box">
            <h3>Threat Detection</h3>
            <h2>{{ stats[4] or 0 }} synthetic</h2>
        </div>
    </div>
    
    <div class="recent">
        <h3>Recent Inspections</h3>
        <table>
            <tr><th>Miner ID</th><th>Verdict</th><th>Confidence</th><th>Time</th></tr>
            {% for inspection in recent %}
            <tr>
                <td>{{ inspection[0] }}</td>
                <td class="{{ inspection[1].lower() }}">{{ inspection[1] }}</td>
                <td>{{ "%.3f"|format(inspection[2] or 0) }}</td>
                <td>{{ inspection[3] }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    </body>
    </html>
    '''
    
    return render_template_string(html_template, stats=stats, recent=recent)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8090, debug=False)