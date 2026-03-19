// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT
"""Community Meme Gallery for RustChain"""

from flask import Flask, request, render_template_string, redirect, url_for, flash, jsonify
import sqlite3
import os
import uuid
import time
from datetime import datetime
from werkzeug.utils import secure_filename
import hashlib

app = Flask(__name__)
app.secret_key = 'rustchain_meme_gallery_2024'

DB_PATH = 'meme_gallery.db'
UPLOAD_FOLDER = 'static/uploads/memes'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    """Initialize the database with required tables"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Memes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meme_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                filename TEXT NOT NULL,
                author TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                votes INTEGER DEFAULT 0,
                rtc_earned REAL DEFAULT 0,
                status TEXT DEFAULT 'pending',
                image_hash TEXT,
                file_size INTEGER
            )
        ''')
        
        # Votes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meme_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meme_id TEXT NOT NULL,
                voter_ip TEXT NOT NULL,
                vote_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(meme_id, voter_ip)
            )
        ''')
        
        conn.commit()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_hash(filepath):
    """Generate hash for uploaded file"""
    hash_sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

@app.route('/')
def gallery():
    """Main gallery view showing all memes"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT meme_id, title, description, filename, author, 
                   votes, rtc_earned, status, created_at
            FROM memes 
            ORDER BY votes DESC, created_at DESC
        ''')
        memes = cursor.fetchall()
    
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Retro Meme Gallery</title>
        <style>
            body { 
                font-family: 'Courier New', monospace; 
                background: #001100; 
                color: #00ff00; 
                margin: 0; 
                padding: 20px;
            }
            .header {
                text-align: center;
                border: 2px solid #00ff00;
                padding: 20px;
                margin-bottom: 30px;
                background: #002200;
            }
            .meme-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }
            .meme-card {
                border: 1px solid #00ff00;
                padding: 15px;
                background: #003300;
                border-radius: 5px;
            }
            .meme-image {
                max-width: 100%;
                height: auto;
                border: 1px solid #006600;
            }
            .meme-info {
                margin-top: 10px;
            }
            .vote-buttons {
                margin-top: 10px;
            }
            .btn {
                background: #004400;
                border: 1px solid #00ff00;
                color: #00ff00;
                padding: 5px 10px;
                margin-right: 10px;
                cursor: pointer;
                font-family: inherit;
            }
            .btn:hover { background: #006600; }
            .submit-link {
                display: inline-block;
                margin: 20px 0;
                padding: 10px 20px;
                background: #440000;
                border: 2px solid #ff0000;
                color: #ff0000;
                text-decoration: none;
                font-weight: bold;
            }
            .stats { color: #ffff00; }
            .status-approved { color: #00ff00; }
            .status-pending { color: #ffff00; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🖥️ RUSTCHAIN RETRO MEME GALLERY 🖥️</h1>
            <p>Best retro computing & blockchain memes - Earn RTC!</p>
            <a href="/submit" class="submit-link">SUBMIT YOUR MEME</a>
        </div>
        
        <div class="meme-grid">
            {% for meme in memes %}
            <div class="meme-card">
                <img src="/static/uploads/memes/{{ meme[3] }}" class="meme-image" alt="{{ meme[1] }}">
                <div class="meme-info">
                    <h3>{{ meme[1] }}</h3>
                    <p>{{ meme[2] or 'No description' }}</p>
                    <p><strong>Author:</strong> {{ meme[4] }}</p>
                    <p class="stats">
                        <span>⬆️ {{ meme[5] }} votes</span>
                        {% if meme[6] > 0 %}
                        <span style="color: #ffaa00;"> | 🪙 {{ meme[6] }} RTC earned</span>
                        {% endif %}
                    </p>
                    <p class="status-{{ meme[7] }}"><strong>Status:</strong> {{ meme[7].upper() }}</p>
                    <div class="vote-buttons">
                        <button class="btn" onclick="vote('{{ meme[0] }}', 'up')">👍 Upvote</button>
                        <button class="btn" onclick="vote('{{ meme[0] }}', 'down')">👎 Downvote</button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        
        <script>
        function vote(memeId, voteType) {
            fetch('/vote', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({meme_id: memeId, vote_type: voteType})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Vote failed: ' + data.error);
                }
            });
        }
        </script>
    </body>
    </html>
    '''
    
    return render_template_string(template, memes=memes)

@app.route('/submit', methods=['GET', 'POST'])
def submit_meme():
    """Meme submission form"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        author = request.form.get('author')
        
        if 'meme_file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['meme_file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Generate unique filename
            file_ext = file.filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
            filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
            
            file.save(filepath)
            
            # Get file info
            file_size = os.path.getsize(filepath)
            file_hash = get_file_hash(filepath)
            meme_id = str(uuid.uuid4())
            
            # Save to database
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO memes (meme_id, title, description, filename, 
                                     author, image_hash, file_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (meme_id, title, description, unique_filename, 
                      author, file_hash, file_size))
                conn.commit()
            
            flash('Meme submitted successfully! Pending review.')
            return redirect(url_for('gallery'))
        else:
            flash('Invalid file type. Please upload PNG, JPG, or GIF.')
    
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Submit Meme - RustChain Gallery</title>
        <style>
            body { 
                font-family: 'Courier New', monospace; 
                background: #001100; 
                color: #00ff00; 
                margin: 0; 
                padding: 20px;
            }
            .form-container {
                max-width: 600px;
                margin: 0 auto;
                border: 2px solid #00ff00;
                padding: 30px;
                background: #002200;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                color: #00ffaa;
                font-weight: bold;
            }
            input[type="text"], input[type="file"], textarea {
                width: 100%;
                padding: 10px;
                background: #003300;
                border: 1px solid #00ff00;
                color: #00ff00;
                font-family: inherit;
                box-sizing: border-box;
            }
            textarea {
                height: 100px;
                resize: vertical;
            }
            .btn {
                background: #004400;
                border: 2px solid #00ff00;
                color: #00ff00;
                padding: 12px 24px;
                cursor: pointer;
                font-family: inherit;
                font-size: 16px;
                margin-right: 10px;
            }
            .btn:hover { background: #006600; }
            .back-link {
                color: #ffff00;
                text-decoration: none;
            }
            .rules {
                background: #330000;
                border: 1px solid #ff0000;
                padding: 15px;
                margin-bottom: 20px;
                color: #ff8888;
            }
            .flash-messages {
                margin-bottom: 20px;
            }
            .flash {
                padding: 10px;
                background: #440000;
                border: 1px solid #ff0000;
                color: #ffaaaa;
                margin-bottom: 10px;
            }
        </style>
    </head>
    <body>
        <div class="form-container">
            <h1>🚀 SUBMIT YOUR RETRO MEME 🚀</h1>
            
            <div class="rules">
                <h3>CONTEST RULES:</h3>
                <ul>
                    <li>Original memes only (you created it)</li>
                    <li>Must relate to retro computing + blockchain</li>
                    <li>PNG/JPG format, min 500px wide</li>
                    <li>Max 5 memes per person</li>
                    <li>Reward: 1 RTC per accepted, 3 RTC for top 3</li>
                </ul>
            </div>
            
            <div class="flash-messages">
                {% with messages = get_flashed_messages() %}
                    {% if messages %}
                        {% for message in messages %}
                        <div class="flash">{{ message }}</div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}
            </div>
            
            <form method="POST" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="title">Meme Title:</label>
                    <input type="text" id="title" name="title" required 
                           placeholder="e.g. PowerBook G4 Mining Squad">
                </div>
                
                <div class="form-group">
                    <label for="description">Description (optional):</label>
                    <textarea id="description" name="description" 
                              placeholder="Brief description of your meme..."></textarea>
                </div>
                
                <div class="form-group">
                    <label for="author">Your Name/Handle:</label>
                    <input type="text" id="author" name="author" required 
                           placeholder="RetroMiner2024">
                </div>
                
                <div class="form-group">
                    <label for="meme_file">Upload Meme File:</label>
                    <input type="file" id="meme_file" name="meme_file" 
                           accept="image/*" required>
                </div>
                
                <button type="submit" class="btn">SUBMIT MEME</button>
                <a href="/" class="back-link">Back to Gallery</a>
            </form>
        </div>
    </body>
    </html>
    '''
    
    return render_template_string(template)

@app.route('/vote', methods=['POST'])
def vote_meme():
    """Handle meme voting"""
    data = request.get_json()
    meme_id = data.get('meme_id')
    vote_type = data.get('vote_type')
    voter_ip = request.remote_addr
    
    if not meme_id or vote_type not in ['up', 'down']:
        return jsonify({'success': False, 'error': 'Invalid vote data'})
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Check if user already voted
        cursor.execute('''
            SELECT vote_type FROM meme_votes 
            WHERE meme_id = ? AND voter_ip = ?
        ''', (meme_id, voter_ip))
        existing_vote = cursor.fetchone()
        
        if existing_vote:
            if existing_vote[0] == vote_type:
                return jsonify({'success': False, 'error': 'Already voted'})
            
            # Update existing vote
            cursor.execute('''
                UPDATE meme_votes 
                SET vote_type = ?, created_at = CURRENT_TIMESTAMP
                WHERE meme_id = ? AND voter_ip = ?
            ''', (vote_type, meme_id, voter_ip))
            
            # Adjust vote count (remove old, add new)
            old_adjustment = 1 if existing_vote[0] == 'up' else -1
            new_adjustment = 1 if vote_type == 'up' else -1
            total_change = new_adjustment - old_adjustment
            
            cursor.execute('''
                UPDATE memes SET votes = votes + ? WHERE meme_id = ?
            ''', (total_change, meme_id))
        else:
            # New vote
            cursor.execute('''
                INSERT INTO meme_votes (meme_id, voter_ip, vote_type)
                VALUES (?, ?, ?)
            ''', (meme_id, voter_ip, vote_type))
            
            vote_change = 1 if vote_type == 'up' else -1
            cursor.execute('''
                UPDATE memes SET votes = votes + ? WHERE meme_id = ?
            ''', (vote_change, meme_id))
        
        conn.commit()
    
    return jsonify({'success': True})

@app.route('/admin')
def admin_panel():
    """Simple admin panel to approve memes and award RTC"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT meme_id, title, author, votes, rtc_earned, status, created_at
            FROM memes 
            ORDER BY created_at DESC
        ''')
        memes = cursor.fetchall()
    
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Panel - Meme Gallery</title>
        <style>
            body { font-family: monospace; background: #000; color: #0f0; padding: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #0f0; padding: 8px; text-align: left; }
            th { background: #003300; }
            .btn { background: #004400; border: 1px solid #0f0; color: #0f0; padding: 4px 8px; margin: 2px; }
            .status-approved { color: #0f0; }
            .status-pending { color: #ff0; }
            .status-rejected { color: #f00; }
        </style>
    </head>
    <body>
        <h1>ADMIN: Meme Management</h1>
        <table>
            <tr>
                <th>Title</th>
                <th>Author</th>
                <th>Votes</th>
                <th>RTC</th>
                <th>Status</th>
                <th>Date</th>
                <th>Actions</th>
            </tr>
            {% for meme in memes %}
            <tr>
                <td>{{ meme[1] }}</td>
                <td>{{ meme[2] }}</td>
                <td>{{ meme[3] }}</td>
                <td>{{ meme[4] }}</td>
                <td class="status-{{ meme[5] }}">{{ meme[5].upper() }}</td>
                <td>{{ meme[6] }}</td>
                <td>
                    <button class="btn" onclick="updateStatus('{{ meme[0] }}', 'approved')">Approve</button>
                    <button class="btn" onclick="awardRTC('{{ meme[0] }}', 1)">Award 1 RTC</button>
                    <button class="btn" onclick="awardRTC('{{ meme[0] }}', 3)">Award 3 RTC</button>
                </td>
            </tr>
            {% endfor %}
        </table>
        
        <script>
        function updateStatus(memeId, status) {
            fetch('/admin/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({meme_id: memeId, status: status})
            }).then(() => location.reload());
        }
        
        function awardRTC(memeId, amount) {
            fetch('/admin/award', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({meme_id: memeId, rtc_amount: amount})
            }).then(() => location.reload());
        }
        </script>
    </body>
    </html>
    '''
    
    return render_template_string(template, memes=memes)

@app.route('/admin/update', methods=['POST'])
def admin_update_status():
    """Update meme status"""
    data = request.get_json()
    meme_id = data.get('meme_id')
    status = data.get('status')
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE memes SET status = ? WHERE meme_id = ?', 
                      (status, meme_id))
        conn.commit()
    
    return jsonify({'success': True})

@app.route('/admin/award', methods=['POST'])
def admin_award_rtc():
    """Award RTC to meme"""
    data = request.get_json()
    meme_id = data.get('meme_id')
    rtc_amount = data.get('rtc_amount')
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE memes 
            SET rtc_earned = rtc_earned + ?, status = 'approved'
            WHERE meme_id = ?
        ''', (rtc_amount, meme_id))
        conn.commit()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5003)