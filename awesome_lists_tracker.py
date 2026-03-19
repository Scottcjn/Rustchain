// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import uuid
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, url_for, flash, jsonify

app = Flask(__name__)
app.secret_key = 'awesome-lists-tracker-key-2024'
DB_PATH = 'awesome_lists.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                project_url TEXT NOT NULL,
                target_list TEXT NOT NULL,
                target_url TEXT NOT NULL,
                submission_type TEXT NOT NULL,
                pr_url TEXT,
                evidence_url TEXT,
                submitter_name TEXT NOT NULL,
                submitter_contact TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_at TIMESTAMP,
                notes TEXT
            )
        ''')

FLAGSHIP_PROJECTS = {
    'RustChain': 'https://rustchain.org',
    'BoTTube': 'https://bottube.ai',
    'Beacon Atlas': 'https://rustchain.org/beacon/',
    'Grazer': 'https://github.com/Scottcjn/grazer-skill',
    'ClawRTC': 'https://clawhub.ai/packages/clawrtc'
}

SUBMISSION_TYPES = [
    'awesome-list',
    'curated-repo',
    'public-directory',
    'tool-registry',
    'other'
]

@app.route('/')
def index():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        submissions = conn.execute('''
            SELECT * FROM submissions 
            ORDER BY submitted_at DESC 
            LIMIT 20
        ''').fetchall()
    
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Awesome Lists Tracker</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: #2c3e50; color: white; padding: 20px; margin: -20px -20px 20px -20px; }
        .stats { display: flex; gap: 20px; margin: 20px 0; }
        .stat { background: #ecf0f1; padding: 15px; border-radius: 5px; flex: 1; text-align: center; }
        .actions { margin: 20px 0; }
        .btn { background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-right: 10px; }
        .btn:hover { background: #2980b9; }
        .btn.success { background: #27ae60; }
        .btn.danger { background: #e74c3c; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f2f2f2; }
        .status-pending { color: #f39c12; }
        .status-approved { color: #27ae60; }
        .status-rejected { color: #e74c3c; }
        .status-verified { color: #16a085; }
        .flash { padding: 10px; margin: 10px 0; border-radius: 5px; }
        .flash.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .flash.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌟 Awesome Lists Tracker</h1>
        <p>Track flagship project submissions to awesome lists and public directories</p>
    </div>
    
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="flash {{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <div class="stats">
        <div class="stat">
            <h3>{{ stats.total }}</h3>
            <p>Total Submissions</p>
        </div>
        <div class="stat">
            <h3>{{ stats.pending }}</h3>
            <p>Pending Review</p>
        </div>
        <div class="stat">
            <h3>{{ stats.verified }}</h3>
            <p>Verified & Paid</p>
        </div>
        <div class="stat">
            <h3>{{ stats.pool_remaining }}</h3>
            <p>RTC Remaining</p>
        </div>
    </div>
    
    <div class="actions">
        <a href="{{ url_for('submit') }}" class="btn">Submit New Entry</a>
        <a href="{{ url_for('dashboard') }}" class="btn">Admin Dashboard</a>
        <a href="{{ url_for('api_submissions') }}" class="btn">JSON API</a>
    </div>
    
    <h2>Recent Submissions</h2>
    <table>
        <tr>
            <th>Project</th>
            <th>Target</th>
            <th>Type</th>
            <th>Submitter</th>
            <th>Status</th>
            <th>Submitted</th>
            <th>Evidence</th>
        </tr>
        {% for sub in submissions %}
        <tr>
            <td><a href="{{ sub.project_url }}" target="_blank">{{ sub.project_name }}</a></td>
            <td><a href="{{ sub.target_url }}" target="_blank">{{ sub.target_list }}</a></td>
            <td>{{ sub.submission_type }}</td>
            <td>{{ sub.submitter_name }}</td>
            <td class="status-{{ sub.status }}">{{ sub.status.title() }}</td>
            <td>{{ sub.submitted_at[:10] }}</td>
            <td>
                {% if sub.pr_url %}
                    <a href="{{ sub.pr_url }}" target="_blank">PR</a>
                {% endif %}
                {% if sub.evidence_url %}
                    <a href="{{ sub.evidence_url }}" target="_blank">Evidence</a>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
    ''', submissions=submissions, stats=get_stats())

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        submission_id = str(uuid.uuid4())[:8]
        
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO submissions (
                        id, project_name, project_url, target_list, target_url,
                        submission_type, pr_url, evidence_url, submitter_name,
                        submitter_contact, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    submission_id,
                    request.form['project_name'],
                    request.form['project_url'],
                    request.form['target_list'],
                    request.form['target_url'],
                    request.form['submission_type'],
                    request.form.get('pr_url'),
                    request.form.get('evidence_url'),
                    request.form['submitter_name'],
                    request.form['submitter_contact'],
                    request.form.get('notes')
                ))
            
            flash(f'Submission {submission_id} created successfully!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
    
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Submit to Awesome Lists</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .form-group { margin: 15px 0; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, select, textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        textarea { height: 100px; }
        .btn { background: #3498db; color: white; padding: 12px 20px; border: none; border-radius: 5px; cursor: pointer; }
        .btn:hover { background: #2980b9; }
        .back-link { color: #3498db; text-decoration: none; }
        .flash { padding: 10px; margin: 10px 0; border-radius: 5px; }
        .flash.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .help-text { font-size: 12px; color: #666; margin-top: 5px; }
        .flagship-note { background: #e8f4fd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #3498db; }
    </style>
</head>
<body>
    <a href="{{ url_for('index') }}" class="back-link">← Back to Tracker</a>
    
    <h1>Submit Awesome List Entry</h1>
    
    <div class="flagship-note">
        <h3>Bounty: 5 RTC per accepted submission</h3>
        <p>Max 2 claims per person. Use only flagship projects listed below.</p>
    </div>
    
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="flash {{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <form method="POST">
        <div class="form-group">
            <label>Flagship Project *</label>
            <select name="project_name" required onchange="updateProjectUrl()">
                <option value="">Select a flagship project...</option>
                {% for name, url in projects.items() %}
                <option value="{{ name }}" data-url="{{ url }}">{{ name }}</option>
                {% endfor %}
            </select>
            <div class="help-text">Choose from pre-approved flagship projects only</div>
        </div>
        
        <div class="form-group">
            <label>Project URL *</label>
            <input type="url" name="project_url" id="project_url" required readonly>
            <div class="help-text">Auto-filled based on selected project</div>
        </div>
        
        <div class="form-group">
            <label>Target List/Directory Name *</label>
            <input type="text" name="target_list" required placeholder="awesome-rust, public-apis, etc.">
            <div class="help-text">Name of the awesome list or directory</div>
        </div>
        
        <div class="form-group">
            <label>Target List URL *</label>
            <input type="url" name="target_url" required placeholder="https://github.com/rust-unofficial/awesome-rust">
            <div class="help-text">Full URL to the list or directory</div>
        </div>
        
        <div class="form-group">
            <label>Submission Type *</label>
            <select name="submission_type" required>
                <option value="">Select type...</option>
                <option value="awesome-list">Awesome List (GitHub)</option>
                <option value="curated-repo">Curated Repository</option>
                <option value="public-directory">Public Directory</option>
                <option value="tool-registry">Tool Registry</option>
                <option value="other">Other</option>
            </select>
        </div>
        
        <div class="form-group">
            <label>Pull Request URL</label>
            <input type="url" name="pr_url" placeholder="https://github.com/owner/repo/pull/123">
            <div class="help-text">Link to your PR (if applicable)</div>
        </div>
        
        <div class="form-group">
            <label>Evidence URL</label>
            <input type="url" name="evidence_url" placeholder="https://example.com/listing">
            <div class="help-text">Direct link to live listing or other proof</div>
        </div>
        
        <div class="form-group">
            <label>Your Name *</label>
            <input type="text" name="submitter_name" required>
        </div>
        
        <div class="form-group">
            <label>Contact Info *</label>
            <input type="text" name="submitter_contact" required placeholder="GitHub username, email, etc.">
            <div class="help-text">How we can reach you for verification</div>
        </div>
        
        <div class="form-group">
            <label>Additional Notes</label>
            <textarea name="notes" placeholder="Any additional information about your submission..."></textarea>
        </div>
        
        <button type="submit" class="btn">Submit Entry</button>
    </form>
    
    <script>
        function updateProjectUrl() {
            const select = document.querySelector('select[name="project_name"]');
            const urlInput = document.getElementById('project_url');
            const selectedOption = select.options[select.selectedIndex];
            
            if (selectedOption.dataset.url) {
                urlInput.value = selectedOption.dataset.url;
            } else {
                urlInput.value = '';
            }
        }
    </script>
</body>
</html>
    ''', projects=FLAGSHIP_PROJECTS)

@app.route('/dashboard')
def dashboard():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        submissions = conn.execute('''
            SELECT * FROM submissions 
            ORDER BY submitted_at DESC
        ''').fetchall()
    
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1400px; margin: 0 auto; padding: 20px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 12px; }
        th { background: #f2f2f2; }
        .actions { white-space: nowrap; }
        .btn { padding: 4px 8px; text-decoration: none; border-radius: 3px; font-size: 11px; margin: 0 2px; }
        .btn.success { background: #27ae60; color: white; }
        .btn.danger { background: #e74c3c; color: white; }
        .btn.info { background: #3498db; color: white; }
        .status-pending { background: #fff3cd; }
        .status-approved { background: #d4edda; }
        .status-rejected { background: #f8d7da; }
        .status-verified { background: #d1ecf1; }
        .back-link { color: #3498db; text-decoration: none; }
    </style>
</head>
<body>
    <a href="{{ url_for('index') }}" class="back-link">← Back to Tracker</a>
    
    <h1>Admin Dashboard</h1>
    
    <table>
        <tr>
            <th>ID</th>
            <th>Project</th>
            <th>Target</th>
            <th>Type</th>
            <th>Submitter</th>
            <th>Contact</th>
            <th>PR/Evidence</th>
            <th>Status</th>
            <th>Submitted</th>
            <th>Notes</th>
            <th>Actions</th>
        </tr>
        {% for sub in submissions %}
        <tr class="status-{{ sub.status }}">
            <td>{{ sub.id }}</td>
            <td><a href="{{ sub.project_url }}" target="_blank">{{ sub.project_name }}</a></td>
            <td><a href="{{ sub.target_url }}" target="_blank">{{ sub.target_list }}</a></td>
            <td>{{ sub.submission_type }}</td>
            <td>{{ sub.submitter_name }}</td>
            <td>{{ sub.submitter_contact }}</td>
            <td>
                {% if sub.pr_url %}<a href="{{ sub.pr_url }}" target="_blank">PR</a><br>{% endif %}
                {% if sub.evidence_url %}<a href="{{ sub.evidence_url }}" target="_blank">Evidence</a>{% endif %}
            </td>
            <td>{{ sub.status }}</td>
            <td>{{ sub.submitted_at[:16] }}</td>
            <td>{{ sub.notes[:50] }}{% if sub.notes and sub.notes|length > 50 %}...{% endif %}</td>
            <td class="actions">
                <a href="{{ url_for('update_status', sub_id=sub.id, status='approved') }}" class="btn success">Approve</a>
                <a href="{{ url_for('update_status', sub_id=sub.id, status='verified') }}" class="btn info">Verify</a>
                <a href="{{ url_for('update_status', sub_id=sub.id, status='rejected') }}" class="btn danger">Reject</a>
            </td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
    ''', submissions=submissions)

@app.route('/update/<sub_id>/<status>')
def update_status(sub_id, status):
    if status not in ['pending', 'approved', 'rejected', 'verified']:
        flash('Invalid status', 'error')
        return redirect(url_for('dashboard'))
    
    with sqlite3.connect(DB_PATH) as conn:
        if status == 'verified':
            conn.execute('''
                UPDATE submissions 
                SET status = ?, verified_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (status, sub_id))
        else:
            conn.execute('UPDATE submissions SET status = ? WHERE id = ?', (status, sub_id))
    
    flash(f'Submission {sub_id} marked as {status}', 'success')
    return redirect(url_for('dashboard'))

@app.route('/api/submissions')
def api_submissions():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        submissions = conn.execute('SELECT * FROM submissions ORDER BY submitted_at DESC').fetchall()
    
    return jsonify([dict(row) for row in submissions])

def get_stats():
    with sqlite3.connect(DB_PATH) as conn:
        stats = {}
        stats['total'] = conn.execute('SELECT COUNT(*) FROM submissions').fetchone()[0]
        stats['pending'] = conn.execute('SELECT COUNT(*) FROM submissions WHERE status = "pending"').fetchone()[0]
        stats['verified'] = conn.execute('SELECT COUNT(*) FROM submissions WHERE status = "verified"').fetchone()[0]
        stats['pool_remaining'] = 150 - (stats['verified'] * 5)
    return stats

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5003)