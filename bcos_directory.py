// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, render_template_string, request, jsonify, send_from_directory
import sqlite3
import json
import os
import hashlib

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bcos-directory-dev-key'

DATABASE = 'bcos_directory.db'

def init_db():
    """Initialize the database with projects table"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            github_repo TEXT NOT NULL,
            bcos_tier TEXT NOT NULL,
            latest_sha TEXT,
            sbom_hash TEXT,
            review_note TEXT,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def load_projects_from_json():
    """Load projects from data/projects.json if it exists"""
    json_file = os.path.join('data', 'projects.json')
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            projects_data = json.load(f)
        
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        for project in projects_data.get('projects', []):
            c.execute('''
                INSERT OR REPLACE INTO projects 
                (name, url, github_repo, bcos_tier, latest_sha, sbom_hash, review_note, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                project.get('name'),
                project.get('url'),
                project.get('github_repo'),
                project.get('bcos_tier'),
                project.get('latest_sha'),
                project.get('sbom_hash'),
                project.get('review_note'),
                project.get('category')
            ))
        
        conn.commit()
        conn.close()

def get_projects(tier_filter=None, category_filter=None):
    """Get projects from database with optional filters"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    query = 'SELECT * FROM projects WHERE 1=1'
    params = []
    
    if tier_filter:
        query += ' AND bcos_tier = ?'
        params.append(tier_filter)
    
    if category_filter:
        query += ' AND category = ?'
        params.append(category_filter)
    
    query += ' ORDER BY created_at DESC'
    
    c.execute(query, params)
    projects = c.fetchall()
    conn.close()
    
    return projects

def get_unique_categories():
    """Get unique categories from database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT DISTINCT category FROM projects WHERE category IS NOT NULL')
    categories = [row[0] for row in c.fetchall()]
    conn.close()
    return categories

# HTML Templates
MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BCOS Certified Directory</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 0;
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5rem;
            font-weight: 300;
        }
        .header p {
            margin: 10px 0 0 0;
            font-size: 1.1rem;
            opacity: 0.9;
        }
        .filters {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        .filter-group {
            display: inline-block;
            margin-right: 20px;
            margin-bottom: 10px;
        }
        .filter-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #555;
        }
        .filter-group select {
            padding: 8px 12px;
            border: 2px solid #e1e5e9;
            border-radius: 4px;
            font-size: 14px;
            background: white;
        }
        .project-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }
        .project-card {
            background: white;
            border-radius: 8px;
            padding: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .project-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }
        .project-name {
            font-size: 1.4rem;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 8px;
        }
        .project-name a {
            color: inherit;
            text-decoration: none;
        }
        .project-name a:hover {
            color: #667eea;
        }
        .project-meta {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin: 16px 0;
            font-size: 0.9rem;
        }
        .meta-item {
            display: flex;
            flex-direction: column;
        }
        .meta-label {
            font-weight: 600;
            color: #666;
            margin-bottom: 4px;
        }
        .meta-value {
            color: #333;
            word-break: break-all;
        }
        .tier-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .tier-l0 { background: #e8f5e8; color: #2d8f2d; }
        .tier-l1 { background: #fff3cd; color: #856404; }
        .tier-l2 { background: #f8d7da; color: #721c24; }
        .category-badge {
            display: inline-block;
            padding: 4px 8px;
            background: #e9ecef;
            color: #495057;
            border-radius: 4px;
            font-size: 0.8rem;
            margin-top: 8px;
        }
        .review-note {
            margin-top: 16px;
            padding: 12px;
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            border-radius: 4px;
            font-style: italic;
            color: #555;
        }
        .github-link {
            color: #0366d6;
            text-decoration: none;
        }
        .github-link:hover {
            text-decoration: underline;
        }
        .badge-embed {
            margin-top: 16px;
            padding: 12px;
            background: #f8f9fa;
            border: 1px dashed #dee2e6;
            border-radius: 4px;
        }
        .badge-embed code {
            font-size: 0.8rem;
            color: #e83e8c;
            background: white;
            padding: 2px 4px;
            border-radius: 2px;
        }
        .stats {
            text-align: center;
            margin-bottom: 30px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1>BCOS Certified Directory</h1>
            <p>Discover trusted blockchain and compute projects with verified attestations</p>
        </div>
    </div>
    
    <div class="container">
        <div class="stats">
            <strong>{{ total_projects }}</strong> certified projects across all tiers
        </div>
        
        <div class="filters">
            <form method="GET" id="filterForm">
                <div class="filter-group">
                    <label for="tier">BCOS Tier:</label>
                    <select name="tier" id="tier" onchange="document.getElementById('filterForm').submit()">
                        <option value="">All Tiers</option>
                        <option value="L0" {% if tier_filter == 'L0' %}selected{% endif %}>L0 - Basic</option>
                        <option value="L1" {% if tier_filter == 'L1' %}selected{% endif %}>L1 - Verified</option>
                        <option value="L2" {% if tier_filter == 'L2' %}selected{% endif %}>L2 - Certified</option>
                    </select>
                </div>
                
                <div class="filter-group">
                    <label for="category">Category:</label>
                    <select name="category" id="category" onchange="document.getElementById('filterForm').submit()">
                        <option value="">All Categories</option>
                        {% for cat in categories %}
                        <option value="{{ cat }}" {% if category_filter == cat %}selected{% endif %}>{{ cat }}</option>
                        {% endfor %}
                    </select>
                </div>
            </form>
        </div>
        
        <div class="project-grid">
            {% for project in projects %}
            <div class="project-card">
                <div class="project-name">
                    <a href="{{ project[2] }}" target="_blank">{{ project[1] }}</a>
                </div>
                
                <div class="project-meta">
                    <div class="meta-item">
                        <div class="meta-label">GitHub</div>
                        <div class="meta-value">
                            <a href="{{ project[3] }}" class="github-link" target="_blank">{{ project[3] }}</a>
                        </div>
                    </div>
                    <div class="meta-item">
                        <div class="meta-label">BCOS Tier</div>
                        <div class="meta-value">
                            <span class="tier-badge tier-{{ project[4].lower() }}">{{ project[4] }}</span>
                        </div>
                    </div>
                    <div class="meta-item">
                        <div class="meta-label">Latest SHA</div>
                        <div class="meta-value">{{ project[5][:12] if project[5] else 'N/A' }}...</div>
                    </div>
                    <div class="meta-item">
                        <div class="meta-label">SBOM Hash</div>
                        <div class="meta-value">{{ project[6][:12] if project[6] else 'N/A' }}...</div>
                    </div>
                </div>
                
                {% if project[8] %}
                <div class="category-badge">{{ project[8] }}</div>
                {% endif %}
                
                {% if project[7] %}
                <div class="review-note">
                    {{ project[7] }}
                </div>
                {% endif %}
                
                <div class="badge-embed">
                    <strong>Embed Badge:</strong><br>
                    <code>&lt;img src="{{ request.host_url }}badge/{{ project[0] }}" alt="BCOS {{ project[4] }} Certified"&gt;</code>
                </div>
            </div>
            {% endfor %}
        </div>
        
        {% if not projects %}
        <div style="text-align: center; padding: 60px; color: #666;">
            <h3>No projects found</h3>
            <p>Try adjusting your filters or check back later.</p>
        </div>
        {% endif %}
    </div>
</body>
</html>
'''

BADGE_SVG_TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" width="120" height="20">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#555;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#4c1;stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="120" height="20" fill="url(#grad)" rx="3"/>
  <text x="10" y="14" font-family="Arial, sans-serif" font-size="11" fill="white">BCOS {{ tier }}</text>
</svg>'''

@app.route('/')
def index():
    tier_filter = request.args.get('tier')
    category_filter = request.args.get('category')
    
    projects = get_projects(tier_filter, category_filter)
    categories = get_unique_categories()
    total_projects = len(get_projects())
    
    return render_template_string(MAIN_TEMPLATE, 
                                projects=projects,
                                categories=categories,
                                total_projects=total_projects,
                                tier_filter=tier_filter,
                                category_filter=category_filter)

@app.route('/projects')
def projects_api():
    tier_filter = request.args.get('tier')
    category_filter = request.args.get('category')
    
    projects = get_projects(tier_filter, category_filter)
    
    projects_data = []
    for project in projects:
        projects_data.append({
            'id': project[0],
            'name': project[1],
            'url': project[2],
            'github_repo': project[3],
            'bcos_tier': project[4],
            'latest_sha': project[5],
            'sbom_hash': project[6],
            'review_note': project[7],
            'category': project[8],
            'created_at': project[9]
        })
    
    return jsonify({'projects': projects_data})

@app.route('/badge/<int:project_id>')
def project_badge(project_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT bcos_tier FROM projects WHERE id = ?', (project_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        tier = result[0]
        svg_content = BADGE_SVG_TEMPLATE.replace('{{ tier }}', tier)
        return svg_content, 200, {'Content-Type': 'image/svg+xml'}
    else:
        return 'Project not found', 404

@app.route('/build')
def build_static():
    """Generate static build in dist/ directory"""
    projects = get_projects()
    categories = get_unique_categories()
    total_projects = len(projects)
    
    # Create dist directory
    os.makedirs('dist', exist_ok=True)
    
    # Generate static HTML
    html_content = render_template_string(MAIN_TEMPLATE,
                                        projects=projects,
                                        categories=categories,
                                        total_projects=total_projects,
                                        tier_filter=None,
                                        category_filter=None)
    
    # Write to dist/index.html
    with open('dist/index.html', 'w') as f:
        f.write(html_content)
    
    # Generate projects JSON for static consumption
    projects_data = []
    for project in projects:
        projects_data.append({
            'id': project[0],
            'name': project[1],
            'url': project[2],
            'github_repo': project[3],
            'bcos_tier': project[4],
            'latest_sha': project[5],
            'sbom_hash': project[6],
            'review_note': project[7],
            'category': project[8],
            'created_at': project[9]
        })
    
    with open('dist/projects.json', 'w') as f:
        json.dump({'projects': projects_data}, f, indent=2)
    
    return jsonify({
        'status': 'success',
        'message': f'Static build generated with {len(projects)} projects',
        'files': ['dist/index.html', 'dist/projects.json']
    })

@app.route('/dist/<path:filename>')
def serve_dist(filename):
    """Serve files from dist directory"""
    return send_from_directory('dist', filename)

if __name__ == '__main__':
    init_db()
    load_projects_from_json()
    app.run(debug=True, host='0.0.0.0', port=5000)