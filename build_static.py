# SPDX-License-Identifier: MIT

import json
import os
from pathlib import Path
from datetime import datetime

def load_projects():
    """Load projects from data/projects.json"""
    projects_file = Path('data/projects.json')
    if not projects_file.exists():
        return []
    
    with open(projects_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('projects', [])

def generate_index_html(projects):
    """Generate the main index.html with embedded CSS/JS"""
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BCOS Certified Projects Directory</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 40px;
            border-bottom: 2px solid #ff6b35;
            padding-bottom: 20px;
        }}
        
        h1 {{
            color: #ff6b35;
            font-size: 2.5rem;
            margin-bottom: 10px;
        }}
        
        .subtitle {{
            color: #888;
            font-size: 1.1rem;
        }}
        
        .search-filters {{
            background: #1a1a1a;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            border: 1px solid #333;
        }}
        
        .search-row {{
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }}
        
        .search-input {{
            flex: 1;
            min-width: 200px;
            padding: 12px;
            border: 1px solid #444;
            border-radius: 4px;
            background: #2a2a2a;
            color: #e0e0e0;
            font-size: 1rem;
        }}
        
        .filter-select {{
            padding: 12px;
            border: 1px solid #444;
            border-radius: 4px;
            background: #2a2a2a;
            color: #e0e0e0;
            font-size: 1rem;
        }}
        
        .projects-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }}
        
        .project-card {{
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
            transition: all 0.3s ease;
        }}
        
        .project-card:hover {{
            border-color: #ff6b35;
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(255, 107, 53, 0.1);
        }}
        
        .project-header {{
            display: flex;
            justify-content: between;
            align-items: flex-start;
            margin-bottom: 15px;
        }}
        
        .project-title {{
            color: #ff6b35;
            font-size: 1.3rem;
            margin-bottom: 5px;
            text-decoration: none;
        }}
        
        .project-title:hover {{
            color: #ff8c69;
        }}
        
        .tier-badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: bold;
            margin-left: auto;
        }}
        
        .tier-L0 {{ background: #28a745; color: white; }}
        .tier-L1 {{ background: #ffc107; color: black; }}
        .tier-L2 {{ background: #dc3545; color: white; }}
        
        .project-url {{
            color: #888;
            font-size: 0.9rem;
            margin-bottom: 10px;
        }}
        
        .project-url a {{
            color: #6c9bd1;
            text-decoration: none;
        }}
        
        .project-url a:hover {{
            text-decoration: underline;
        }}
        
        .project-meta {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin: 15px 0;
            font-size: 0.9rem;
        }}
        
        .meta-item {{
            background: #2a2a2a;
            padding: 8px;
            border-radius: 4px;
        }}
        
        .meta-label {{
            color: #999;
            font-weight: bold;
        }}
        
        .meta-value {{
            color: #e0e0e0;
            font-family: monospace;
            word-break: break-all;
        }}
        
        .project-review {{
            background: #2a2a2a;
            padding: 12px;
            border-radius: 4px;
            border-left: 3px solid #ff6b35;
            margin-top: 15px;
        }}
        
        .review-label {{
            color: #ff6b35;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .category-tag {{
            display: inline-block;
            background: #3a3a3a;
            color: #ccc;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8rem;
            margin: 2px;
        }}
        
        .no-results {{
            text-align: center;
            color: #888;
            font-size: 1.2rem;
            margin-top: 50px;
        }}
        
        .badge-code {{
            background: #2a2a2a;
            border: 1px solid #444;
            border-radius: 4px;
            padding: 8px;
            margin-top: 10px;
            font-family: monospace;
            font-size: 0.8rem;
            color: #ccc;
            cursor: pointer;
        }}
        
        .badge-code:hover {{
            background: #333;
        }}
        
        footer {{
            text-align: center;
            margin-top: 60px;
            padding-top: 20px;
            border-top: 1px solid #333;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>BCOS Certified Projects Directory</h1>
            <p class="subtitle">Browse certified blockchain projects with trust metadata</p>
        </header>
        
        <div class="search-filters">
            <div class="search-row">
                <input type="text" id="searchInput" class="search-input" placeholder="Search projects..." />
                <select id="tierFilter" class="filter-select">
                    <option value="">All Tiers</option>
                    <option value="L0">L0</option>
                    <option value="L1">L1</option>
                    <option value="L2">L2</option>
                </select>
                <select id="categoryFilter" class="filter-select">
                    <option value="">All Categories</option>
                    <option value="agent infra">Agent Infrastructure</option>
                    <option value="video">Video</option>
                    <option value="blockchain">Blockchain</option>
                    <option value="compute rentals">Compute Rentals</option>
                </select>
            </div>
        </div>
        
        <div class="projects-grid" id="projectsGrid">
            {''.join(generate_project_card(project, index) for index, project in enumerate(projects))}
        </div>
        
        <div class="no-results" id="noResults" style="display: none;">
            No projects found matching your criteria.
        </div>
        
        <footer>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')} | Total Projects: {len(projects)}</p>
        </footer>
    </div>
    
    <script>
        const projects = {json.dumps(projects, indent=2)};
        
        function filterProjects() {{
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();
            const tierFilter = document.getElementById('tierFilter').value;
            const categoryFilter = document.getElementById('categoryFilter').value.toLowerCase();
            
            let visibleCount = 0;
            
            projects.forEach((project, index) => {{
                const card = document.querySelector(`[data-project-index="${{index}}"]`);
                if (!card) return;
                
                let matches = true;
                
                // Search filter
                if (searchTerm) {{
                    const searchableText = [
                        project.name,
                        project.url,
                        project.github_repo,
                        project.review_note,
                        ...(project.categories || [])
                    ].join(' ').toLowerCase();
                    
                    matches = matches && searchableText.includes(searchTerm);
                }}
                
                // Tier filter
                if (tierFilter && project.bcos_tier !== tierFilter) {{
                    matches = false;
                }}
                
                // Category filter
                if (categoryFilter) {{
                    const hasCategory = (project.categories || []).some(cat => 
                        cat.toLowerCase().includes(categoryFilter)
                    );
                    matches = matches && hasCategory;
                }}
                
                card.style.display = matches ? 'block' : 'none';
                if (matches) visibleCount++;
            }});
            
            // Show/hide no results message
            const noResults = document.getElementById('noResults');
            noResults.style.display = visibleCount === 0 ? 'block' : 'none';
        }}
        
        // Event listeners
        document.getElementById('searchInput').addEventListener('input', filterProjects);
        document.getElementById('tierFilter').addEventListener('change', filterProjects);
        document.getElementById('categoryFilter').addEventListener('change', filterProjects);
        
        // Badge code copying
        document.querySelectorAll('.badge-code').forEach(element => {{
            element.addEventListener('click', function() {{
                navigator.clipboard.writeText(this.textContent).then(() => {{
                    const original = this.textContent;
                    this.textContent = 'Copied!';
                    setTimeout(() => {{
                        this.textContent = original;
                    }}, 1000);
                }});
            }});
        }});
    </script>
</body>
</html>"""
    
    return html_content

def generate_project_card(project, index=0):
    """Generate HTML for a single project card"""
    categories_html = ''.join(
        f'<span class="category-tag">{category}</span>' 
        for category in project.get('categories', [])
    )
    
    badge_embed = f'<img src="https://img.shields.io/badge/BCOS-{project.get("bcos_tier", "Unknown")}-{"green" if project.get("bcos_tier") == "L0" else "yellow" if project.get("bcos_tier") == "L1" else "red"}" alt="BCOS {project.get("bcos_tier", "Unknown")}" />'
    
    return f'''
    <div class="project-card" data-project-index="{index}">
        <div class="project-header">
            <div>
                <a href="{project.get('url', '#')}" class="project-title" target="_blank">
                    {project.get('name', 'Unknown Project')}
                </a>
                <div class="project-url">
                    <a href="{project.get('url', '#')}" target="_blank">{project.get('url', 'No URL')}</a>
                </div>
            </div>
            <span class="tier-badge tier-{project.get('bcos_tier', 'L2')}">
                {project.get('bcos_tier', 'Unknown')}
            </span>
        </div>
        
        <div class="project-meta">
            <div class="meta-item">
                <div class="meta-label">GitHub:</div>
                <div class="meta-value">
                    <a href="https://github.com/{project.get('github_repo', '')}" target="_blank" style="color: #6c9bd1;">
                        {project.get('github_repo', 'Not specified')}
                    </a>
                </div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Latest SHA:</div>
                <div class="meta-value">{project.get('latest_attested_sha', 'Not available')[:12]}...</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">SBOM Hash:</div>
                <div class="meta-value">{project.get('sbom_hash', 'Not available')[:12]}...</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Categories:</div>
                <div class="meta-value">{categories_html if categories_html else 'Not specified'}</div>
            </div>
        </div>
        
        {f'''<div class="project-review">
            <div class="review-label">Review Note:</div>
            <div>{project.get('review_note', 'No review available')}</div>
        </div>''' if project.get('review_note') else ''}
        
        <div class="badge-code" title="Click to copy badge embed code">
            {badge_embed}
        </div>
    </div>
    '''

def generate_project_page(project):
    """Generate individual project page HTML"""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project.get('name', 'Unknown Project')} - BCOS Certified</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            background: #0a0a0a; 
            color: #e0e0e0; 
            margin: 0; 
            padding: 20px; 
        }}
        .container {{ 
            max-width: 800px; 
            margin: 0 auto; 
            background: #1a1a1a; 
            padding: 30px; 
            border-radius: 8px; 
            border: 1px solid #333; 
        }}
        h1 {{ color: #ff6b35; }}
        .meta-grid {{ 
            display: grid; 
            grid-template-columns: 200px 1fr; 
            gap: 10px; 
            margin: 20px 0; 
        }}
        .meta-label {{ font-weight: bold; color: #999; }}
        .meta-value {{ font-family: monospace; word-break: break-all; }}
        .back-link {{ 
            display: inline-block; 
            color: #6c9bd1; 
            text-decoration: none; 
            margin-bottom: 20px; 
        }}
        .back-link:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <a href="../index.html" class="back-link">← Back to Directory</a>
        
        <h1>{project.get('name', 'Unknown Project')}</h1>
        
        <div class="meta-grid">
            <div class="meta-label">URL:</div>
            <div class="meta-value">
                <a href="{project.get('url', '#')}" target="_blank" style="color: #6c9bd1;">
                    {project.get('url', 'Not specified')}
                </a>
            </div>
            
            <div class="meta-label">GitHub:</div>
            <div class="meta-value">
                <a href="https://github.com/{project.get('github_repo', '')}" target="_blank" style="color: #6c9bd1;">
                    {project.get('github_repo', 'Not specified')}
                </a>
            </div>
            
            <div class="meta-label">BCOS Tier:</div>
            <div class="meta-value">{project.get('bcos_tier', 'Unknown')}</div>
            
            <div class="meta-label">Latest SHA:</div>
            <div class="meta-value">{project.get('latest_attested_sha', 'Not available')}</div>
            
            <div class="meta-label">SBOM Hash:</div>
            <div class="meta-value">{project.get('sbom_hash', 'Not available')}</div>
            
            <div class="meta-label">Categories:</div>
            <div class="meta-value">{', '.join(project.get('categories', []))}</div>
        </div>
        
        {f'''<h2>Review Note</h2>
        <div style="background: #2a2a2a; padding: 15px; border-radius: 4px; border-left: 3px solid #ff6b35;">
            {project.get('review_note', 'No review available')}
        </div>''' if project.get('review_note') else ''}
    </div>
</body>
</html>'''

def build_static_site():
    """Main build function"""
    print("Building BCOS Certified Projects Directory...")
    
    # Create dist directory
    dist_dir = Path('dist')
    dist_dir.mkdir(exist_ok=True)
    
    # Load projects data
    projects = load_projects()
    print(f"Loaded {len(projects)} projects")
    
    # Generate main index.html
    index_html = generate_index_html(projects)
    with open(dist_dir / 'index.html', 'w', encoding='utf-8') as f:
        f.write(index_html)
    print("Generated index.html")
    
    # Generate individual project pages
    projects_dir = dist_dir / 'projects'
    projects_dir.mkdir(exist_ok=True)
    
    for project in projects:
        project_slug = project.get('name', 'unknown').lower().replace(' ', '-').replace('/', '-')
        project_html = generate_project_page(project)
        
        project_file = projects_dir / f'{project_slug}.html'
        with open(project_file, 'w', encoding='utf-8') as f:
            f.write(project_html)
        print(f"Generated projects/{project_slug}.html")
    
    print(f"Build complete! Generated {len(projects) + 1} HTML files in dist/")

if __name__ == '__main__':
    # Make projects available globally for the template
    projects = load_projects()
    build_static_site()
