// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import sqlite3
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
from urllib.parse import quote

DB_PATH = 'rustchain.db'
BADGES_DIR = '.github/badges'

def sanitize_slug(name):
    """Create collision-safe slug from hunter name"""
    slug = re.sub(r'[^a-zA-Z0-9_-]', '_', name.lower())
    slug = re.sub(r'_+', '_', slug).strip('_')
    return slug[:32] if slug else 'unknown'

def get_weekly_growth():
    """Calculate weekly growth metrics"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        week_ago = datetime.now() - timedelta(days=7)
        week_ago_str = week_ago.strftime('%Y-%m-%d %H:%M:%S')

        # Total bounties this week
        cursor.execute("""
            SELECT COUNT(*) FROM bounties
            WHERE created_at >= ? AND status = 'completed'
        """, (week_ago_str,))
        weekly_count = cursor.fetchone()[0]

        # Total RTC distributed this week
        cursor.execute("""
            SELECT COALESCE(SUM(reward_amount), 0) FROM bounties
            WHERE created_at >= ? AND status = 'completed'
        """, (week_ago_str,))
        weekly_rtc = cursor.fetchone()[0]

        return {
            'bounties': weekly_count,
            'rtc_distributed': weekly_rtc
        }

def get_top_hunters(limit=3):
    """Get top hunters by total RTC earned"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT hunter_name, COUNT(*) as bounties_completed,
                   COALESCE(SUM(reward_amount), 0) as total_rtc
            FROM bounties
            WHERE status = 'completed' AND hunter_name IS NOT NULL
            GROUP BY hunter_name
            ORDER BY total_rtc DESC, bounties_completed DESC
            LIMIT ?
        """, (limit,))

        return cursor.fetchall()

def get_category_stats():
    """Get bounty statistics by category"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT category, COUNT(*) as count,
                   COALESCE(SUM(reward_amount), 0) as total_rtc
            FROM bounties
            WHERE status = 'completed' AND category IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
        """)

        categories = {}
        for row in cursor.fetchall():
            categories[row[0]] = {
                'count': row[1],
                'total_rtc': row[2]
            }

        return categories

def get_hunter_stats(hunter_name):
    """Get detailed stats for a specific hunter"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Total stats
        cursor.execute("""
            SELECT COUNT(*) as total_bounties,
                   COALESCE(SUM(reward_amount), 0) as total_rtc
            FROM bounties
            WHERE hunter_name = ? AND status = 'completed'
        """, (hunter_name,))

        total_stats = cursor.fetchone()

        # Weekly stats
        week_ago = datetime.now() - timedelta(days=7)
        week_ago_str = week_ago.strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("""
            SELECT COUNT(*) as weekly_bounties,
                   COALESCE(SUM(reward_amount), 0) as weekly_rtc
            FROM bounties
            WHERE hunter_name = ? AND status = 'completed'
            AND created_at >= ?
        """, (hunter_name, week_ago_str))

        weekly_stats = cursor.fetchone()

        # Category breakdown
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM bounties
            WHERE hunter_name = ? AND status = 'completed'
            AND category IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
        """, (hunter_name,))

        categories = dict(cursor.fetchall())

        return {
            'name': hunter_name,
            'slug': sanitize_slug(hunter_name),
            'total_bounties': total_stats[0],
            'total_rtc': total_stats[1],
            'weekly_bounties': weekly_stats[0],
            'weekly_rtc': weekly_stats[1],
            'categories': categories
        }

def generate_badge_json(label, message, color="blue"):
    """Generate shields.io badge JSON format"""
    return {
        "schemaVersion": 1,
        "label": label,
        "message": str(message),
        "color": color
    }

def validate_badge_json(badge_data):
    """Validate badge JSON against expected schema"""
    required_fields = ['schemaVersion', 'label', 'message', 'color']

    if not isinstance(badge_data, dict):
        return False

    for field in required_fields:
        if field not in badge_data:
            return False

    if badge_data['schemaVersion'] != 1:
        return False

    return True

def create_badges_directory():
    """Ensure badges directory exists"""
    os.makedirs(BADGES_DIR, exist_ok=True)

def save_badge(filename, badge_data):
    """Save badge JSON to file with validation"""
    if not validate_badge_json(badge_data):
        raise ValueError(f"Invalid badge data for {filename}")

    filepath = os.path.join(BADGES_DIR, filename)
    with open(filepath, 'w') as f:
        json.dump(badge_data, f, indent=2)

def main():
    """Generate all dynamic badges"""
    create_badges_directory()

    # Weekly growth badges
    weekly_stats = get_weekly_growth()

    weekly_bounties_badge = generate_badge_json(
        "Weekly Bounties",
        weekly_stats['bounties'],
        "brightgreen"
    )
    save_badge('weekly_bounties.json', weekly_bounties_badge)

    weekly_rtc_badge = generate_badge_json(
        "Weekly RTC",
        f"{weekly_stats['rtc_distributed']} RTC",
        "orange"
    )
    save_badge('weekly_rtc.json', weekly_rtc_badge)

    # Top hunters badge
    top_hunters = get_top_hunters(3)
    if top_hunters:
        top_hunter_names = [hunter[0] for hunter in top_hunters[:3]]
        top_hunters_text = " | ".join(top_hunter_names)

        top_hunters_badge = generate_badge_json(
            "Top Hunters",
            top_hunters_text,
            "blue"
        )
        save_badge('top_hunters.json', top_hunters_badge)

    # Category badges
    categories = get_category_stats()
    for category, stats in categories.items():
        if stats['count'] > 0:
            category_slug = sanitize_slug(category)

            badge = generate_badge_json(
                f"{category.title()} Bounties",
                f"{stats['count']} ({stats['total_rtc']} RTC)",
                "purple"
            )
            save_badge(f'category_{category_slug}.json', badge)

    # Per-hunter badges
    hunters_seen = set()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT hunter_name FROM bounties
            WHERE hunter_name IS NOT NULL AND status = 'completed'
        """)

        for row in cursor.fetchall():
            hunter_name = row[0]
            if hunter_name in hunters_seen:
                continue

            hunters_seen.add(hunter_name)
            hunter_stats = get_hunter_stats(hunter_name)

            # Total RTC badge
            rtc_badge = generate_badge_json(
                f"{hunter_name}",
                f"{hunter_stats['total_rtc']} RTC",
                "yellow"
            )
            save_badge(f'hunter_{hunter_stats["slug"]}_rtc.json', rtc_badge)

            # Bounties completed badge
            bounties_badge = generate_badge_json(
                f"{hunter_name} Bounties",
                str(hunter_stats['total_bounties']),
                "green"
            )
            save_badge(f'hunter_{hunter_stats["slug"]}_bounties.json', bounties_badge)

            # Generate hunter summary JSON
            hunter_summary = {
                'hunter': hunter_stats,
                'last_updated': datetime.now().isoformat()
            }

            summary_path = os.path.join(BADGES_DIR, f'hunter_{hunter_stats["slug"]}_summary.json')
            with open(summary_path, 'w') as f:
                json.dump(hunter_summary, f, indent=2)

    # Generate master index
    badge_files = [f for f in os.listdir(BADGES_DIR) if f.endswith('.json')]

    index_data = {
        'generated_at': datetime.now().isoformat(),
        'total_badges': len(badge_files),
        'badge_files': sorted(badge_files),
        'weekly_stats': weekly_stats,
        'top_hunters_count': len(top_hunters),
        'categories_available': list(categories.keys())
    }

    index_path = os.path.join(BADGES_DIR, 'index.json')
    with open(index_path, 'w') as f:
        json.dump(index_data, f, indent=2)

    print(f"Generated {len(badge_files)} badge files")

if __name__ == '__main__':
    main()
