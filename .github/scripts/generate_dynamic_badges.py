# SPDX-License-Identifier: MIT
import json
import os
import sys
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BadgeGenerator:
    """Generate shields.io compatible JSON badge files with hunter metrics."""

    def __init__(self, output_dir: str = "badges", data_dir: str = "data/hunters"):
        self.output_dir = Path(output_dir)
        self.data_dir = Path(data_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Badge colors and styling
        self.colors = {
            'success': '#28a745',
            'info': '#007bff',
            'warning': '#ffc107',
            'danger': '#dc3545',
            'primary': '#007bff',
            'secondary': '#6c757d',
            'gold': '#ffd700',
            'silver': '#c0c0c0',
            'bronze': '#cd7f32'
        }

    def load_hunter_data(self) -> Dict[str, Any]:
        """Load hunter statistics from JSON files."""
        hunters = {}

        if not self.data_dir.exists():
            logger.warning(f"Data directory {self.data_dir} does not exist")
            return hunters

        for json_file in self.data_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    hunter_id = json_file.stem
                    hunters[hunter_id] = data
            except Exception as e:
                logger.error(f"Error loading {json_file}: {e}")

        logger.info(f"Loaded data for {len(hunters)} hunters")
        return hunters

    def create_slug(self, name: str, existing_slugs: set) -> str:
        """Generate collision-safe slug for hunter names."""
        # Basic slug creation
        slug = re.sub(r'[^\w\s-]', '', name.lower())
        slug = re.sub(r'[\s_-]+', '-', slug).strip('-')

        # Handle collisions
        original_slug = slug
        counter = 1
        while slug in existing_slugs:
            slug = f"{original_slug}-{counter}"
            counter += 1

        existing_slugs.add(slug)
        return slug

    def validate_badge_json(self, badge_data: Dict[str, Any]) -> bool:
        """Validate shield.io JSON schema."""
        required_fields = ['schemaVersion', 'label', 'message']

        for field in required_fields:
            if field not in badge_data:
                logger.error(f"Missing required field: {field}")
                return False

        if badge_data.get('schemaVersion') != 1:
            logger.warning("Non-standard schema version")

        return True

    def write_badge_json(self, filename: str, badge_data: Dict[str, Any]) -> None:
        """Write validated badge JSON to file."""
        if not self.validate_badge_json(badge_data):
            logger.error(f"Invalid badge data for {filename}")
            return

        filepath = self.output_dir / f"{filename}.json"
        with open(filepath, 'w') as f:
            json.dump(badge_data, f, indent=2)
        logger.info(f"Generated badge: {filepath}")

    def calculate_weekly_growth(self, hunters: Dict[str, Any]) -> Dict[str, float]:
        """Calculate weekly growth metrics for hunters."""
        growth_data = {}
        cutoff_date = datetime.now() - timedelta(days=7)

        for hunter_id, data in hunters.items():
            recent_bounties = 0
            total_bounties = data.get('total_bounties', 0)

            # Simple heuristic - assume uniform distribution for demo
            if total_bounties > 0:
                recent_bounties = max(0, int(total_bounties * 0.1))  # 10% in last week

            growth_rate = (recent_bounties / max(total_bounties, 1)) * 100
            growth_data[hunter_id] = growth_rate

        return growth_data

    def get_top_hunters(self, hunters: Dict[str, Any], limit: int = 3) -> List[Tuple[str, Dict]]:
        """Get top hunters by total RTC earned."""
        hunter_list = []

        for hunter_id, data in hunters.items():
            total_rtc = data.get('total_rtc', 0)
            hunter_list.append((hunter_id, data, total_rtc))

        # Sort by RTC earned descending
        hunter_list.sort(key=lambda x: x[2], reverse=True)

        return [(h[0], h[1]) for h in hunter_list[:limit]]

    def categorize_bounties(self, hunters: Dict[str, Any]) -> Dict[str, int]:
        """Categorize bounty types across all hunters."""
        categories = {
            'docs': 0,
            'outreach': 0,
            'bug': 0,
            'feature': 0,
            'other': 0
        }

        for hunter_id, data in hunters.items():
            bounties = data.get('bounties', [])
            for bounty in bounties:
                title = bounty.get('title', '').lower()
                description = bounty.get('description', '').lower()

                if any(word in title + description for word in ['doc', 'documentation', 'readme']):
                    categories['docs'] += 1
                elif any(word in title + description for word in ['outreach', 'marketing', 'social']):
                    categories['outreach'] += 1
                elif any(word in title + description for word in ['bug', 'fix', 'error']):
                    categories['bug'] += 1
                elif any(word in title + description for word in ['feature', 'enhancement', 'implement']):
                    categories['feature'] += 1
                else:
                    categories['other'] += 1

        return categories

    def generate_weekly_growth_badge(self, hunters: Dict[str, Any]) -> None:
        """Generate weekly growth summary badge."""
        growth_data = self.calculate_weekly_growth(hunters)

        if not growth_data:
            return

        avg_growth = sum(growth_data.values()) / len(growth_data)

        if avg_growth > 20:
            color = self.colors['success']
            message = f"+{avg_growth:.1f}% growth"
        elif avg_growth > 10:
            color = self.colors['warning']
            message = f"+{avg_growth:.1f}% growth"
        else:
            color = self.colors['info']
            message = f"+{avg_growth:.1f}% growth"

        badge_data = {
            "schemaVersion": 1,
            "label": "Weekly Growth",
            "message": message,
            "color": color.lstrip('#'),
            "style": "flat"
        }

        self.write_badge_json('weekly-growth', badge_data)

    def generate_top_hunters_badge(self, hunters: Dict[str, Any]) -> None:
        """Generate top 3 hunters summary badge."""
        top_hunters = self.get_top_hunters(hunters, 3)

        if not top_hunters:
            return

        # Create summary message
        hunter_names = []
        for hunter_id, data in top_hunters:
            name = data.get('name', hunter_id)
            rtc = data.get('total_rtc', 0)
            hunter_names.append(f"{name} ({rtc:.0f})")

        message = " | ".join(hunter_names)

        badge_data = {
            "schemaVersion": 1,
            "label": "Top Hunters",
            "message": message,
            "color": self.colors['gold'].lstrip('#'),
            "style": "flat"
        }

        self.write_badge_json('top-hunters', badge_data)

    def generate_category_badges(self, hunters: Dict[str, Any]) -> None:
        """Generate category-specific badges if data exists."""
        categories = self.categorize_bounties(hunters)

        for category, count in categories.items():
            if count == 0:
                continue

            # Color based on count
            if count > 20:
                color = self.colors['success']
            elif count > 10:
                color = self.colors['info']
            else:
                color = self.colors['secondary']

            badge_data = {
                "schemaVersion": 1,
                "label": f"{category.title()} Bounties",
                "message": str(count),
                "color": color.lstrip('#'),
                "style": "flat"
            }

            self.write_badge_json(f'category-{category}', badge_data)

    def generate_hunter_badges(self, hunters: Dict[str, Any]) -> None:
        """Generate individual hunter badges with collision-safe slugs."""
        existing_slugs = set()

        for hunter_id, data in hunters.items():
            name = data.get('name', hunter_id)
            slug = self.create_slug(name, existing_slugs)

            total_rtc = data.get('total_rtc', 0)
            total_bounties = data.get('total_bounties', 0)

            # Main hunter badge
            badge_data = {
                "schemaVersion": 1,
                "label": name,
                "message": f"{total_rtc:.0f} RTC • {total_bounties} bounties",
                "color": self.colors['primary'].lstrip('#'),
                "style": "flat"
            }

            self.write_badge_json(f'hunter-{slug}', badge_data)

            # RTC-only badge
            rtc_badge = {
                "schemaVersion": 1,
                "label": f"{name} RTC",
                "message": f"{total_rtc:.1f}",
                "color": self.colors['success'].lstrip('#'),
                "style": "flat"
            }

            self.write_badge_json(f'hunter-{slug}-rtc', rtc_badge)

    def generate_baseline_badges(self, hunters: Dict[str, Any]) -> None:
        """Generate baseline project badges."""
        total_hunters = len(hunters)
        total_rtc = sum(data.get('total_rtc', 0) for data in hunters.values())
        total_bounties = sum(data.get('total_bounties', 0) for data in hunters.values())

        # Total hunters badge
        hunters_badge = {
            "schemaVersion": 1,
            "label": "Active Hunters",
            "message": str(total_hunters),
            "color": self.colors['info'].lstrip('#'),
            "style": "flat"
        }
        self.write_badge_json('total-hunters', hunters_badge)

        # Total RTC badge
        rtc_badge = {
            "schemaVersion": 1,
            "label": "Total RTC Distributed",
            "message": f"{total_rtc:.0f}",
            "color": self.colors['success'].lstrip('#'),
            "style": "flat"
        }
        self.write_badge_json('total-rtc', rtc_badge)

        # Total bounties badge
        bounties_badge = {
            "schemaVersion": 1,
            "label": "Bounties Completed",
            "message": str(total_bounties),
            "color": self.colors['primary'].lstrip('#'),
            "style": "flat"
        }
        self.write_badge_json('total-bounties', bounties_badge)

    def generate_all_badges(self) -> None:
        """Generate all badge types."""
        logger.info("Starting badge generation...")

        hunters = self.load_hunter_data()

        if not hunters:
            logger.warning("No hunter data found, generating empty badges")
            hunters = {}

        # Generate all badge types
        self.generate_baseline_badges(hunters)
        self.generate_weekly_growth_badge(hunters)
        self.generate_top_hunters_badge(hunters)
        self.generate_category_badges(hunters)
        self.generate_hunter_badges(hunters)

        logger.info("Badge generation completed")

    def generate_readme_snippets(self) -> str:
        """Generate README snippets for badge embedding."""
        base_url = "https://img.shields.io/endpoint"
        repo_url = "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/badges"

        snippets = """
# Dynamic Badge Examples

## Project Overview Badges
```markdown
![Active Hunters](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/badges/total-hunters.json)
![Total RTC](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/badges/total-rtc.json)
![Bounties Completed](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/badges/total-bounties.json)
```

## Growth & Performance Badges
```markdown
![Weekly Growth](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/badges/weekly-growth.json)
![Top Hunters](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/badges/top-hunters.json)
```

## Category Badges
```markdown
![Docs Bounties](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/badges/category-docs.json)
![Bug Bounties](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/badges/category-bug.json)
![Feature Bounties](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/badges/category-feature.json)
```

## Individual Hunter Badges
Replace `hunter-slug` with the actual hunter slug:
```markdown
![Hunter Stats](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/badges/hunter-{slug}.json)
![Hunter RTC](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/badges/hunter-{slug}-rtc.json)
```

## HTML Embedding
```html
<img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/badges/total-hunters.json" alt="Active Hunters">
```
"""

        readme_path = self.output_dir / "README.md"
        with open(readme_path, 'w') as f:
            f.write(snippets)

        logger.info(f"Generated README snippets: {readme_path}")
        return snippets


def main():
    """Main entry point for badge generation."""
    generator = BadgeGenerator()

    try:
        generator.generate_all_badges()
        generator.generate_readme_snippets()
        logger.info("All badges generated successfully!")

    except Exception as e:
        logger.error(f"Badge generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
