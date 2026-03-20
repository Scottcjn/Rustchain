// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import json

DB_PATH = 'awesome_list_tracker.db'

app = Flask(__name__)

# Initialize database
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL,
                project_url TEXT NOT NULL,
                list_name TEXT NOT NULL,
                list_url TEXT NOT NULL,
                submission_type TEXT NOT NULL,
                pr_url TEXT,
                listing_url TEXT,
                submitter TEXT NOT NULL,
                submitter_address TEXT,
                status TEXT DEFAULT 'pending',
                verification_notes TEXT,
                payout_amount REAL DEFAULT 5.0,
                paid BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_at TIMESTAMP
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS eligible_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL,
                description TEXT
            )
        ''')

        # Insert eligible projects
        projects = [
            ('RustChain', 'https://rustchain.org', 'Blockchain implementation in Rust'),
            ('BoTTube', 'https://bottube.ai', 'AI-powered video platform'),
            ('Beacon Atlas / Beacon', 'https://rustchain.org/beacon/', 'Beacon network explorer'),
            ('Grazer', 'https://github.com/Scottcjn/grazer-skill', 'Grazer skill development tool'),
            ('ClawRTC', 'https://clawhub.ai/packages/clawrtc', 'Real-time communication package')
        ]

        for name, url, desc in projects:
            conn.execute(
                'INSERT OR IGNORE INTO eligible_projects (name, url, description) VALUES (?, ?, ?)',
                (name, url, desc)
            )

# HTML Templates
DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Awesome List Tracker - Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        h1 { color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }
        .stats { display: flex; gap: 20px; margin: 20px 0; }
        .stat-box { background: linear-gradient(135deg, #4CAF50, #45a049); color: white;
                   padding: 20px; border-radius: 8px; flex: 1; text-align: center; }
        .stat-number { font-size: 2em; font-weight: bold; }
        .stat-label { font-size: 0.9em; opacity: 0.9; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f8f9fa; font-weight: bold; }
        .status-pending { color: #ff9800; font-weight: bold; }
        .status-approved { color: #4CAF50; font-weight: bold; }
        .status-rejected { color: #f44336; font-weight: bold; }
        .btn { padding: 8px 16px; text-decoration: none; border-radius: 4px; margin: 2px; }
        .btn-primary { background: #007bff; color: white; }
        .btn-success { background: #28a745; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        .form-section { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Awesome List Tracker</h1>

        <div class="stats">
            <div class="stat-box">
                <div class="stat-number">{{ total_submissions }}</div>
                <div class="stat-label">Total Submissions</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{ approved_count }}</div>
                <div class="stat-label">Approved</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{ total_payout }}</div>
                <div class="stat-label">RTC Paid Out</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{{ remaining_pool }}</div>
                <div class="stat-label">RTC Remaining</div>
            </div>
        </div>

        <div class="form-section">
            <h3>Submit New Entry</h3>
            <form action="/submit" method="post" style="display: grid; gap: 10px; max-width: 600px;">
                <select name="project" required>
                    <option value="">Select Project</option>
                    {% for project in projects %}
                    <option value="{{ project[0] }}">{{ project[0] }} - {{ project[1] }}</option>
                    {% endfor %}
                </select>

                <input type="text" name="list_name" placeholder="List/Directory Name" required>
                <input type="url" name="list_url" placeholder="List/Directory URL" required>

                <select name="submission_type" required>
                    <option value="">Submission Type</option>
                    <option value="pr">Pull Request (Merged)</option>
                    <option value="listing">Live Listing</option>
                    <option value="other">Other Placement</option>
                </select>

                <input type="url" name="pr_url" placeholder="PR URL (if applicable)">
                <input type="url" name="listing_url" placeholder="Direct Listing URL">
                <input type="text" name="submitter" placeholder="Your Name/Handle" required>
                <input type="text" name="submitter_address" placeholder="RTC Address (for payout)">

                <button type="submit" class="btn btn-primary">Submit Entry</button>
            </form>
        </div>

        <h3>Recent Submissions</h3>
        <table>
            <thead>
                <tr>
                    <th>Project</th>
                    <th>List Name</th>
                    <th>Type</th>
                    <th>Submitter</th>
                    <th>Status</th>
                    <th>Payout</th>
                    <th>Date</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for sub in submissions %}
                <tr>
                    <td><strong>{{ sub[1] }}</strong></td>
                    <td><a href="{{ sub[4] }}" target="_blank">{{ sub[3] }}</a></td>
                    <td>{{ sub[5] }}</td>
                    <td>{{ sub[8] }}</td>
                    <td class="status-{{ sub[10] }}">{{ sub[10] }}</td>
                    <td>{{ sub[12] }} RTC</td>
                    <td>{{ sub[14][:10] }}</td>
                    <td>
                        {% if sub[6] %}<a href="{{ sub[6] }}" target="_blank" class="btn btn-primary">PR</a>{% endif %}
                        {% if sub[7] %}<a href="{{ sub[7] }}" target="_blank" class="btn btn-success">Live</a>{% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
'''

@app.route('/')
def dashboard():
    with sqlite3.connect(DB_PATH) as conn:
        # Get statistics
        total_submissions = conn.execute('SELECT COUNT(*) FROM submissions').fetchone()[0]
        approved_count = conn.execute('SELECT COUNT(*) FROM submissions WHERE status = "approved"').fetchone()[0]
        total_payout = conn.execute('SELECT COALESCE(SUM(payout_amount), 0) FROM submissions WHERE paid = TRUE').fetchone()[0]
        remaining_pool = 150 - total_payout

        # Get eligible projects
        projects = conn.execute('SELECT name, url FROM eligible_projects').fetchall()

        # Get recent submissions
        submissions = conn.execute('''
            SELECT * FROM submissions
            ORDER BY created_at DESC
            LIMIT 20
        ''').fetchall()

        return render_template_string(DASHBOARD_TEMPLATE,
            total_submissions=total_submissions,
            approved_count=approved_count,
            total_payout=total_payout,
            remaining_pool=remaining_pool,
            projects=projects,
            submissions=submissions
        )

@app.route('/submit', methods=['POST'])
def submit_entry():
    project = request.form['project']
    list_name = request.form['list_name']
    list_url = request.form['list_url']
    submission_type = request.form['submission_type']
    pr_url = request.form.get('pr_url', '')
    listing_url = request.form.get('listing_url', '')
    submitter = request.form['submitter']
    submitter_address = request.form.get('submitter_address', '')

    # Get project URL
    with sqlite3.connect(DB_PATH) as conn:
        project_url = conn.execute(
            'SELECT url FROM eligible_projects WHERE name = ?',
            (project,)
        ).fetchone()[0]

        conn.execute('''
            INSERT INTO submissions
            (project, project_url, list_name, list_url, submission_type, pr_url,
             listing_url, submitter, submitter_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (project, project_url, list_name, list_url, submission_type,
              pr_url, listing_url, submitter, submitter_address))

    return jsonify({'status': 'success', 'message': 'Submission added successfully'})

@app.route('/api/submissions')
def api_submissions():
    with sqlite3.connect(DB_PATH) as conn:
        submissions = conn.execute('''
            SELECT id, project, list_name, list_url, submission_type, submitter,
                   status, payout_amount, created_at, pr_url, listing_url
            FROM submissions
            ORDER BY created_at DESC
        ''').fetchall()

        return jsonify([{
            'id': s[0], 'project': s[1], 'list_name': s[2], 'list_url': s[3],
            'submission_type': s[4], 'submitter': s[5], 'status': s[6],
            'payout_amount': s[7], 'created_at': s[8], 'pr_url': s[9], 'listing_url': s[10]
        } for s in submissions])

@app.route('/api/verify/<int:submission_id>', methods=['POST'])
def verify_submission(submission_id):
    data = request.get_json()
    status = data.get('status', 'approved')  # approved, rejected, pending
    notes = data.get('notes', '')

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            UPDATE submissions
            SET status = ?, verification_notes = ?, verified_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, notes, submission_id))

        if status == 'approved':
            conn.execute('''
                UPDATE submissions
                SET paid = TRUE
                WHERE id = ?
            ''', (submission_id,))

    return jsonify({'status': 'success', 'message': f'Submission {status}'})

@app.route('/api/stats')
def api_stats():
    with sqlite3.connect(DB_PATH) as conn:
        stats = {}
        stats['total'] = conn.execute('SELECT COUNT(*) FROM submissions').fetchone()[0]
        stats['approved'] = conn.execute('SELECT COUNT(*) FROM submissions WHERE status = "approved"').fetchone()[0]
        stats['pending'] = conn.execute('SELECT COUNT(*) FROM submissions WHERE status = "pending"').fetchone()[0]
        stats['rejected'] = conn.execute('SELECT COUNT(*) FROM submissions WHERE status = "rejected"').fetchone()[0]
        stats['total_payout'] = conn.execute('SELECT COALESCE(SUM(payout_amount), 0) FROM submissions WHERE paid = TRUE').fetchone()[0]
        stats['remaining_pool'] = 150 - stats['total_payout']

        # Top contributors
        contributors = conn.execute('''
            SELECT submitter, COUNT(*) as count, SUM(CASE WHEN paid THEN payout_amount ELSE 0 END) as earned
            FROM submissions
            GROUP BY submitter
            ORDER BY count DESC
            LIMIT 10
        ''').fetchall()
        stats['top_contributors'] = [{'name': c[0], 'submissions': c[1], 'earned': c[2]} for c in contributors]

        return jsonify(stats)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5003)
