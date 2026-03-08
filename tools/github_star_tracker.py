#!/usr/bin/env python3
"""
GitHub Star Growth Tracker Dashboard

Tracks Scottcjn repo stars over time with SQLite storage and HTML chart.
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


OWNER = "Scottcjn"
DB_PATH = Path("star_tracker.db")


@dataclass
class RepoStars:
    name: str
    stars: int
    url: str


def ensure_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS snapshots(
                ts REAL NOT NULL,
                repo TEXT NOT NULL,
                stars INTEGER NOT NULL,
                PRIMARY KEY (ts, repo)
            )
        """)
        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_repo_ts ON snapshots(repo, ts)
        """)
        db.commit()


def get_all_repos(owner: str) -> List[RepoStars]:
    """Fetch all repositories for the owner."""
    repos: List[RepoStars] = []
    page = 1
    
    while True:
        url = f"https://api.github.com/users/{owner}/repos?per_page=100&page={page}"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "rustchain-star-tracker/1.0",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data:
                    break
                for repo in data:
                    repos.append(RepoStars(
                        name=repo["name"],
                        stars=repo.get("stargazers_count", 0),
                        url=repo["html_url"]
                    ))
                if len(data) < 100:
                    break
                page += 1
        except Exception as e:
            print(f"Error fetching repos: {e}", file=sys.stderr)
            break
    
    return repos


def save_snapshot(path: Path, repos: List[RepoStars]) -> None:
    """Save current star counts to database."""
    now = time.time()
    with sqlite3.connect(str(path)) as db:
        for repo in repos:
            try:
                db.execute(
                    "INSERT OR REPLACE INTO snapshots(ts, repo, stars) VALUES (?, ?, ?)",
                    (now, repo.name, repo.stars)
                )
            except sqlite3.IntegrityError:
                db.execute(
                    "UPDATE snapshots SET stars = ? WHERE ts = ? AND repo = ?",
                    (repo.stars, now, repo.name)
                )
        db.commit()


def get_history(path: Path, days: int = 30) -> Dict[str, List[Tuple[float, int]]]:
    """Get star history for all repos."""
    cutoff = time.time() - (days * 86400)
    with sqlite3.connect(str(path)) as db:
        rows = db.execute("""
            SELECT repo, ts, stars FROM snapshots
            WHERE ts >= ?
            ORDER BY ts ASC
        """, (cutoff,)).fetchall()
    
    history: Dict[str, List[Tuple[float, int]]] = {}
    for repo, ts, stars in rows:
        if repo not in history:
            history[repo] = []
        history[repo].append((ts, stars))
    
    return history


def get_total_stars(repos: List[RepoStars]) -> int:
    return sum(r.stars for r in repos)


def calculate_daily_deltas(path: Path) -> List[Dict[str, Any]]:
    """Calculate daily star changes."""
    with sqlite3.connect(str(path)) as db:
        # Get latest snapshot for each repo
        latest = db.execute("""
            SELECT s1.repo, s1.stars, s1.ts
            FROM snapshots s1
            INNER JOIN (
                SELECT repo, MAX(ts) as max_ts
                FROM snapshots
                GROUP BY repo
            ) s2 ON s1.repo = s2.repo AND s1.ts = s2.max_ts
        """).fetchall()
        
        # Get previous day's snapshot
        prev_cutoff = time.time() - 2 * 86400
        prev = db.execute("""
            SELECT s1.repo, s1.stars
            FROM snapshots s1
            INNER JOIN (
                SELECT repo, MAX(ts) as max_ts
                FROM snapshots
                WHERE ts <= ?
                GROUP BY repo
            ) s2 ON s1.repo = s2.repo AND s1.ts = s2.max_ts
        """, (prev_cutoff,)).fetchall()
    
    prev_dict = {r[0]: r[1] for r in prev}
    
    deltas = []
    for repo, stars, _ in latest:
        prev_stars = prev_dict.get(repo, stars)
        delta = stars - prev_stars
        deltas.append({
            "repo": repo,
            "stars": stars,
            "daily_delta": delta
        })
    
    deltas.sort(key=lambda x: x["daily_delta"], reverse=True)
    return deltas


def generate_html(path: Path, repos: List[RepoStars], days: int = 30) -> str:
    """Generate HTML dashboard."""
    history = get_history(path, days)
    total_stars = get_total_stars(repos)
    deltas = calculate_daily_deltas(path)
    
    # Prepare chart data
    chart_data = []
    for repo_name in list(history.keys())[:20]:  # Top 20 repos
        data_points = history[repo_name]
        if len(data_points) >= 2:
            first_stars = data_points[0][1]
            last_stars = data_points[-1][1]
            growth = last_stars - first_stars
            chart_data.append({
                "name": repo_name,
                "growth": growth,
                "current": last_stars
            })
    
    chart_data.sort(key=lambda x: x["growth"], reverse=True)
    top_growers = chart_data[:10]
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #30363d; }}
        th {{ background: #161b22; color: #8b949e; }}
        tr:hover {{ background: #161b22; }}
        .positive {{ color: #3fb950; }}
        .negative {{ color: #f85149; }}
        a {{ color: #58a6ff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .chart-container {{ background: #161b22; padding: 20px; border-radius: 8px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>⭐ GitHub Star Growth Tracker - {OWNER}</h1>
        <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{total_stars:,}</div>
                <div class="stat-label">Total Stars</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(repos)}</div>
                <div class="stat-label">Repositories</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{sum(1 for d in deltas if d['daily_delta'] > 0)}</div>
                <div class="stat-label">Growing Today</div>
            </div>
        </div>
        
        <div class="chart-container">
            <h2>Top Growers (Last {days} days)</h2>
            <canvas id="growthChart" height="100"></canvas>
        </div>
        
        <h2>All Repositories</h2>
        <table>
            <thead>
                <tr>
                    <th>Repository</th>
                    <th>Stars</th>
                    <th>Daily Δ</th>
                </tr>
            </thead>
            <tbody>
"""
    
    for d in deltas:
        delta_class = "positive" if d["daily_delta"] > 0 else "negative" if d["daily_delta"] < 0 else ""
        delta_sign = "+" if d["daily_delta"] > 0 else ""
        html += f"""
                <tr>
                    <td><a href="https://github.com/{OWNER}/{d['repo']}" target="_blank">{d['repo']}</a></td>
                    <td>{d['stars']:,}</td>
                    <td class="{delta_class}">{delta_sign}{d['daily_delta']}</td>
                </tr>
"""
    
    html += """
            </tbody>
        </table>
    </div>
    <script>
        const ctx = document.getElementById('growthChart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: """ + json.dumps([r["name"][:20] for r in top_growers]) + """,
                datasets: [{
                    label: 'Star Growth',
                    data: """ + json.dumps([r["growth"] for r in top_growers]) + """,
                    backgroundColor: '#58a6ff',
                    borderColor: '#388bfd',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: { beginAtZero: true, grid: { color: '#30363d' }, ticks: { color: '#8b949e' } },
                    x: { grid: { color: '#30363d' }, ticks: { color: '#8b949e' } }
                }
            }
        });
    </script>
</body>
</html>
"""
    return html


def print_terminal(repos: List[RepoStars], deltas: List[Dict[str, Any]]) -> None:
    """Print terminal dashboard."""
    total_stars = get_total_stars(repos)
    
    print(f"GitHub Star Growth Tracker - {OWNER}")
    print("=" * 60)
    print(f"Total Stars: {total_stars:,}")
    print(f"Repositories: {len(repos)}")
    print()
    print("Top Growers Today:")
    print("-" * 40)
    
    for d in deltas[:10]:
        delta_sign = "+" if d["daily_delta"] > 0 else ""
        print(f"  {d['repo']:<30} {d['stars']:>5}  {delta_sign}{d['daily_delta']}")
    
    print()
    print("All Repositories:")
    print("-" * 40)
    for d in deltas:
        delta_sign = "+" if d["daily_delta"] > 0 else ""
        print(f"  {d['repo']:<30} {d['stars']:>5}  {delta_sign}{d['daily_delta']}")


def main():
    parser = argparse.ArgumentParser(description="GitHub Star Growth Tracker")
    parser.add_argument("--fetch", action="store_true", help="Fetch latest star data")
    parser.add_argument("--html", action="store_true", help="Generate HTML dashboard")
    parser.add_argument("--days", type=int, default=30, help="Days of history to show")
    parser.add_argument("--db", type=str, default=str(DB_PATH), help="Database path")
    args = parser.parse_args()
    
    db_path = Path(args.db)
    ensure_db(db_path)
    
    if args.fetch:
        print("Fetching repositories...")
        repos = get_all_repos(OWNER)
        print(f"Found {len(repos)} repositories with {get_total_stars(repos):,} total stars")
        
        print("Saving snapshot...")
        save_snapshot(db_path, repos)
        print("Done!")
    
    if args.html:
        repos = get_all_repos(OWNER)
        save_snapshot(db_path, repos)
        
        html = generate_html(db_path, repos, args.days)
        output_path = Path("star_tracker.html")
        output_path.write_text(html)
        print(f"HTML dashboard saved to {output_path}")
    
    # Default: show terminal output
    repos = get_all_repos(OWNER)
    save_snapshot(db_path, repos)
    deltas = calculate_daily_deltas(db_path)
    print_terminal(repos, deltas)


if __name__ == "__main__":
    main()
