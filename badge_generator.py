# SPDX-License-Identifier: MIT

import json
import os
import re
import sqlite3
import hashlib
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path


class BadgeGenerator:

    def __init__(self, db_path: str = "rustchain.db", badges_dir: str = "badges"):
        self.db_path = db_path
        self.badges_dir = Path(badges_dir)
        self.badges_dir.mkdir(exist_ok=True)
        self.slug_registry = {}
        self._load_existing_slugs()

    def _load_existing_slugs(self):
        """Load existing badge slugs to prevent collisions"""
        for badge_file in self.badges_dir.glob("*.json"):
            try:
                with open(badge_file, 'r') as f:
                    data = json.load(f)
                    if 'slug' in data:
                        self.slug_registry[data['slug']] = badge_file.stem
            except (json.JSONDecodeError, IOError):
                continue

    def create_safe_slug(self, name: str, category: str = "") -> str:
        """Generate collision-safe slug for hunter or category"""
        base_slug = re.sub(r'[^a-zA-Z0-9_-]', '_', f"{category}_{name}".lower().strip('_'))
        base_slug = re.sub(r'_{2,}', '_', base_slug)

        if base_slug not in self.slug_registry:
            self.slug_registry[base_slug] = name
            return base_slug

        # Handle collision with hash suffix
        hash_suffix = hashlib.md5(f"{name}_{category}".encode()).hexdigest()[:6]
        collision_slug = f"{base_slug}_{hash_suffix}"
        self.slug_registry[collision_slug] = name
        return collision_slug

    def parse_hunter_data_db(self) -> List[Dict[str, Any]]:
        """Parse hunter data from SQLite database"""
        hunters = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT DISTINCT miner_id as hunter_id,
                           COUNT(*) as total_transactions,
                           SUM(amount_rtc) as total_rtc,
                           MIN(timestamp) as first_seen,
                           MAX(timestamp) as last_activity
                    FROM transactions
                    WHERE miner_id IS NOT NULL
                    GROUP BY miner_id
                    ORDER BY total_rtc DESC
                """)

                for row in cursor.fetchall():
                    hunters.append({
                        'hunter_id': row['hunter_id'],
                        'name': row['hunter_id'][:12] + "..." if len(row['hunter_id']) > 12 else row['hunter_id'],
                        'total_transactions': row['total_transactions'],
                        'total_rtc': float(row['total_rtc'] or 0),
                        'first_seen': row['first_seen'],
                        'last_activity': row['last_activity'],
                        'category': self._infer_category(row)
                    })
        except sqlite3.Error:
            pass

        return hunters

    def _infer_category(self, row) -> str:
        """Infer hunter category from transaction patterns"""
        rtc_amount = float(row['total_rtc'] or 0)
        if rtc_amount > 100:
            return "whale"
        elif rtc_amount > 10:
            return "active"
        else:
            return "starter"

    def parse_hunter_data_json(self, json_path: str) -> List[Dict[str, Any]]:
        """Parse hunter data from JSON file"""
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'hunters' in data:
                    return data['hunters']
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return []

    def generate_hunter_badge(self, hunter: Dict[str, Any]) -> Dict[str, Any]:
        """Generate individual hunter badge JSON"""
        rtc_val = hunter.get('total_rtc', 0)
        tx_count = hunter.get('total_transactions', 0)

        # Determine color based on RTC amount
        if rtc_val >= 100:
            color = "brightgreen"
        elif rtc_val >= 10:
            color = "green"
        elif rtc_val >= 1:
            color = "yellow"
        else:
            color = "lightgrey"

        return {
            "schemaVersion": 1,
            "label": hunter.get('name', 'Hunter'),
            "message": f"{rtc_val:.2f} RTC | {tx_count} tx",
            "color": color,
            "slug": self.create_safe_slug(hunter.get('hunter_id', 'unknown'), 'hunter'),
            "namedLogo": "bitcoin",
            "logoColor": "orange"
        }

    def generate_weekly_growth_badge(self, hunters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate weekly growth summary badge"""
        now = datetime.now()
        week_ago = now - timedelta(days=7)

        recent_hunters = []
        total_weekly_rtc = 0

        for hunter in hunters:
            last_activity = hunter.get('last_activity')
            if last_activity and isinstance(last_activity, str):
                try:
                    activity_date = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                    if activity_date >= week_ago:
                        recent_hunters.append(hunter)
                        total_weekly_rtc += hunter.get('total_rtc', 0)
                except ValueError:
                    continue

        growth_msg = f"+{len(recent_hunters)} hunters | {total_weekly_rtc:.1f} RTC"

        return {
            "schemaVersion": 1,
            "label": "Weekly Growth",
            "message": growth_msg,
            "color": "blue" if len(recent_hunters) > 5 else "lightblue",
            "slug": "weekly_growth",
            "style": "flat-square"
        }

    def generate_top_hunters_badge(self, hunters: List[Dict[str, Any]], limit: int = 3) -> Dict[str, Any]:
        """Generate top hunters summary badge"""
        top_hunters = sorted(hunters, key=lambda x: x.get('total_rtc', 0), reverse=True)[:limit]

        if not top_hunters:
            return {
                "schemaVersion": 1,
                "label": "Top Hunters",
                "message": "No data",
                "color": "inactive",
                "slug": "top_hunters"
            }

        total_rtc = sum(h.get('total_rtc', 0) for h in top_hunters)
        names = [h.get('name', 'Unknown')[:8] for h in top_hunters]

        return {
            "schemaVersion": 1,
            "label": "Top 3 Hunters",
            "message": f"{', '.join(names)} | {total_rtc:.1f} RTC",
            "color": "gold",
            "slug": "top_hunters",
            "logoSvg": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16'><text y='12' font-size='12'>🏆</text></svg>"
        }

    def generate_category_badge(self, hunters: List[Dict[str, Any]], category: str) -> Optional[Dict[str, Any]]:
        """Generate category-specific badge if data exists"""
        category_hunters = [h for h in hunters if h.get('category') == category]

        if not category_hunters:
            return None

        total_rtc = sum(h.get('total_rtc', 0) for h in category_hunters)
        count = len(category_hunters)

        colors = {
            'docs': 'blue',
            'outreach': 'purple',
            'bug': 'red',
            'whale': 'gold',
            'active': 'green',
            'starter': 'lightgrey'
        }

        return {
            "schemaVersion": 1,
            "label": f"{category.title()} Hunters",
            "message": f"{count} hunters | {total_rtc:.1f} RTC",
            "color": colors.get(category, "lightblue"),
            "slug": self.create_safe_slug(category, 'category'),
            "style": "flat"
        }

    def validate_badge_schema(self, badge_data: Dict[str, Any]) -> bool:
        """Validate badge JSON against shields.io schema"""
        required_fields = ['schemaVersion', 'label', 'message']

        if not all(field in badge_data for field in required_fields):
            return False

        if badge_data['schemaVersion'] != 1:
            return False

        if not isinstance(badge_data['label'], str) or not isinstance(badge_data['message'], str):
            return False

        # Optional field validation
        optional_fields = {
            'color': str,
            'labelColor': str,
            'logoSvg': str,
            'namedLogo': str,
            'style': str,
            'slug': str
        }

        for field, expected_type in optional_fields.items():
            if field in badge_data and not isinstance(badge_data[field], expected_type):
                return False

        return True

    def save_badge(self, badge_data: Dict[str, Any], filename: str) -> bool:
        """Save badge JSON to file with validation"""
        if not self.validate_badge_schema(badge_data):
            return False

        filepath = self.badges_dir / f"{filename}.json"
        try:
            with open(filepath, 'w') as f:
                json.dump(badge_data, f, indent=2, sort_keys=True)
            return True
        except IOError:
            return False

    def generate_all_badges(self, data_source: Union[str, List[Dict[str, Any]]] = None):
        """Generate all badge types from data source"""
        if isinstance(data_source, str):
            hunters = self.parse_hunter_data_json(data_source)
        elif isinstance(data_source, list):
            hunters = data_source
        else:
            hunters = self.parse_hunter_data_db()

        if not hunters:
            return

        # Generate individual hunter badges
        for hunter in hunters[:20]:  # Limit to prevent too many files
            badge = self.generate_hunter_badge(hunter)
            slug = badge.get('slug', 'unknown_hunter')
            self.save_badge(badge, f"hunter_{slug}")

        # Generate summary badges
        weekly_badge = self.generate_weekly_growth_badge(hunters)
        self.save_badge(weekly_badge, "weekly_growth")

        top_hunters_badge = self.generate_top_hunters_badge(hunters)
        self.save_badge(top_hunters_badge, "top_hunters")

        # Generate category badges if data exists
        categories = set(h.get('category') for h in hunters if h.get('category'))
        for category in categories:
            category_badge = self.generate_category_badge(hunters, category)
            if category_badge:
                slug = category_badge.get('slug', category)
                self.save_badge(category_badge, f"category_{slug}")

    def get_embed_examples(self) -> List[str]:
        """Generate README embed examples for badges"""
        examples = []

        # Base URL for shields.io dynamic badges
        base_url = "https://img.shields.io/endpoint"
        repo_badges_url = "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/badges"

        examples.append("## Badge Embed Examples\n")
        examples.append("### Weekly Growth")
        examples.append(f"![Weekly Growth]({base_url}?url={repo_badges_url}/weekly_growth.json)")
        examples.append("")

        examples.append("### Top Hunters")
        examples.append(f"![Top Hunters]({base_url}?url={repo_badges_url}/top_hunters.json)")
        examples.append("")

        examples.append("### Markdown Format")
        examples.append("```markdown")
        examples.append(f"[![Rustchain Weekly]({base_url}?url={repo_badges_url}/weekly_growth.json)](https://github.com/Scottcjn/Rustchain)")
        examples.append("```")

        return examples
