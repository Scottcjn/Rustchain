// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, render_template_string, redirect, url_for, flash, jsonify
import sqlite3
import os
import datetime
import re

app = Flask(__name__)
app.secret_key = 'rustchain_grandma_bounty_secret'

DB_PATH = 'video_submissions.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS video_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                video_url TEXT NOT NULL,
                video_duration INTEGER,
                has_grandma BOOLEAN DEFAULT FALSE,
                submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                validation_status TEXT DEFAULT 'pending',
                validator_notes TEXT,
                rtc_reward REAL DEFAULT 5.0
            )
        ''')

def validate_video_url(url):
    youtube_pattern = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+'
    bottube_pattern = r'(https?://)?(www\.)?bottube\.com/.+'
    return bool(re.match(youtube_pattern, url) or re.match(bottube_pattern, url))

@app.route('/')
def index():
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Grandma Explanation Bounty</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; background: white; padding: 30px; border-radius: 8px; }
            .bounty-header { background: #2c3e50; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
            .requirements { background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 15px 0; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, textarea, select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #e74c3c; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #c0392b; }
            .submissions { margin-top: 30px; }
            .submission-item { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #e74c3c; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="bounty-header">
                <h1>🎥 Explain RustChain to Your Grandma</h1>
                <h2>Reward: 5 RTC (+3 RTC if grandma is in the video!)</h2>
            </div>
            
            <div class="requirements">
                <h3>Requirements:</h3>
                <ul>
                    <li><strong>Under 60 seconds</strong></li>
                    <li>Explain what RustChain is, what mining means, why old computers get bonus rewards</li>
                    <li><strong>No jargon</strong> - if you say "attestation" or "epoch settlement," you lose</li>
                    <li>Upload to BoTTube (preferred) or YouTube/social media</li>
                </ul>
            </div>

            {% with messages = get_flashed_messages() %}
                {% if messages %}
                    {% for message in messages %}
                        <div style="background: #2ecc71; color: white; padding: 10px; border-radius: 4px; margin: 10px 0;">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <form method="POST" action="/submit">
                <div class="form-group">
                    <label>Username:</label>
                    <input type="text" name="username" required>
                </div>
                
                <div class="form-group">
                    <label>RustChain Wallet Address:</label>
                    <input type="text" name="wallet_address" required>
                </div>
                
                <div class="form-group">
                    <label>Video URL (BoTTube/YouTube):</label>
                    <input type="url" name="video_url" required>
                </div>
                
                <div class="form-group">
                    <label>Video Duration (seconds):</label>
                    <input type="number" name="video_duration" max="60" required>
                </div>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" name="has_grandma" style="width: auto; margin-right: 10px;">
                        My actual grandma/grandpa is in this video (+3 RTC bonus!)
                    </label>
                </div>
                
                <button type="submit">Submit Video for Bounty</button>
            </form>

            <div class="submissions">
                <h3>Recent Submissions</h3>
                {% for submission in submissions %}
                <div class="submission-item">
                    <strong>{{ submission[1] }}</strong> 
                    {% if submission[5] %}<span style="color: #e74c3c;">👵 GRANDMA BONUS!</span>{% endif %}
                    <br>
                    <small>{{ submission[4] }}s video | {{ submission[6] }} | Status: {{ submission[7] }}</small>
                    <br>
                    <a href="{{ submission[3] }}" target="_blank">{{ submission[3] }}</a>
                    <br>
                    <strong>Potential Reward: {{ submission[9] }} RTC</strong>
                </div>
                {% endfor %}
            </div>
        </div>
    </body>
    </html>
    '''
    
    with sqlite3.connect(DB_PATH) as conn:
        submissions = conn.execute(
            'SELECT * FROM video_submissions ORDER BY submission_date DESC LIMIT 10'
        ).fetchall()
    
    return render_template_string(template, submissions=submissions)

@app.route('/submit', methods=['POST'])
def submit_video():
    username = request.form.get('username', '').strip()
    wallet_address = request.form.get('wallet_address', '').strip()
    video_url = request.form.get('video_url', '').strip()
    video_duration = int(request.form.get('video_duration', 0))
    has_grandma = bool(request.form.get('has_grandma'))
    
    if not all([username, wallet_address, video_url]):
        flash('All fields are required!')
        return redirect(url_for('index'))
    
    if video_duration > 60:
        flash('Video must be under 60 seconds!')
        return redirect(url_for('index'))
    
    if not validate_video_url(video_url):
        flash('Please provide a valid BoTTube or YouTube URL')
        return redirect(url_for('index'))
    
    rtc_reward = 5.0
    if has_grandma:
        rtc_reward += 3.0
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO video_submissions 
            (username, wallet_address, video_url, video_duration, has_grandma, rtc_reward)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, wallet_address, video_url, video_duration, has_grandma, rtc_reward))
    
    flash(f'Video submitted successfully! Potential reward: {rtc_reward} RTC')
    return redirect(url_for('index'))

@app.route('/validate/<int:submission_id>', methods=['GET', 'POST'])
def validate_submission(submission_id):
    if request.method == 'POST':
        status = request.form.get('status')
        notes = request.form.get('notes', '')
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                UPDATE video_submissions 
                SET validation_status = ?, validator_notes = ?
                WHERE id = ?
            ''', (status, notes, submission_id))
        
        return jsonify({'success': True})
    
    with sqlite3.connect(DB_PATH) as conn:
        submission = conn.execute(
            'SELECT * FROM video_submissions WHERE id = ?', 
            (submission_id,)
        ).fetchone()
    
    if not submission:
        return "Submission not found", 404
    
    validation_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Validate Submission - RustChain Bounty</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 600px; }
            .submission-details { background: #f8f9fa; padding: 20px; border-radius: 5px; }
            .form-group { margin: 15px 0; }
            button { padding: 10px 15px; margin: 5px; border: none; border-radius: 4px; cursor: pointer; }
            .approve { background: #27ae60; color: white; }
            .reject { background: #e74c3c; color: white; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Validate Video Submission</h2>
            <div class="submission-details">
                <p><strong>Username:</strong> {{ submission[1] }}</p>
                <p><strong>Wallet:</strong> {{ submission[2] }}</p>
                <p><strong>Video URL:</strong> <a href="{{ submission[3] }}" target="_blank">{{ submission[3] }}</a></p>
                <p><strong>Duration:</strong> {{ submission[4] }} seconds</p>
                <p><strong>Has Grandma:</strong> {{ "Yes" if submission[5] else "No" }}</p>
                <p><strong>Potential Reward:</strong> {{ submission[9] }} RTC</p>
                <p><strong>Submitted:</strong> {{ submission[6] }}</p>
            </div>
            
            <form method="POST">
                <div class="form-group">
                    <label>Validation Status:</label>
                    <select name="status" required>
                        <option value="pending">Pending</option>
                        <option value="approved">Approved</option>
                        <option value="rejected">Rejected</option>
                        <option value="needs_review">Needs Review</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Validator Notes:</label>
                    <textarea name="notes" rows="4" placeholder="Any notes about this submission..."></textarea>
                </div>
                
                <button type="submit" class="approve">Update Status</button>
            </form>
        </div>
    </body>
    </html>
    '''
    
    return render_template_string(validation_template, submission=submission)

@app.route('/api/submissions')
def api_submissions():
    with sqlite3.connect(DB_PATH) as conn:
        submissions = conn.execute(
            'SELECT * FROM video_submissions ORDER BY submission_date DESC'
        ).fetchall()
    
    result = []
    for sub in submissions:
        result.append({
            'id': sub[0],
            'username': sub[1],
            'wallet_address': sub[2],
            'video_url': sub[3],
            'duration': sub[4],
            'has_grandma': sub[5],
            'submission_date': sub[6],
            'status': sub[7],
            'notes': sub[8],
            'rtc_reward': sub[9]
        })
    
    return jsonify(result)

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        init_db()
    app.run(debug=True, port=5002)