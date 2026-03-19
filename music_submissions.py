// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, request, render_template_string, redirect, url_for, send_from_directory
import sqlite3
import os
import hashlib
from datetime import datetime
import mimetypes

app = Flask(__name__)

DB_PATH = 'music_submissions.db'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'ogg', 'flac', 'txt', 'md'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                genre TEXT,
                description TEXT,
                audio_file TEXT,
                lyrics_file TEXT,
                file_hash TEXT,
                rtc_address TEXT,
                submitted_at TEXT,
                approved INTEGER DEFAULT 0
            )
        ''')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_hash(filepath):
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]

@app.route('/')
def index():
    with sqlite3.connect(DB_PATH) as conn:
        submissions = conn.execute('''
            SELECT id, title, artist_name, genre, description, audio_file, 
                   lyrics_file, submitted_at, approved 
            FROM submissions 
            ORDER BY submitted_at DESC
        ''').fetchall()
    
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>RustChain Music Submissions</title>
    <style>
        body { font-family: 'Courier New', monospace; background: #1a1a1a; color: #00ff00; margin: 0; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .header { text-align: center; border-bottom: 2px solid #00ff00; margin-bottom: 30px; padding-bottom: 20px; }
        .bounty { background: #2d2d2d; padding: 15px; border-left: 4px solid #ff6600; margin-bottom: 20px; }
        .submit-form { background: #2d2d2d; padding: 20px; border-radius: 5px; margin-bottom: 30px; }
        .submit-form input, .submit-form textarea, .submit-form select { 
            width: 100%; padding: 8px; margin: 5px 0; background: #1a1a1a; 
            color: #00ff00; border: 1px solid #00ff00; 
        }
        .submit-form button { 
            background: #00ff00; color: #1a1a1a; padding: 10px 20px; 
            border: none; cursor: pointer; font-weight: bold; 
        }
        .submissions { margin-top: 30px; }
        .submission { background: #2d2d2d; margin: 15px 0; padding: 15px; border-radius: 5px; }
        .submission.approved { border-left: 4px solid #00ff00; }
        .submission.pending { border-left: 4px solid #ffaa00; }
        .file-link { color: #66ccff; text-decoration: none; }
        .file-link:hover { text-decoration: underline; }
        .meta { font-size: 0.9em; color: #888; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎵 RustChain Music Submissions 🎵</h1>
            <p>Sea shanties welcome! Mining songs encouraged!</p>
        </div>
        
        <div class="bounty">
            <h3>💰 CREATIVE BOUNTY: 15 RTC</h3>
            <p><strong>Write & Record a RustChain Theme Song</strong></p>
            <ul>
                <li>Original composition (lyrics + music)</li>
                <li>30 seconds minimum, 3 minutes max</li>
                <li>Must reference: RustChain, RTC, Proof of Antiquity, vintage hardware, or 1 CPU = 1 Vote</li>
                <li>Upload audio file + lyrics text file</li>
            </ul>
        </div>

        <form class="submit-form" method="POST" enctype="multipart/form-data">
            <h3>Submit Your RustChain Song</h3>
            <input type="text" name="title" placeholder="Song Title" required>
            <input type="text" name="artist_name" placeholder="Artist/Band Name" required>
            <select name="genre">
                <option value="">Select Genre</option>
                <option value="Sea Shanty">Sea Shanty</option>
                <option value="Folk">Folk/Acoustic</option>
                <option value="Chiptune">Chiptune/8-bit</option>
                <option value="Lo-fi">Lo-fi Hip Hop</option>
                <option value="Country">Country</option>
                <option value="Rock">Rock</option>
                <option value="Electronic">Electronic</option>
                <option value="Other">Other</option>
            </select>
            <textarea name="description" placeholder="Description (optional)" rows="3"></textarea>
            <label>Audio File (MP3, WAV, M4A, OGG, FLAC - max 50MB):</label>
            <input type="file" name="audio_file" accept=".mp3,.wav,.m4a,.ogg,.flac" required>
            <label>Lyrics File (TXT or MD):</label>
            <input type="file" name="lyrics_file" accept=".txt,.md">
            <input type="text" name="rtc_address" placeholder="RTC Address (for bounty payment)">
            <button type="submit">Submit Song</button>
        </form>

        <div class="submissions">
            <h3>Submitted Songs ({{ submissions|length }})</h3>
            {% for sub in submissions %}
            <div class="submission {{ 'approved' if sub[8] else 'pending' }}">
                <h4>{{ sub[1] }} by {{ sub[2] }}</h4>
                {% if sub[3] %}<p><strong>Genre:</strong> {{ sub[3] }}</p>{% endif %}
                {% if sub[4] %}<p>{{ sub[4] }}</p>{% endif %}
                <p>
                    {% if sub[5] %}
                    <a href="{{ url_for('download_file', filename=sub[5]) }}" class="file-link">🎵 Audio</a>
                    {% endif %}
                    {% if sub[6] %}
                    <a href="{{ url_for('download_file', filename=sub[6]) }}" class="file-link">📄 Lyrics</a>
                    {% endif %}
                </p>
                <p class="meta">
                    Submitted: {{ sub[7] }} | 
                    Status: {{ 'Approved ✓' if sub[8] else 'Under Review' }}
                </p>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
    ''', submissions=submissions)

@app.route('/', methods=['POST'])
def submit_song():
    title = request.form.get('title', '').strip()
    artist_name = request.form.get('artist_name', '').strip()
    genre = request.form.get('genre', '').strip()
    description = request.form.get('description', '').strip()
    rtc_address = request.form.get('rtc_address', '').strip()
    
    if not title or not artist_name:
        return redirect(url_for('index'))
    
    audio_file = request.files.get('audio_file')
    lyrics_file = request.files.get('lyrics_file')
    
    if not audio_file or not allowed_file(audio_file.filename):
        return redirect(url_for('index'))
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    audio_filename = None
    lyrics_filename = None
    
    if audio_file:
        audio_ext = audio_file.filename.rsplit('.', 1)[1].lower()
        audio_filename = f"{timestamp}_{hashlib.md5(title.encode()).hexdigest()[:8]}_audio.{audio_ext}"
        audio_path = os.path.join(UPLOAD_FOLDER, audio_filename)
        audio_file.save(audio_path)
        
        if os.path.getsize(audio_path) > MAX_FILE_SIZE:
            os.remove(audio_path)
            return redirect(url_for('index'))
    
    if lyrics_file and allowed_file(lyrics_file.filename):
        lyrics_ext = lyrics_file.filename.rsplit('.', 1)[1].lower()
        lyrics_filename = f"{timestamp}_{hashlib.md5(title.encode()).hexdigest()[:8]}_lyrics.{lyrics_ext}"
        lyrics_path = os.path.join(UPLOAD_FOLDER, lyrics_filename)
        lyrics_file.save(lyrics_path)
    
    file_hash = get_file_hash(os.path.join(UPLOAD_FOLDER, audio_filename)) if audio_filename else None
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO submissions 
            (title, artist_name, genre, description, audio_file, lyrics_file, 
             file_hash, rtc_address, submitted_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, artist_name, genre, description, audio_filename, lyrics_filename,
              file_hash, rtc_address, datetime.now().isoformat()))
    
    return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/admin/approve/<int:submission_id>')
def approve_submission(submission_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('UPDATE submissions SET approved = 1 WHERE id = ?', (submission_id,))
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5003)