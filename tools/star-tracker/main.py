#!/usr/bin/env python3
"""
GitHub Star Growth Tracker
Tracks Scottcjn repo stars over time and renders a dashboard.
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

# Configuration
DB_PATH = os.path.expanduser("~/.github_star_tracker.db")
GITHUB_API = "https://api.github.com"
OWNER = "Scottcjn"


def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_name TEXT NOT NULL,
            stars INTEGER NOT NULL,
            recorded_at TEXT NOT NULL,
            UNIQUE(repo_name, recorded_at)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repos (
            name TEXT PRIMARY KEY,
            added_at TEXT NOT NULL
        )
    """)
    
    conn.commit()
    return conn


def get_all_repos(owner: str) -> List[Dict]:
    """Get all repositories for an owner."""
    repos = []
    page = 1
    while True:
        url = f"{GITHUB_API}/users/{owner}/repos?per_page=100&page={page}&type=all"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error fetching repos: {response.status_code}")
            break
        
        data = response.json()
        if not data:
            break
        
        repos.extend(data)
        page += 1
        
        # Rate limit protection
        if "next" not in response.links:
            break
    
    return repos


def get_repo_stars(owner: str, repo: str) -> int:
    """Get star count for a single repo."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("stargazers_count", 0)
    return 0


def record_stars(conn: sqlite3.Connection, repos: List[Dict]):
    """Record star counts for all repos."""
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    for repo in repos:
        repo_name = repo["name"]
        stars = repo.get("stargazers_count", 0)
        
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO stars (repo_name, stars, recorded_at) VALUES (?, ?, ?)",
                (repo_name, stars, today)
            )
            
            # Also update if already exists
            cursor.execute(
                "UPDATE stars SET stars = ? WHERE repo_name = ? AND recorded_at = ?",
                (stars, repo_name, today)
            )
        except Exception as e:
            print(f"Error recording {repo_name}: {e}")
        
        # Ensure repo is tracked
        cursor.execute(
            "INSERT OR IGNORE INTO repos (name, added_at) VALUES (?, ?)",
            (repo_name, today)
        )
    
    conn.commit()


def get_star_history(conn: sqlite3.Connection, days: int = 30) -> List[Dict]:
    """Get star history for the past N days."""
    cursor = conn.cursor()
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    cursor.execute("""
        SELECT repo_name, stars, recorded_at 
        FROM stars 
        WHERE recorded_at >= ?
        ORDER BY recorded_at
    """, (start_date,))
    
    return [{"repo": r[0], "stars": r[1], "date": r[2]} for r in cursor.fetchall()]


def get_total_stars(conn: sqlite3.Connection) -> int:
    """Get total stars across all repos."""
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute("""
        SELECT SUM(stars) FROM stars WHERE recorded_at = ?
    """, (today,))
    
    result = cursor.fetchone()[0]
    return result if result else 0


def get_daily_delta(conn: sqlite3.Connection) -> int:
    """Calculate daily star delta."""
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    cursor.execute("""
        SELECT SUM(stars) FROM stars WHERE recorded_at = ?
    """, (today,))
    today_stars = cursor.fetchone()[0] or 0
    
    cursor.execute("""
        SELECT SUM(stars) FROM stars WHERE recorded_at = ?
    """, (yesterday,))
    yesterday_stars = cursor.fetchone()[0] or 0
    
    return today_stars - yesterday_stars


def get_top_growers(conn: sqlite3.Connection, days: int = 7) -> List[Dict]:
    """Get top growing repos."""
    cursor = conn.cursor()
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute("""
        SELECT s1.repo_name, s1.stars as current_stars, s2.stars as old_stars
        FROM stars s1
        JOIN stars s2 ON s1.repo_name = s2.repo_name
        WHERE s1.recorded_at = ? AND s2.recorded_at = ?
    """, (today, start_date))
    
    growers = []
    for row in cursor.fetchall():
        delta = row[1] - row[2]
        if delta > 0:
            growers.append({
                "repo": row[0],
                "stars": row[1],
                "growth": delta
            })
    
    growers.sort(key=lambda x: x["growth"], reverse=True)
    return growers[:10]


def generate_html_dashboard(conn: sqlite3.Connection, output_path: str = "star_dashboard.html"):
    """Generate HTML dashboard."""
    total_stars = get_total_stars(conn)
    daily_delta = get_daily_delta(conn)
    top_growers = get_top_growers(conn)
    history = get_star_history(conn, days=30)
    
    # Prepare chart data
    dates = sorted(set(h["date"] for h in history))
    repo_names = list(set(h["repo"] for h in history))[:20]  # Top 20 repos
    
    chart_data = {}
    for repo in repo_names:
        repo_history = [h for h in history if h["repo"] == repo]
        chart_data[repo] = {h["date"]: h["stars"] for h in repo_history}
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>GitHub Star Growth Tracker - {OWNER}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #0d1117; color: #c9d1d9; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #58a6ff; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: #161b22; padding: 20px; border-radius: 8px; flex: 1; }}
        .stat-value {{ font-size: 32px; font-weight: bold; color: #58a6ff; }}
        .stat-label {{ color: #8b949e; margin-top: 5px; }}
        .positive {{ color: #3fb950; }}
        .negative {{ color: #f85149; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #30363d; }}
        th {{ color: #8b949e; }}
        .chart-container {{ background: #161b22; padding: 20px; border-radius: 8px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>⭐ GitHub Star Growth Tracker - {OWNER}</h1>
        <p>Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{total_stars:,}</div>
                <div class="stat-label">Total Stars</div>
            </div>
            <div class="stat-card">
                <div class="stat-value {'positive' if daily_delta >= 0 else 'negative'}">{'+' if daily_delta >= 0 else ''}{daily_delta}</div>
                <div class="stat-label">Daily Change</div>
            </div>
        </div>
        
        <div class="chart-container">
            <canvas id="starChart"></canvas>
        </div>
        
        <h2>Top Growers (7 days)</h2>
        <table>
            <tr><th>Repository</th><th>Stars</th><th>Growth</th></tr>
"""
    
    for g in top_growers:
        html += f"""            <tr><td>{g['repo']}</td><td>{g['stars']}</td><td class="positive">+{g['growth']}</td></tr>
"""
    
    html += """        </table>
    </div>
    <script>
        const ctx = document.getElementById('starChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: """ + json.dumps(dates) + """,
                datasets: ["""
    
    colors = ['#58a6ff', '#3fb950', '#f85149', '#d29922', '#a371f7', '#f778ba']
    datasets = []
    for i, repo in enumerate(list(chart_data.keys())[:10]):
        data = [chart_data[repo].get(d, 0) for d in dates]
        datasets.append(f"""
                    {{
                        label: '{repo}',
                        data: {data},
                        borderColor: '{colors[i % len(colors)]}',
                        tension: 0.3
                    }}""")
    
    html += ",".join(datasets)
    html += """
            ]
            },
            options: {
                responsive: true,
                plugins: { legend: { labels: { color: '#c9d1d9' } } },
                scales: {
                    x: { ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
                    y: { ticks: { color: '#8b949e' }, grid: { color: '#30363d' } }
                }
            }
        });
    </script>
</body>
</html>"""
    
    with open(output_path, "w") as f:
        f.write(html)
    
    print(f"Dashboard generated: {output_path}")
    return output_path


def print_terminal_dashboard(conn: sqlite3.Connection):
    """Print dashboard in terminal."""
    total_stars = get_total_stars(conn)
    daily_delta = get_daily_delta(conn)
    top_growers = get_top_growers(conn)
    
    print("\n" + "=" * 60)
    print(f"GitHub Star Growth Tracker - {OWNER}")
    print(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)
    
    print(f"\nTotal Stars: {total_stars:,}")
    delta_sign = "+" if daily_delta >= 0 else ""
    print(f"Daily Change: {delta_sign}{daily_delta}")
    
    print("\nTop Growers (7 days):")
    print(f"{'Repository':<40} {'Stars':<10} {'Growth':<10}")
    print("-" * 60)
    for g in top_growers:
        print(f"{g['repo']:<40} {g['stars']:<10} +{g['growth']:<10}")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="GitHub Star Growth Tracker")
    parser.add_argument("--fetch", action="store_true", help="Fetch latest star data")
    parser.add_argument("--dashboard", action="store_true", help="Generate HTML dashboard")
    parser.add_argument("--output", default="star_dashboard.html", help="Output file for dashboard")
    parser.add_argument("-w", "--watch", action="store_true", help="Watch mode")
    parser.add_argument("-i", "--interval", type=int, default=3600, help="Watch interval in seconds")
    args = parser.parse_args()
    
    conn = init_db()
    
    if args.fetch:
        print(f"Fetching repositories for {OWNER}...")
        repos = get_all_repos(OWNER)
        print(f"Found {len(repos)} repositories")
        
        print("Recording star counts...")
        record_stars(conn, repos)
        print("Done!")
    
    if args.dashboard:
        generate_html_dashboard(conn, args.output)
    else:
        print_terminal_dashboard(conn)
    
    if args.watch:
        try:
            while True:
                time.sleep(args.interval)
                repos = get_all_repos(OWNER)
                record_stars(conn, repos)
                print("\033[2J\033[H", end="")
                print_terminal_dashboard(conn)
        except KeyboardInterrupt:
            print("\nStopped.")
    
    conn.close()


if __name__ == "__main__":
    main()
