#!/usr/bin/env python3
"""
GitHub Star Growth Tracker Dashboard
Tracks all Scottcjn repo stars over time.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
import urllib.request
import urllib.error

DB_PATH = "star_tracker.db"
OWNER = "Scottcjn"

def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            repo TEXT NOT NULL,
            stars INTEGER NOT NULL,
            UNIQUE(date, repo)
        )
    """)
    conn.commit()
    return conn

def get_all_repos():
    """Fetch all repos from GitHub."""
    url = f"https://api.github.com/users/{OWNER}/repos?per_page=100"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "RustChain-StarTracker")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            repos = json.loads(response.read().decode())
            return {repo["name"]: repo["stargazers_count"] for repo in repos}
    except Exception as e:
        print(f"Error fetching repos: {e}")
        return {}

def save_snapshot(conn, repos):
    """Save today's star counts."""
    today = datetime.now().strftime("%Y-%m-%d")
    c = conn.cursor()
    for repo, stars in repos.items():
        try:
            c.execute(
                "INSERT OR REPLACE INTO snapshots (date, repo, stars) VALUES (?, ?, ?)",
                (today, repo, stars)
            )
        except Exception as e:
            print(f"Error saving {repo}: {e}")
    conn.commit()

def get_history(conn, days=30):
    """Get star history for the last N days."""
    c = conn.cursor()
    c.execute("""
        SELECT date, SUM(stars) as total_stars 
        FROM snapshots 
        WHERE date >= date('now', '-' || ? || ' days')
        GROUP BY date 
        ORDER BY date
    """, (days,))
    return c.fetchall()

def get_top_growers(conn):
    """Get top growing repos."""
    c = conn.cursor()
    c.execute("""
        SELECT s1.repo, s1.stars as current, s0.stars as previous,
               s1.stars - s0.stars as growth
        FROM snapshots s1
        JOIN snapshots s0 ON s1.repo = s0.repo AND s1.date = date('now') 
                          AND s0.date = date('now', '-7 days')
        ORDER BY growth DESC
        LIMIT 10
    """)
    return c.fetchall()

def generate_html(history, top_growers, total_stars, daily_delta):
    """Generate HTML dashboard."""
    dates = [h[0] for h in history]
    stars = [h[1] for h in history]
    
    chart_data = ",".join([str(s) for s in stars])
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>GitHub Star Growth Tracker - {OWNER}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               max-width: 900px; margin: 0 auto; padding: 20px; background: #0d1117; color: #c9d1d9; }}
        h1 {{ color: #58a6ff; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #161b22; padding: 20px; border-radius: 8px; border: 1px solid #30363d; }}
        .stat-value {{ font-size: 32px; font-weight: bold; color: #58a6ff; }}
        .stat-label {{ color: #8b949e; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #30363d; }}
        th {{ color: #58a6ff; }}
        .positive {{ color: #3fb950; }}
    </style>
</head>
<body>
    <h1>⭐ GitHub Star Growth Tracker</h1>
    <p>Owner: <strong>{OWNER}</strong></p>
    
    <div class="stats">
        <div class="stat-card">
            <div class="stat-value">{total_stars}</div>
            <div class="stat-label">Total Stars</div>
        </div>
        <div class="stat-card">
            <div class="stat-value positive">+{daily_delta}</div>
            <div class="stat-label">Today's Delta</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(dates)}</div>
            <div class="stat-label">Days Tracked</div>
        </div>
    </div>
    
    <h2>📈 Star Growth Chart</h2>
    <canvas id="chart" height="80"></canvas>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        new Chart(document.getElementById('chart'), {{
            type: 'line',
            data: {{
                labels: {dates},
                datasets: [{{
                    label: 'Total Stars',
                    data: {chart_data},
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88, 166, 255, 0.1)',
                    fill: true,
                    tension: 0.3
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    y: {{ grid: {{ color: '#30363d' }} }},
                    x: {{ grid: {{ color: '#30363d' }} }}
                }}
            }}
        }});
    </script>
    
    <h2>🏆 Top Growers (7 days)</h2>
    <table>
        <tr><th>Repo</th><th>Current</th><th>Previous</th><th>Growth</th></tr>
"""
    
    for repo, current, previous, growth in top_growers:
        html += f"        <tr><td>{repo}</td><td>{current}</td><td>{previous}</td><td class='positive'>+{growth}</td></tr>\n"
    
    html += """    </table>
</body>
</html>"""
    return html

def main():
    print(f"\n📊 GitHub Star Growth Tracker - {OWNER}")
    print("="*50)
    
    conn = init_db()
    
    # Fetch and save today's data
    print("📥 Fetching repos from GitHub...")
    repos = get_all_repos()
    if repos:
        save_snapshot(conn, repos)
        total_stars = sum(repos.values())
        print(f"   Found {len(repos)} repos with {total_stars} total stars")
    else:
        print("   No repos fetched, using cached data")
    
    # Get history
    history = get_history(conn)
    if history:
        total_stars = history[-1][1] if history else 0
        daily_delta = history[-1][1] - history[-2][1] if len(history) > 1 else 0
    else:
        total_stars = 0
        daily_delta = 0
    
    # Get top growers
    top_growers = get_top_growers(conn)
    
    # Generate dashboard
    html = generate_html(history, top_growers, total_stars, daily_delta)
    with open("star_tracker_dashboard.html", "w") as f:
        f.write(html)
    
    print(f"\n✅ Dashboard generated: star_tracker_dashboard.html")
    print(f"   Total Stars: {total_stars}")
    print(f"   Daily Delta: +{daily_delta}")
    
    if top_growers:
        print(f"\n🏆 Top Growers (7 days):")
        for repo, current, prev, growth in top_growers[:5]:
            print(f"   {repo}: +{growth}")
    
    conn.close()

if __name__ == "__main__":
    main()
