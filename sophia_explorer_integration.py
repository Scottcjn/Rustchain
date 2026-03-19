// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, render_template_string, request, jsonify
import sqlite3
import json
import time
from datetime import datetime

app = Flask(__name__)

DB_PATH = 'rustchain.db'

def init_sophia_tables():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS sophia_verdicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            miner_address TEXT NOT NULL,
            block_height INTEGER NOT NULL,
            fingerprint_hash TEXT NOT NULL,
            verdict TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            reasoning TEXT,
            timestamp INTEGER NOT NULL,
            elyan_model_version TEXT DEFAULT 'elyan-sophia:7b-q4_K_M'
        )''')
        
        c.execute('''CREATE INDEX IF NOT EXISTS idx_sophia_miner 
                     ON sophia_verdicts(miner_address)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_sophia_block 
                     ON sophia_verdicts(block_height)''')
        
        conn.commit()

def get_sophia_verdict_emoji(verdict):
    verdict_emojis = {
        'APPROVED': '✨',
        'SUSPICIOUS': '⚠️',
        'REJECTED': '❌',
        'ANALYZING': '🔍',
        'ERROR': '💥'
    }
    return verdict_emojis.get(verdict, '❓')

@app.route('/sophia/explorer')
def sophia_explorer():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        c.execute('''SELECT DISTINCT miner_address FROM blocks 
                     ORDER BY height DESC LIMIT 50''')
        miners = [row[0] for row in c.fetchall()]
        
        miner_verdicts = {}
        for miner in miners:
            c.execute('''SELECT verdict, confidence_score, timestamp 
                         FROM sophia_verdicts 
                         WHERE miner_address = ? 
                         ORDER BY timestamp DESC LIMIT 1''', (miner,))
            result = c.fetchone()
            if result:
                verdict, confidence, ts = result
                miner_verdicts[miner] = {
                    'verdict': verdict,
                    'confidence': confidence,
                    'emoji': get_sophia_verdict_emoji(verdict),
                    'timestamp': ts
                }
    
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Sophia Elya Explorer - RustChain</title>
    <style>
        body { font-family: 'SF Mono', monospace; background: #0a0a0a; color: #e0e0e0; padding: 20px; }
        .header { color: #ff6b35; font-size: 24px; margin-bottom: 30px; }
        .miner-card { 
            background: #1a1a1a; 
            border: 1px solid #333; 
            border-radius: 8px; 
            padding: 15px; 
            margin: 10px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .miner-addr { font-weight: bold; color: #4CAF50; }
        .sophia-status { 
            font-size: 18px; 
            padding: 5px 10px;
            border-radius: 20px;
            background: #2a2a2a;
        }
        .confidence { font-size: 12px; color: #888; margin-left: 10px; }
        .approved { border-left: 3px solid #4CAF50; }
        .suspicious { border-left: 3px solid #FFC107; }
        .rejected { border-left: 3px solid #F44336; }
        .analyzing { border-left: 3px solid #2196F3; }
        .no-verdict { border-left: 3px solid #666; }
    </style>
</head>
<body>
    <div class="header">🤖 Sophia Elya Attestation Inspector</div>
    
    {% for miner in miners %}
    {% set verdict_data = miner_verdicts.get(miner) %}
    <div class="miner-card {% if verdict_data %}{{ verdict_data.verdict.lower() }}{% else %}no-verdict{% endif %}">
        <div>
            <div class="miner-addr">{{ miner[:20] }}...</div>
            <div style="font-size: 12px; color: #666;">
                {% if verdict_data %}
                    Last check: {{ verdict_data.timestamp | timestamp_to_date }}
                {% else %}
                    No attestation yet
                {% endif %}
            </div>
        </div>
        
        <div class="sophia-status">
            {% if verdict_data %}
                {{ verdict_data.emoji }} Sophia Elya: {{ verdict_data.verdict }}!
                <span class="confidence">{{ "%.1f" | format(verdict_data.confidence * 100) }}%</span>
            {% else %}
                ❓ Awaiting Sophia Analysis
            {% endif %}
        </div>
    </div>
    {% endfor %}
    
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>
    ''', miners=miners, miner_verdicts=miner_verdicts)

@app.route('/sophia/verdict/<miner_address>')
def miner_verdict_history(miner_address):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        c.execute('''SELECT verdict, confidence_score, reasoning, 
                            fingerprint_hash, block_height, timestamp, elyan_model_version
                     FROM sophia_verdicts 
                     WHERE miner_address = ? 
                     ORDER BY timestamp DESC LIMIT 20''', (miner_address,))
        
        verdicts = []
        for row in c.fetchall():
            verdicts.append({
                'verdict': row[0],
                'confidence': row[1],
                'reasoning': row[2],
                'fingerprint_hash': row[3],
                'block_height': row[4],
                'timestamp': row[5],
                'model_version': row[6],
                'emoji': get_sophia_verdict_emoji(row[0])
            })
    
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>{{ miner_address }} - Sophia Verdicts</title>
    <style>
        body { font-family: 'SF Mono', monospace; background: #0a0a0a; color: #e0e0e0; padding: 20px; }
        .header { color: #ff6b35; font-size: 20px; margin-bottom: 20px; }
        .verdict-entry { 
            background: #1a1a1a; 
            border: 1px solid #333; 
            border-radius: 8px; 
            padding: 15px; 
            margin: 15px 0;
        }
        .verdict-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .verdict-status { font-size: 18px; }
        .reasoning { 
            background: #2a2a2a; 
            padding: 10px; 
            border-radius: 5px; 
            margin: 10px 0;
            font-style: italic;
        }
        .metadata { font-size: 12px; color: #888; }
        .back-link { color: #4CAF50; text-decoration: none; }
    </style>
</head>
<body>
    <a href="/sophia/explorer" class="back-link">← Back to Explorer</a>
    
    <div class="header">Sophia Verdicts for {{ miner_address }}</div>
    
    {% for verdict in verdicts %}
    <div class="verdict-entry">
        <div class="verdict-header">
            <div class="verdict-status">
                {{ verdict.emoji }} {{ verdict.verdict }} 
                <span style="color: #888;">({{ "%.1f" | format(verdict.confidence * 100) }}%)</span>
            </div>
            <div class="metadata">Block {{ verdict.block_height }}</div>
        </div>
        
        {% if verdict.reasoning %}
        <div class="reasoning">{{ verdict.reasoning }}</div>
        {% endif %}
        
        <div class="metadata">
            Fingerprint: {{ verdict.fingerprint_hash[:16] }}...<br>
            Model: {{ verdict.model_version }}<br>
            Timestamp: {{ verdict.timestamp | timestamp_to_date }}
        </div>
    </div>
    {% endfor %}
    
    {% if not verdicts %}
    <div style="text-align: center; color: #666; margin-top: 50px;">
        No Sophia verdicts found for this miner.
    </div>
    {% endif %}
</body>
</html>
    ''', miner_address=miner_address, verdicts=verdicts)

@app.route('/api/sophia/submit_verdict', methods=['POST'])
def submit_sophia_verdict():
    data = request.json
    
    required_fields = ['miner_address', 'block_height', 'fingerprint_hash', 
                      'verdict', 'confidence_score']
    
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing field: {field}'}), 400
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        c.execute('''INSERT INTO sophia_verdicts 
                     (miner_address, block_height, fingerprint_hash, verdict, 
                      confidence_score, reasoning, timestamp, elyan_model_version)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (data['miner_address'],
                   data['block_height'],
                   data['fingerprint_hash'],
                   data['verdict'],
                   data['confidence_score'],
                   data.get('reasoning', ''),
                   int(time.time()),
                   data.get('elyan_model_version', 'elyan-sophia:7b-q4_K_M')))
        
        conn.commit()
    
    return jsonify({'status': 'success', 'message': 'Sophia verdict recorded'})

@app.route('/api/sophia/miner_status/<miner_address>')
def api_miner_status(miner_address):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        c.execute('''SELECT verdict, confidence_score, reasoning, timestamp 
                     FROM sophia_verdicts 
                     WHERE miner_address = ? 
                     ORDER BY timestamp DESC LIMIT 1''', (miner_address,))
        
        result = c.fetchone()
        if result:
            verdict, confidence, reasoning, timestamp = result
            return jsonify({
                'miner_address': miner_address,
                'verdict': verdict,
                'confidence_score': confidence,
                'reasoning': reasoning,
                'emoji': get_sophia_verdict_emoji(verdict),
                'timestamp': timestamp,
                'status': 'found'
            })
        else:
            return jsonify({
                'miner_address': miner_address,
                'status': 'no_verdict'
            })

def timestamp_to_date_filter(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

app.jinja_env.filters['timestamp_to_date'] = timestamp_to_date_filter

if __name__ == '__main__':
    init_sophia_tables()
    app.run(debug=True, host='0.0.0.0', port=5000)