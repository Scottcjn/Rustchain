// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify, render_template_string
import sqlite3
import json
from datetime import datetime, timedelta
import hashlib

DB_PATH = "rustchain.db"

app = Flask(__name__)

def init_sophia_inspections_table():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sophia_inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                block_hash TEXT NOT NULL,
                hardware_fingerprint TEXT NOT NULL,
                verdict TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                reasoning TEXT,
                timestamp INTEGER NOT NULL,
                sophia_version TEXT DEFAULT 'elyan-sophia:7b-q4_K_M'
            )
        ''')
        conn.commit()

def get_sophia_verdict(miner_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT verdict, confidence_score, reasoning, timestamp
            FROM sophia_inspections 
            WHERE miner_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        ''', (miner_id,))
        return cursor.fetchone()

def get_verdict_history(miner_id, days=30):
    cutoff = int((datetime.now() - timedelta(days=days)).timestamp())
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT verdict, confidence_score, reasoning, timestamp, block_hash
            FROM sophia_inspections 
            WHERE miner_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
        ''', (miner_id, cutoff))
        return cursor.fetchall()

def format_verdict_emoji(verdict, confidence):
    if verdict == "VALID" and confidence >= 0.85:
        return "✨ Sophia Elya Check: OK!"
    elif verdict == "VALID" and confidence >= 0.70:
        return "⚠️ Sophia Elya Check: Caution"
    elif verdict == "SUSPICIOUS":
        return "🔍 Sophia Elya Check: Under Review"
    else:
        return "❌ Sophia Elya Check: Failed"

@app.route('/sophia/explorer')
def sophia_explorer():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT DISTINCT miner_id FROM sophia_inspections
            ORDER BY miner_id
        ''')
        miners = [row[0] for row in cursor.fetchall()]
    
    miner_verdicts = []
    for miner_id in miners:
        verdict_data = get_sophia_verdict(miner_id)
        if verdict_data:
            verdict, confidence, reasoning, timestamp = verdict_data
            emoji_status = format_verdict_emoji(verdict, confidence)
            miner_verdicts.append({
                'miner_id': miner_id,
                'verdict': verdict,
                'confidence': confidence,
                'emoji_status': emoji_status,
                'reasoning': reasoning,
                'timestamp': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            })
    
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SophiaCore Attestation Inspector</title>
        <style>
            body { font-family: monospace; background: #0a0a0a; color: #00ff41; margin: 20px; }
            .header { border-bottom: 2px solid #00ff41; padding-bottom: 10px; margin-bottom: 20px; }
            .miner-card { 
                border: 1px solid #333; 
                margin: 10px 0; 
                padding: 15px; 
                background: #111;
                border-radius: 5px;
            }
            .verdict-ok { color: #00ff41; }
            .verdict-caution { color: #ffaa00; }
            .verdict-review { color: #ff6600; }
            .verdict-failed { color: #ff0000; }
            .confidence { font-size: 0.9em; opacity: 0.8; }
            .reasoning { 
                margin-top: 10px; 
                padding: 10px; 
                background: #222; 
                border-left: 3px solid #00ff41;
                font-size: 0.85em;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🤖 SophiaCore Attestation Inspector</h1>
            <p>AI-powered hardware validation by Sophia Elya (elyan-sophia:7b-q4_K_M)</p>
        </div>
        
        {% for miner in miner_verdicts %}
        <div class="miner-card">
            <h3>Miner: {{ miner.miner_id }}</h3>
            <div class="{% if 'OK!' in miner.emoji_status %}verdict-ok{% elif 'Caution' in miner.emoji_status %}verdict-caution{% elif 'Review' in miner.emoji_status %}verdict-review{% else %}verdict-failed{% endif %}">
                <strong>{{ miner.emoji_status }}</strong>
            </div>
            <div class="confidence">
                Confidence: {{ "%.2f"|format(miner.confidence) }} | 
                Verdict: {{ miner.verdict }} |
                {{ miner.timestamp }}
            </div>
            {% if miner.reasoning %}
            <div class="reasoning">
                <strong>Sophia's Analysis:</strong><br>
                {{ miner.reasoning }}
            </div>
            {% endif %}
            <p><a href="/sophia/miner/{{ miner.miner_id }}" style="color: #00ff41;">View History →</a></p>
        </div>
        {% endfor %}
        
        {% if not miner_verdicts %}
        <div class="miner-card">
            <p>No Sophia Elya inspections found. Waiting for hardware attestations...</p>
        </div>
        {% endif %}
    </body>
    </html>
    '''
    
    return render_template_string(template, miner_verdicts=miner_verdicts)

@app.route('/sophia/miner/<miner_id>')
def sophia_miner_history(miner_id):
    history = get_verdict_history(miner_id)
    
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sophia History: {{ miner_id }}</title>
        <style>
            body { font-family: monospace; background: #0a0a0a; color: #00ff41; margin: 20px; }
            .header { border-bottom: 2px solid #00ff41; padding-bottom: 10px; margin-bottom: 20px; }
            .inspection { 
                border: 1px solid #333; 
                margin: 10px 0; 
                padding: 15px; 
                background: #111;
                border-radius: 5px;
            }
            .verdict-valid { color: #00ff41; }
            .verdict-suspicious { color: #ff6600; }
            .verdict-invalid { color: #ff0000; }
            .meta { font-size: 0.9em; opacity: 0.7; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔍 Sophia History: {{ miner_id }}</h1>
            <p><a href="/sophia/explorer" style="color: #00ff41;">← Back to Explorer</a></p>
        </div>
        
        {% for record in history %}
        <div class="inspection">
            <div class="verdict-{{ record[0].lower() }}">
                <strong>{{ format_verdict_emoji(record[0], record[1]) }}</strong>
            </div>
            <div class="meta">
                Block: {{ record[4] }} | 
                Confidence: {{ "%.3f"|format(record[1]) }} |
                {{ datetime.fromtimestamp(record[3]).strftime('%Y-%m-%d %H:%M:%S') }}
            </div>
            {% if record[2] %}
            <div style="margin-top: 10px; padding: 10px; background: #222; border-left: 3px solid #00ff41; font-size: 0.9em;">
                {{ record[2] }}
            </div>
            {% endif %}
        </div>
        {% endfor %}
        
        {% if not history %}
        <div class="inspection">
            <p>No inspection history found for this miner.</p>
        </div>
        {% endif %}
    </body>
    </html>
    '''
    
    return render_template_string(template, 
                                miner_id=miner_id, 
                                history=history,
                                format_verdict_emoji=format_verdict_emoji,
                                datetime=datetime)

@app.route('/api/sophia/verdict/<miner_id>')
def api_sophia_verdict(miner_id):
    verdict_data = get_sophia_verdict(miner_id)
    if not verdict_data:
        return jsonify({"error": "No verdict found"}), 404
    
    verdict, confidence, reasoning, timestamp = verdict_data
    return jsonify({
        "miner_id": miner_id,
        "verdict": verdict,
        "confidence_score": confidence,
        "emoji_status": format_verdict_emoji(verdict, confidence),
        "reasoning": reasoning,
        "timestamp": timestamp,
        "sophia_version": "elyan-sophia:7b-q4_K_M"
    })

@app.route('/api/sophia/submit', methods=['POST'])
def api_submit_inspection():
    data = request.json
    required_fields = ['miner_id', 'block_hash', 'hardware_fingerprint', 'verdict', 'confidence_score']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO sophia_inspections 
            (miner_id, block_hash, hardware_fingerprint, verdict, confidence_score, reasoning, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['miner_id'],
            data['block_hash'],
            data['hardware_fingerprint'],
            data['verdict'],
            float(data['confidence_score']),
            data.get('reasoning', ''),
            int(datetime.now().timestamp())
        ))
        conn.commit()
    
    return jsonify({"status": "inspection_recorded", "miner_id": data['miner_id']})

if __name__ == '__main__':
    init_sophia_inspections_table()
    app.run(debug=True, port=5003)