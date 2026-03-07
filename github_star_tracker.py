#!/usr/bin/env python3
"""
GitHub Star Growth Tracker Dashboard
Tracks all Scottcjn repo stars over time.
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests


# Configuration
DB_FILE = "github_stars.db"
GITHUB_API_DELAY = 0.5  # seconds between API calls to avoid rate limiting
OWNER = "Scottcjn"


def init_db(conn: sqlite3.Connection):
    """Initialize the database schema."""
    cursor = conn.cursor()
    
    # Repos table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repos (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            description TEXT,
            stars INTEGER DEFAULT 0,
            forks INTEGER DEFAULT 0,
            language TEXT,
            created_at TEXT,
            updated_at TEXT,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Star history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS star_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER NOT NULL,
            stars INTEGER NOT NULL,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (repo_id) REFERENCES repos (id),
            UNIQUE (repo_id, date(recorded_at))
        )
    """)
    
    conn.commit()


def get_all_repos(owner: str, token: Optional[str] = None) -> List[dict]:
    """Get all repos for an owner using GitHub API."""
    repos = []
    page = 1
    per_page = 100
    
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    
    while True:
        url = f"https://api.github.com/users/{owner}/repos"
        params = {"page": page, "per_page": per_page, "sort": "updated"}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                break
                
            repos.extend(data)
            
            if len(data) < per_page:
                break
                
            page += 1
            time.sleep(GITHUB_API_DELAY)
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching repos: {e}")
            break
    
    return repos


def get_repo_stars(owner: str, repo: str, token: Optional[str] = None) -> dict:
    """Get current stars for a specific repo."""
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    
    url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {repo}: {e}")
        return {}


def save_repos_to_db(conn: sqlite3.Connection, repos: List[dict]):
    """Save or update repos in the database."""
    cursor = conn.cursor()
    
    for repo in repos:
        cursor.execute("""
            INSERT INTO repos (id, name, full_name, description, stars, forks, language, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                full_name = excluded.full_name,
                description = excluded.description,
                stars = excluded.stars,
                forks = excluded.forks,
                language = excluded.language,
                updated_at = excluded.updated_at
        """, (
            repo.get("id"),
            repo.get("name"),
            repo.get("full_name"),
            repo.get("description"),
            repo.get("stargazers_count", 0),
            repo.get("forks_count", 0),
            repo.get("language"),
            repo.get("created_at"),
            repo.get("updated_at")
        ))
    
    conn.commit()


def record_star_snapshots(conn: sqlite3.Connection):
    """Record current star counts as snapshots."""
    cursor = conn.cursor()
    
    # Get all repo IDs and current stars
    cursor.execute("SELECT id, name, stars FROM repos")
    repos = cursor.fetchall()
    
    for repo_id, name, stars in repos:
        try:
            cursor.execute("""
                INSERT INTO star_history (repo_id, stars, recorded_at)
                VALUES (?, ?, datetime('now', 'utc'))
                ON CONFLICT(repo_id, date(recorded_at)) DO UPDATE SET
                    stars = excluded.stars
            """, (repo_id, stars))
        except sqlite3.IntegrityError:
            # Already recorded today
            pass
    
    conn.commit()


def get_total_stars(conn: sqlite3.Connection) -> int:
    """Get total stars across all repos."""
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(stars) FROM repos")
    result = cursor.fetchone()
    return result[0] if result[0] else 0


def get_daily_deltas(conn: sqlite3.Connection) -> List[dict]:
    """Get daily star deltas."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            r.name,
            sh1.stars as today_stars,
            sh2.stars as yesterday_stars,
            sh1.stars - COALESCE(sh2.stars, 0) as delta
        FROM repos r
        JOIN star_history sh1 ON r.id = sh1.repo_id
        LEFT JOIN star_history sh2 ON r.id = sh2.repo_id 
            AND date(sh2.recorded_at) = date('now', '-1 day', 'utc')
        WHERE date(sh1.recorded_at) = date('now', 'utc')
        ORDER BY delta DESC
        LIMIT 10
    """)
    
    results = []
    for row in cursor.fetchall():
        results.append({
            "name": row[0],
            "today_stars": row[1],
            "yesterday_stars": row[2] or 0,
            "delta": row[3]
        })
    
    return results


def get_top_growers(conn: sqlite3.Connection, days: int = 7) -> List[dict]:
    """Get top growers over the past N days."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            r.name,
            MIN(sh.stars) as start_stars,
            MAX(sh.stars) as end_stars,
            MAX(sh.stars) - MIN(sh.stars) as growth
        FROM repos r
        JOIN star_history sh ON r.id = sh.repo_id
        WHERE date(sh.recorded_at) >= date('now', f'-{days} days', 'utc')
        GROUP BY r.id
        HAVING growth > 0
        ORDER BY growth DESC
        LIMIT 10
    """)
    
    results = []
    for row in cursor.fetchall():
        results.append({
            "name": row[0],
            "start_stars": row[1],
            "end_stars": row[2],
            "growth": row[3]
        })
    
    return results


def get_all_repos_stars(conn: sqlite3.Connection) -> List[dict]:
    """Get all repos with their current stars."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, stars, forks, language, updated_at 
        FROM repos 
        ORDER BY stars DESC
    """)
    
    results = []
    for row in cursor.fetchall():
        results.append({
            "name": row[0],
            "stars":            "forks": row[2],
            "language": row[3 row[1],
],
            "updated_at": row[4]
        })
    
    return results


def generate_html_dashboard(conn: sqlite3.Connection, output_file: str = "stars_dashboard.html"):
    """Generate an HTML dashboard with charts."""
    total_stars = get_total_stars(conn)
    daily_deltas = get_daily_deltas(conn)
    top_growers = get_top_growers(conn)
    all_repos = get_all_repos_stars(conn)
    
    # Get historical data for chart
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date(recorded_at) as day, SUM(stars) as total
        FROM star_history
        WHERE date(recorded_at) >= date('now', '-30 days', 'utc')
        GROUP BY day
        ORDER BY day
    """)
    
    chart_data = []
    for row in cursor.fetchall():
        chart_data.append(f"['{row[0]}', {row[1]}]")
    
    chart_data_str = ",\n        ".join(chart_data)
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub Star Growth Tracker - {OWNER}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #0d1117;
            color: #c9d1d9;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1, h2 {{
            color: #58a6ff;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 20px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 36px;
            font-weight: bold;
            color: #58a6ff;
        }}
        .stat-label {{
            color: #8b949e;
            margin-top: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #30363d;
        }}
        th {{
            background: #161b22;
            color: #58a6ff;
        }}
        .delta-positive {{
            color: #3fb950;
        }}
        .delta-negative {{
            color: #f85149;
        }}
        .repo-link {{
            color: #58a6ff;
            text-decoration: none;
        }}
        .repo-link:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>⭐ GitHub Star Growth Tracker</h1>
        <p>Tracking all <strong>{OWNER}</strong> repositories</p>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{total_stars:,}</div>
                <div class="stat-label">Total Stars</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(all_repos)}</div>
                <div class="stat-label">Repositories</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{sum(r['forks'] for r in all_repos):,}</div>
                <div class="stat-label">Total Forks</div>
            </div>
        </div>
        
        <h2>📈 Star Growth (Last 30 Days)</h2>
        <canvas id="growthChart" height="80"></canvas>
        
        <h2>🔥 Today's Top Gainers</h2>
        <table>
            <tr>
                <th>Repository</th>
                <th>Yesterday</th>
                <th>Today</th>
                <th>Delta</th>
            </tr>
"""
    
    for repo in daily_deltas:
        delta_class = "delta-positive" if repo["delta"] > 0 else "delta-negative"
        delta_sign = "+" if repo["delta"] > 0 else ""
        html += f"""            <tr>
                <td><a class="repo-link" href="https://github.com/{OWNER}/{repo['name']}">{repo['name']}</a></td>
                <td>{repo['yesterday_stars']}</td>
                <td>{repo['today_stars']}</td>
                <td class="{delta_class}">{delta_sign}{repo['delta']}</td>
            </tr>
"""
    
    html += """        </table>
        
        <h2>🏆 Top Growers (Last 7 Days)</h2>
        <table>
            <tr>
                <th>Repository</th>
                <th>Start</th>
                <th>End</th>
                <th>Growth</th>
            </tr>
"""
    
    for repo in top_growers:
        html += f"""            <tr>
                <td><a class="repo-link" href="https://github.com/{OWNER}/{repo['name']}">{repo['name']}</a></td>
                <td>{repo['start_stars']}</td>
                <td>{repo['end_stars']}</td>
                <td class="delta-positive">+{repo['growth']}</td>
            </tr>
"""
    
    html += """        </table>
        
        <h2>📦 All Repositories</h2>
        <table>
            <tr>
                <th>Repository</th>
                <th>Stars</th>
                <th>Forks</th>
                <th>Language</th>
                <th>Updated</th>
            </tr>
"""
    
    for repo in all_repos:
        html += f"""            <tr>
                <td><a class="repo-link" href="https://github.com/{OWNER}/{repo['name']}">{repo['name']}</a></td>
                <td>⭐ {repo['stars']}</td>
                <td>{repo['forks']}</td>
                <td>{repo['language'] or '-'}</td>
                <td>{repo['updated_at'][:10]}</td>
            </tr>
"""
    
    html += f"""        </table>
        
        <p style="color: #8b949e; text-align: center; margin-top: 40px;">
            Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
        </p>
    </div>
    
    <script>
        const ctx = document.getElementById('growthChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: [{chart_data_str}].map(d => d[0]),
                datasets: [{{
                    label: 'Total Stars',
                    data: [{chart_data_str}].map(d => d[1]),
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88, 166, 255, 0.1)',
                    fill: true,
                    tension: 0.3
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        labels: {{ color: '#c9d1d9' }}
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#8b949e' }},
                        grid: {{ color: '#30363d' }}
                    }},
                    y: {{
                        ticks: {{ color: '#8b949e' }},
                        grid: {{ color: '#30363d' }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    
    with open(output_file, 'w') as f:
        f.write(html)
    
    print(f"Dashboard generated: {output_file}")


def print_terminal_dashboard(conn: sqlite3.Connection):
    """Print dashboard to terminal."""
    total_stars = get_total_stars(conn)
    daily_deltas = get_daily_deltas(conn)
    top_growers = get_top_growers(conn)
    all_repos = get_all_repos_stars(conn)
    
    print("\n" + "=" * 60)
    print(f"  GitHub Star Growth Tracker - {OWNER}")
    print("=" * 60)
    print()
    print(f"  Total Stars: {total_stars:,}")
    print(f"  Repositories: {len(all_repos)}")
    print(f"  Total Forks: {sum(r['forks'] for r in all_repos):,}")
    print()
    
    print("-" * 60)
    print("  Today's Top Gainers")
    print("-" * 60)
    print(f"  {'Repository':<30} {'Yesterday':<10} {'Today':<10} {'Delta':<10}")
    for repo in daily_deltas[:5]:
        delta = f"+{repo['delta']}" if repo['delta'] > 0 else str(repo['delta'])
        print(f"  {repo['name']:<30} {repo['yesterday_stars']:<10} {repo['today_stars']:<10} {delta:<10}")
    print()
    
    print("-" * 60)
    print("  Top Growers (Last 7 Days)")
    print("-" * 60)
    print(f"  {'Repository':<30} {'Start':<10} {'End':<10} {'Growth':<10}")
    for repo in top_growers[:5]:
        print(f"  {repo['name']:<30} {repo['start_stars']:<10} {repo['end_stars']:<10} +{repo['growth']:<10}")
    print()
    
    print("-" * 60)
    print("  All Repositories (Top 20)")
    print("-" * 60)
    print(f"  {'Repository':<30} {'Stars':<10} {'Forks':<10} {'Language':<15}")
    for repo in all_repos[:20]:
        lang = repo['language'] or '-'
        print(f"  {repo['name']:<30} {repo['stars']:<10} {repo['forks']:<10} {lang:<15}")
    print()
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="GitHub Star Growth Tracker - Track repo stars over time"
    )
    parser.add_argument(
        "--token", "-t",
        type=str,
        help="GitHub personal access token (for higher rate limits)"
    )
    parser.add_argument(
        "--update", "-u",
        action="store_true",
        help="Fetch latest data from GitHub"
    )
    parser.add_argument(
        "--html", "-w",
        action="store_true",
        help="Generate HTML dashboard"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="stars_dashboard.html",
        help="HTML output file (default: stars_dashboard.html)"
    )
    
    args = parser.parse_args()
    
    # Connect to database
    conn = sqlite3.connect(DB_FILE)
    init_db(conn)
    
    # Update data if requested
    if args.update:
        print(f"Fetching repos from {OWNER}...")
        repos = get_all_repos(OWNER, args.token)
        print(f"Found {len(repos)} repositories")
        
        print("Saving to database...")
        save_repos_to_db(conn, repos)
        
        print("Recording star snapshots...")
        record_star_snapshots(conn)
        
        print("Done!")
    
    # Generate output
    if args.html:
        generate_html_dashboard(conn, args.output)
    else:
        print_terminal_dashboard(conn)
    
    conn.close()


if __name__ == "__main__":
    main()
