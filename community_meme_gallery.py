// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import os
import hashlib
from flask import Flask, request, render_template_string, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import uuid

app = Flask(__name__)
app.secret_key = 'rustchain_meme_gallery_2026'

UPLOAD_FOLDER = 'uploads/memes'
DB_PATH = 'meme_contest.db'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS memes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                username TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_hash TEXT UNIQUE NOT NULL,
                description TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved BOOLEAN DEFAULT FALSE,
                votes INTEGER DEFAULT 0,
                rtc_awarded INTEGER DEFAULT 0,
                admin_notes TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meme_id INTEGER NOT NULL,
                voter_ip TEXT NOT NULL,
                voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meme_id) REFERENCES memes (id),
                UNIQUE(meme_id, voter_ip)
            )
        ''')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_hash(file_path):
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

@app.route('/')
def gallery():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        memes = conn.execute('''
            SELECT * FROM memes 
            WHERE approved = 1 
            ORDER BY votes DESC, submitted_at DESC
        ''').fetchall()
    
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Retro Computing Meme Contest</title>
        <style>
            body { font-family: monospace; max-width: 1200px; margin: 0 auto; padding: 20px; background: #0a0a0a; color: #00ff00; }
            .header { text-align: center; border: 2px solid #00ff00; padding: 20px; margin-bottom: 30px; }
            .meme-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 30px; }
            .meme-card { border: 1px solid #004400; padding: 15px; background: #1a1a1a; }
            .meme-img { max-width: 100%; height: auto; border: 1px solid #333; }
            .meme-meta { margin-top: 10px; font-size: 12px; color: #888; }
            .vote-btn { background: #004400; color: #00ff00; border: none; padding: 5px 15px; cursor: pointer; margin-top: 10px; }
            .vote-btn:hover { background: #006600; }
            .submit-link { display: inline-block; background: #440000; color: #ff4444; padding: 10px 20px; text-decoration: none; border: 1px solid #ff4444; }
            .submit-link:hover { background: #660000; }
            .rtc-badge { background: #ffaa00; color: #000; padding: 2px 8px; border-radius: 3px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🖥️ RUSTCHAIN RETRO MEME CONTEST 🖥️</h1>
            <p>Mining blockchain on vintage hardware since 2026</p>
            <a href="{{ url_for('submit') }}" class="submit-link">SUBMIT YOUR MEME</a>
        </div>
        
        <div class="meme-grid">
            {% for meme in memes %}
            <div class="meme-card">
                <h3>{{ meme.title }}</h3>
                <img src="{{ url_for('uploaded_file', filename=meme.filename) }}" class="meme-img" alt="{{ meme.title }}">
                <div class="meme-meta">
                    <p><strong>By:</strong> {{ meme.username }}</p>
                    {% if meme.description %}
                    <p><strong>Description:</strong> {{ meme.description }}</p>
                    {% endif %}
                    <p><strong>Votes:</strong> {{ meme.votes }}</p>
                    {% if meme.rtc_awarded > 0 %}
                    <span class="rtc-badge">{{ meme.rtc_awarded }} RTC AWARDED</span>
                    {% endif %}
                    <form method="POST" action="{{ url_for('vote', meme_id=meme.id) }}" style="display: inline;">
                        <button type="submit" class="vote-btn">VOTE FOR THIS MEME</button>
                    </form>
                </div>
            </div>
            {% endfor %}
        </div>
        
        {% if not memes %}
        <div style="text-align: center; margin-top: 100px;">
            <h2>No approved memes yet!</h2>
            <p>Be the first to submit a dank retro computing meme.</p>
        </div>
        {% endif %}
    </body>
    </html>
    '''
    return render_template_string(template, memes=memes)

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        username = request.form.get('username', '').strip()
        description = request.form.get('description', '').strip()
        file = request.files.get('file')
        
        if not title or not username or not file:
            flash('Title, username, and image file are required!')
            return redirect(url_for('submit'))
        
        if not allowed_file(file.filename):
            flash('Invalid file type! Use PNG or JPG only.')
            return redirect(url_for('submit'))
        
        # Check submission limit per user
        with sqlite3.connect(DB_PATH) as conn:
            user_count = conn.execute('SELECT COUNT(*) FROM memes WHERE username = ?', (username,)).fetchone()[0]
            if user_count >= 5:
                flash('Maximum 5 memes per person allowed!')
                return redirect(url_for('submit'))
        
        # Save file with unique name
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(file_path)
        
        # Check for duplicate content
        file_hash = get_file_hash(file_path)
        
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO memes (title, username, filename, file_hash, description)
                    VALUES (?, ?, ?, ?, ?)
                ''', (title, username, unique_filename, file_hash, description))
            
            flash('Meme submitted! Awaiting admin approval.')
            return redirect(url_for('gallery'))
            
        except sqlite3.IntegrityError:
            os.remove(file_path)
            flash('This image has already been submitted!')
            return redirect(url_for('submit'))
    
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Submit Meme - RustChain Contest</title>
        <style>
            body { font-family: monospace; max-width: 600px; margin: 0 auto; padding: 20px; background: #0a0a0a; color: #00ff00; }
            .form-container { border: 2px solid #00ff00; padding: 30px; background: #1a1a1a; }
            input, textarea, select { width: 100%; padding: 10px; background: #2a2a2a; color: #00ff00; border: 1px solid #004400; margin: 5px 0 15px 0; }
            .submit-btn { background: #004400; color: #00ff00; border: none; padding: 15px 30px; cursor: pointer; font-size: 16px; }
            .submit-btn:hover { background: #006600; }
            .rules { background: #440000; padding: 15px; margin-bottom: 20px; border: 1px solid #ff4444; color: #ffaaaa; }
            .back-link { color: #00ff00; text-decoration: none; }
            .back-link:hover { color: #ffffff; }
            .flash { background: #666600; color: #ffffff; padding: 10px; margin-bottom: 15px; border: 1px solid #ffff00; }
        </style>
    </head>
    <body>
        <h1><a href="{{ url_for('gallery') }}" class="back-link">← Back to Gallery</a></h1>
        <h2>Submit Your Retro Computing Meme</h2>
        
        <div class="rules">
            <h3>Contest Rules:</h3>
            <ul>
                <li>Original memes only (you made it)</li>
                <li>Must relate to mining crypto on vintage hardware, RustChain PoA, PowerPC/G4/G5/POWER8, retro Macs, 486s, etc.</li>
                <li>PNG or JPG format, at least 500px wide</li>
                <li>Max 5 memes per person</li>
                <li>Rewards: 1 RTC per accepted meme, 3 RTC for top 3</li>
            </ul>
        </div>
        
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="flash">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="form-container">
            <form method="POST" enctype="multipart/form-data">
                <label>Meme Title:</label>
                <input type="text" name="title" required maxlength="200" placeholder="PowerBook G4 Mining in 2026">
                
                <label>Your Username:</label>
                <input type="text" name="username" required maxlength="50" placeholder="retroMiner42">
                
                <label>Meme Image:</label>
                <input type="file" name="file" accept=".png,.jpg,.jpeg" required>
                
                <label>Description (optional):</label>
                <textarea name="description" rows="3" maxlength="500" placeholder="When you're mining RTC on a PowerBook G4..."></textarea>
                
                <button type="submit" class="submit-btn">SUBMIT MEME FOR REVIEW</button>
            </form>
        </div>
    </body>
    </html>
    '''
    return render_template_string(template)

@app.route('/vote/<int:meme_id>', methods=['POST'])
def vote(meme_id):
    voter_ip = request.remote_addr
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('INSERT INTO votes (meme_id, voter_ip) VALUES (?, ?)', (meme_id, voter_ip))
            conn.execute('UPDATE memes SET votes = votes + 1 WHERE id = ?', (meme_id,))
        flash('Vote counted!')
    except sqlite3.IntegrityError:
        flash('You already voted for this meme!')
    
    return redirect(url_for('gallery'))

@app.route('/admin')
def admin():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        pending = conn.execute('SELECT * FROM memes WHERE approved = 0 ORDER BY submitted_at DESC').fetchall()
        approved = conn.execute('SELECT * FROM memes WHERE approved = 1 ORDER BY votes DESC, submitted_at DESC').fetchall()
    
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin - Meme Contest</title>
        <style>
            body { font-family: monospace; max-width: 1200px; margin: 0 auto; padding: 20px; background: #0a0a0a; color: #00ff00; }
            .admin-section { border: 1px solid #444; padding: 20px; margin: 20px 0; background: #1a1a1a; }
            .meme-item { border-bottom: 1px solid #333; padding: 15px 0; }
            .admin-img { max-width: 300px; height: auto; }
            .approve-btn { background: #004400; color: #00ff00; border: none; padding: 5px 15px; margin: 5px; cursor: pointer; }
            .reject-btn { background: #440000; color: #ff4444; border: none; padding: 5px 15px; margin: 5px; cursor: pointer; }
            .rtc-input { width: 60px; background: #2a2a2a; color: #ffaa00; border: 1px solid #ffaa00; padding: 3px; }
            .back-link { color: #00ff00; text-decoration: none; }
        </style>
    </head>
    <body>
        <h1><a href="{{ url_for('gallery') }}" class="back-link">← Back to Gallery</a></h1>
        <h1>Admin Panel - Meme Contest</h1>
        
        <div class="admin-section">
            <h2>Pending Approval ({{ pending|length }})</h2>
            {% for meme in pending %}
            <div class="meme-item">
                <h3>{{ meme.title }} by {{ meme.username }}</h3>
                <img src="{{ url_for('uploaded_file', filename=meme.filename) }}" class="admin-img">
                <p><strong>Description:</strong> {{ meme.description or 'None' }}</p>
                <p><strong>Submitted:</strong> {{ meme.submitted_at }}</p>
                
                <form method="POST" action="{{ url_for('admin_action') }}" style="display: inline;">
                    <input type="hidden" name="meme_id" value="{{ meme.id }}">
                    <input type="hidden" name="action" value="approve">
                    RTC Award: <input type="number" name="rtc_award" value="1" min="0" max="10" class="rtc-input">
                    <button type="submit" class="approve-btn">APPROVE</button>
                </form>
                
                <form method="POST" action="{{ url_for('admin_action') }}" style="display: inline;">
                    <input type="hidden" name="meme_id" value="{{ meme.id }}">
                    <input type="hidden" name="action" value="reject">
                    <button type="submit" class="reject-btn">REJECT</button>
                </form>
            </div>
            {% endfor %}
        </div>
        
        <div class="admin-section">
            <h2>Approved Memes ({{ approved|length }})</h2>
            {% for meme in approved %}
            <div class="meme-item">
                <h3>{{ meme.title }} by {{ meme.username }}</h3>
                <p><strong>Votes:</strong> {{ meme.votes }} | <strong>RTC Awarded:</strong> {{ meme.rtc_awarded }}</p>
                
                <form method="POST" action="{{ url_for('admin_action') }}" style="display: inline;">
                    <input type="hidden" name="meme_id" value="{{ meme.id }}">
                    <input type="hidden" name="action" value="update_rtc">
                    Update RTC: <input type="number" name="rtc_award" value="{{ meme.rtc_awarded }}" min="0" max="10" class="rtc-input">
                    <button type="submit" class="approve-btn">UPDATE</button>
                </form>
            </div>
            {% endfor %}
        </div>
    </body>
    </html>
    '''
    return render_template_string(template, pending=pending, approved=approved)

@app.route('/admin/action', methods=['POST'])
def admin_action():
    meme_id = request.form.get('meme_id')
    action = request.form.get('action')
    rtc_award = int(request.form.get('rtc_award', 0))
    
    with sqlite3.connect(DB_PATH) as conn:
        if action == 'approve':
            conn.execute('UPDATE memes SET approved = 1, rtc_awarded = ? WHERE id = ?', (rtc_award, meme_id))
        elif action == 'reject':
            meme = conn.execute('SELECT filename FROM memes WHERE id = ?', (meme_id,)).fetchone()
            if meme:
                file_path = os.path.join(UPLOAD_FOLDER, meme[0])
                if os.path.exists(file_path):
                    os.remove(file_path)
            conn.execute('DELETE FROM memes WHERE id = ?', (meme_id,))
        elif action == 'update_rtc':
            conn.execute('UPDATE memes SET rtc_awarded = ? WHERE id = ?', (rtc_award, meme_id))
    
    return redirect(url_for('admin'))

@app.route('/uploads/memes/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5002)