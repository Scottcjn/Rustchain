// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import render_template_string

AWESOME_TRACKER_MAIN = """
<!DOCTYPE html>
<html>
<head>
    <title>Awesome List Tracker - RustChain</title>
    <style>
        body { font-family: monospace; background: #1a1a1a; color: #00ff41; margin: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { border-bottom: 2px solid #00ff41; padding-bottom: 10px; margin-bottom: 20px; }
        .project-card {
            border: 1px solid #333;
            margin: 10px 0;
            padding: 15px;
            background: #0f0f0f;
            border-radius: 3px;
        }
        .project-title { color: #00ccff; font-size: 1.2em; font-weight: bold; }
        .project-url { color: #888; font-size: 0.9em; margin: 5px 0; }
        .bounty-info { color: #ffaa00; background: #2a2000; padding: 8px; border-radius: 3px; margin: 10px 0; }
        .submissions-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        .submissions-table th, .submissions-table td {
            border: 1px solid #333;
            padding: 8px;
            text-align: left;
        }
        .submissions-table th { background: #0a0a0a; color: #00ff41; }
        .status-pending { color: #ffaa00; }
        .status-approved { color: #00ff41; }
        .status-rejected { color: #ff4444; }
        .submit-form { background: #0f0f0f; padding: 20px; border: 1px solid #333; margin: 20px 0; }
        .form-input {
            background: #1a1a1a;
            border: 1px solid #333;
            color: #00ff41;
            padding: 8px;
            width: 100%;
            margin: 5px 0;
        }
        .form-button {
            background: #003300;
            border: 1px solid #00ff41;
            color: #00ff41;
            padding: 10px 20px;
            cursor: pointer;
        }
        .form-button:hover { background: #004400; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat-card { background: #0f0f0f; border: 1px solid #333; padding: 15px; text-align: center; }
        .stat-number { font-size: 2em; color: #00ccff; }
        .stat-label { color: #888; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Awesome List Tracker</h1>
            <p>Track flagship project submissions to awesome lists and directories</p>
        </div>

        <div class="bounty-info">
            <strong>BOUNTY ACTIVE:</strong> 5 RTC per accepted placement | Max 2 per person | Pool: {{ bounty_pool }} RTC remaining
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{{ total_submissions }}</div>
                <div class="stat-label">Total Submissions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ approved_count }}</div>
                <div class="stat-label">Approved</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ pending_count }}</div>
                <div class="stat-label">Pending Review</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ rtc_paid }}</div>
                <div class="stat-label">RTC Paid Out</div>
            </div>
        </div>

        <h2>🚀 Eligible Flagship Projects</h2>
        {% for project in projects %}
        <div class="project-card">
            <div class="project-title">{{ project.name }}</div>
            <div class="project-url">{{ project.url }}</div>
            <div>{{ project.description }}</div>
            <div style="margin-top: 10px; color: #888;">
                Submissions: {{ project.submission_count }} | Approved: {{ project.approved_count }}
            </div>
        </div>
        {% endfor %}

        <h2>📝 Submit New Placement</h2>
        <div class="submit-form">
            <form method="POST" action="/awesome-tracker/submit">
                <input type="text" name="github_username" placeholder="Your GitHub username" class="form-input" required>
                <select name="project_name" class="form-input" required>
                    <option value="">Select flagship project...</option>
                    {% for project in projects %}
                    <option value="{{ project.name }}">{{ project.name }}</option>
                    {% endfor %}
                </select>
                <input type="url" name="awesome_list_url" placeholder="URL of the awesome list/directory" class="form-input" required>
                <input type="url" name="pr_url" placeholder="Pull Request or listing URL" class="form-input" required>
                <textarea name="description" placeholder="Brief description of the placement..." class="form-input" rows="3"></textarea>
                <button type="submit" class="form-button">Submit for Review</button>
            </form>
        </div>

        <h2>📋 Recent Submissions</h2>
        <table class="submissions-table">
            <thead>
                <tr>
                    <th>Date</th>
                    <th>User</th>
                    <th>Project</th>
                    <th>List/Directory</th>
                    <th>Link</th>
                    <th>Status</th>
                    <th>RTC</th>
                </tr>
            </thead>
            <tbody>
                {% for submission in submissions %}
                <tr>
                    <td>{{ submission.created_at }}</td>
                    <td>{{ submission.github_username }}</td>
                    <td>{{ submission.project_name }}</td>
                    <td><a href="{{ submission.awesome_list_url }}" target="_blank" style="color: #00ccff;">View List</a></td>
                    <td><a href="{{ submission.pr_url }}" target="_blank" style="color: #00ccff;">View PR</a></td>
                    <td class="status-{{ submission.status }}">{{ submission.status.title() }}</td>
                    <td>{{ submission.rtc_reward if submission.status == 'approved' else '-' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #333; color: #666;">
            <p>Powered by RustChain Network | Track your contributions to awesome lists and directories</p>
        </div>
    </div>
</body>
</html>
"""

AWESOME_TRACKER_ADMIN = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Panel - Awesome List Tracker</title>
    <style>
        body { font-family: monospace; background: #1a1a1a; color: #00ff41; margin: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { border-bottom: 2px solid #ff6600; padding-bottom: 10px; margin-bottom: 20px; }
        .admin-section {
            background: #0f0f0f;
            border: 1px solid #ff6600;
            margin: 20px 0;
            padding: 20px;
        }
        .submission-card {
            background: #1a1a1a;
            border: 1px solid #333;
            margin: 10px 0;
            padding: 15px;
        }
        .submission-header { color: #00ccff; font-size: 1.1em; margin-bottom: 10px; }
        .submission-detail { margin: 5px 0; color: #ccc; }
        .submission-actions { margin-top: 15px; }
        .action-button {
            background: #003300;
            border: 1px solid #00ff41;
            color: #00ff41;
            padding: 8px 15px;
            margin: 5px;
            cursor: pointer;
        }
        .approve-btn { border-color: #00ff41; }
        .reject-btn { border-color: #ff4444; color: #ff4444; background: #330000; }
        .action-button:hover { opacity: 0.8; }
        .form-input {
            background: #1a1a1a;
            border: 1px solid #333;
            color: #00ff41;
            padding: 8px;
            margin: 5px 0;
        }
        .stats-overview { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; }
        .stat-box { background: #0a0a0a; padding: 15px; border: 1px solid #444; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔧 Admin Panel - Awesome List Tracker</h1>
            <p style="color: #ff6600;">Review and manage awesome list submissions</p>
        </div>

        <div class="admin-section">
            <h2>📊 Overview Stats</h2>
            <div class="stats-overview">
                <div class="stat-box">
                    <div style="font-size: 1.5em; color: #ffaa00;">{{ pending_count }}</div>
                    <div>Pending Review</div>
                </div>
                <div class="stat-box">
                    <div style="font-size: 1.5em; color: #00ff41;">{{ approved_today }}</div>
                    <div>Approved Today</div>
                </div>
                <div class="stat-box">
                    <div style="font-size: 1.5em; color: #00ccff;">{{ total_rtc_paid }}</div>
                    <div>Total RTC Paid</div>
                </div>
                <div class="stat-box">
                    <div style="font-size: 1.5em; color: #888;">{{ bounty_remaining }}</div>
                    <div>RTC Remaining</div>
                </div>
            </div>
        </div>

        <div class="admin-section">
            <h2>⏳ Pending Submissions</h2>
            {% for submission in pending_submissions %}
            <div class="submission-card">
                <div class="submission-header">
                    {{ submission.project_name }} by @{{ submission.github_username }}
                </div>
                <div class="submission-detail"><strong>Submitted:</strong> {{ submission.created_at }}</div>
                <div class="submission-detail"><strong>Awesome List:</strong>
                    <a href="{{ submission.awesome_list_url }}" target="_blank" style="color: #00ccff;">{{ submission.awesome_list_url }}</a>
                </div>
                <div class="submission-detail"><strong>PR/Listing:</strong>
                    <a href="{{ submission.pr_url }}" target="_blank" style="color: #00ccff;">{{ submission.pr_url }}</a>
                </div>
                {% if submission.description %}
                <div class="submission-detail"><strong>Description:</strong> {{ submission.description }}</div>
                {% endif %}

                <div class="submission-actions">
                    <form method="POST" action="/awesome-tracker/admin/review" style="display: inline;">
                        <input type="hidden" name="submission_id" value="{{ submission.id }}">
                        <button type="submit" name="action" value="approve" class="action-button approve-btn">
                            ✅ Approve (5 RTC)
                        </button>
                        <button type="submit" name="action" value="reject" class="action-button reject-btn">
                            ❌ Reject
                        </button>
                    </form>
                </div>
            </div>
            {% endfor %}

            {% if not pending_submissions %}
            <p style="color: #666;">No pending submissions to review.</p>
            {% endif %}
        </div>

        <div class="admin-section">
            <h2>✅ Recently Reviewed</h2>
            {% for submission in recent_reviewed %}
            <div class="submission-card" style="border-color: {% if submission.status == 'approved' %}#00ff41{% else %}#ff4444{% endif %};">
                <div class="submission-header">
                    {{ submission.project_name }} by @{{ submission.github_username }}
                    <span style="color: {% if submission.status == 'approved' %}#00ff41{% else %}#ff4444{% endif %};">
                        [{{ submission.status.upper() }}]
                    </span>
                </div>
                <div class="submission-detail"><strong>Reviewed:</strong> {{ submission.reviewed_at }}</div>
                <div class="submission-detail"><strong>List:</strong>
                    <a href="{{ submission.awesome_list_url }}" target="_blank" style="color: #888;">{{ submission.awesome_list_url }}</a>
                </div>
                {% if submission.status == 'approved' %}
                <div class="submission-detail" style="color: #00ff41;"><strong>RTC Paid:</strong> {{ submission.rtc_reward }}</div>
                {% endif %}
            </div>
            {% endfor %}
        </div>

        <div class="admin-section">
            <h2>⚙️ Bounty Settings</h2>
            <form method="POST" action="/awesome-tracker/admin/settings">
                <label>RTC per placement:</label>
                <input type="number" name="rtc_per_placement" value="{{ current_rtc_per_placement }}" class="form-input" style="width: 100px;">

                <label>Max claims per user:</label>
                <input type="number" name="max_per_user" value="{{ current_max_per_user }}" class="form-input" style="width: 100px;">

                <label>Total bounty pool:</label>
                <input type="number" name="total_pool" value="{{ current_total_pool }}" class="form-input" style="width: 100px;">

                <button type="submit" class="action-button">Update Settings</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

def render_awesome_tracker_main(**kwargs):
    return render_template_string(AWESOME_TRACKER_MAIN, **kwargs)

def render_awesome_tracker_admin(**kwargs):
    return render_template_string(AWESOME_TRACKER_ADMIN, **kwargs)
