#!/usr/bin/env python3
"""
Dynamic Shields Badge Generator v2

Generates shields.io-compatible JSON badge endpoints for the RustChain
bounty program. Badges are written to .github/badges/ and served via
GitHub raw URLs.

Usage:
    python .github/scripts/generate_dynamic_badges.py
    python .github/scripts/generate_dynamic_badges.py --data-file bounty_data.json
    python .github/scripts/generate_dynamic_badges.py --output-dir .github/badges

Badge types:
    - network_status.json     — Network health badge
    - total_bounties.json     — Total bounties paid out
    - weekly_growth.json      — Weekly growth percentage
    - top_hunters.json        — Top 3 bounty hunters summary
    - category_docs.json      — Documentation bounties count
    - category_outreach.json  — Outreach/community bounties count
    - category_bugs.json      — Bug bounties count
    - hunter_<slug>.json      — Per-hunter badge (collision-safe slug)
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional


# ── Badge schema ─────────────────────────────────────────────────────

BADGE_SCHEMA_VERSION = 1

# shields.io endpoint badge format
# https://shields.io/badges/endpoint-badge
BADGE_TEMPLATE = {
    "schemaVersion": 1,
    "label": "",
    "message": "",
    "color": "brightgreen",
    "style": "flat-square",
}

COLORS = {
    "green": "brightgreen",
    "blue": "007ec6",
    "orange": "orange",
    "red": "e05d44",
    "yellow": "dfb317",
    "purple": "9f66cc",
    "grey": "555",
    "gold": "f5a623",
}

CATEGORY_LABELS = {
    "docs": ("📝 Docs Bounties", COLORS["blue"]),
    "outreach": ("📣 Outreach Bounties", COLORS["purple"]),
    "bugs": ("🐛 Bug Bounties", COLORS["red"]),
    "security": ("🔒 Security Bounties", COLORS["orange"]),
    "feature": ("⚡ Feature Bounties", COLORS["green"]),
}


# ── Slug generation (collision-safe) ─────────────────────────────────


def make_slug(name: str) -> str:
    """Generate a URL-safe, collision-resistant slug from a hunter name.

    Rules:
    1. Lowercase
    2. Replace non-alphanumeric with hyphens
    3. Collapse multiple hyphens
    4. Strip leading/trailing hyphens
    5. Append 4-char hash suffix for collision safety
    """
    slug = re.sub(r"[^a-z0-9]", "-", name.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        slug = "unknown"
    # Append short hash for collision safety
    h = hashlib.sha256(name.encode()).hexdigest()[:4]
    return f"{slug}-{h}"


# ── Badge generators ─────────────────────────────────────────────────


def badge(label: str, message: str, color: str = "brightgreen", **extra) -> dict:
    """Create a shields.io endpoint badge dict."""
    b = dict(BADGE_TEMPLATE)
    b["label"] = label
    b["message"] = str(message)
    b["color"] = color
    b.update(extra)
    return b


def generate_network_status_badge(data: dict) -> dict:
    """Network health status badge."""
    status = data.get("network_status", "unknown")
    color = {"healthy": COLORS["green"], "degraded": COLORS["yellow"]}.get(
        status, COLORS["grey"]
    )
    return badge("RustChain", status.capitalize(), color)


def generate_total_bounties_badge(data: dict) -> dict:
    """Total RTC paid out badge."""
    total = data.get("total_rtc_paid", 0)
    return badge("Bounties Paid", f"{total:,} RTC", COLORS["gold"])


def generate_weekly_growth_badge(data: dict) -> dict:
    """Weekly growth percentage badge."""
    growth = data.get("weekly_growth_pct", 0.0)
    if growth > 0:
        msg = f"+{growth:.1f}%"
        color = COLORS["green"]
    elif growth < 0:
        msg = f"{growth:.1f}%"
        color = COLORS["red"]
    else:
        msg = "0%"
        color = COLORS["grey"]
    return badge("Weekly Growth", msg, color)


def generate_top_hunters_badge(hunters: List[dict]) -> dict:
    """Top 3 hunters summary badge."""
    if not hunters:
        return badge("Top Hunters", "none yet", COLORS["grey"])
    top3 = sorted(hunters, key=lambda h: h.get("total_rtc", 0), reverse=True)[:3]
    names = " | ".join(f"{h.get('name', '?')} ({h.get('total_rtc', 0)})" for h in top3)
    return badge("🏆 Top Hunters", names, COLORS["gold"])


def generate_category_badge(category: str, count: int) -> dict:
    """Category-specific badge (docs, outreach, bugs, etc.)."""
    label, color = CATEGORY_LABELS.get(
        category, (f"{category} Bounties", COLORS["grey"])
    )
    return badge(label, str(count), color)


def generate_hunter_badge(hunter: dict) -> dict:
    """Per-hunter badge with total RTC and rank."""
    name = hunter.get("name", "Unknown")
    rtc = hunter.get("total_rtc", 0)
    rank = hunter.get("rank", "?")
    prs = hunter.get("merged_prs", 0)
    return badge(
        f"🎯 {name}",
        f"#{rank} • {rtc} RTC • {prs} PRs",
        COLORS["blue"],
    )


# ── Data loading ─────────────────────────────────────────────────────


def load_data(data_file: Optional[str] = None) -> dict:
    """Load bounty data from file or generate sample data."""
    if data_file and Path(data_file).exists():
        with open(data_file) as f:
            return json.load(f)

    # Generate from CONTRIBUTORS.md and git history if available
    data = {
        "network_status": "healthy",
        "total_rtc_paid": 0,
        "weekly_growth_pct": 0.0,
        "hunters": [],
        "categories": {},
    }

    # Try to parse CONTRIBUTORS.md for hunter data
    contributors_path = Path("CONTRIBUTORS.md")
    if contributors_path.exists():
        data["hunters"] = _parse_contributors(contributors_path.read_text())

    # Try to count bounty issues by category
    bounties_dir = Path("bounties")
    if bounties_dir.exists():
        data["categories"] = _count_categories(bounties_dir)

    return data


def _parse_contributors(text: str) -> List[dict]:
    """Parse CONTRIBUTORS.md for hunter names and RTC amounts."""
    hunters: Dict[str, dict] = {}
    # Match patterns like "| @username | 150 RTC |" or "- @username — 150 RTC"
    patterns = [
        re.compile(r"\|\s*@?(\S+)\s*\|\s*(\d+(?:\.\d+)?)\s*RTC\s*\|"),
        re.compile(r"[-*]\s*@?(\S+)\s*[-—]\s*(\d+(?:\.\d+)?)\s*RTC"),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            name = match.group(1).strip()
            rtc = float(match.group(2))
            if name in hunters:
                hunters[name]["total_rtc"] += rtc
                hunters[name]["merged_prs"] += 1
            else:
                hunters[name] = {"name": name, "total_rtc": rtc, "merged_prs": 1}

    # Sort and assign ranks
    ranked = sorted(hunters.values(), key=lambda h: h["total_rtc"], reverse=True)
    for i, h in enumerate(ranked):
        h["rank"] = i + 1

    return ranked


def _count_categories(bounties_dir: Path) -> Dict[str, int]:
    """Count bounties by category from directory structure."""
    cats: Dict[str, int] = Counter()
    for item in bounties_dir.iterdir():
        if item.is_dir():
            name = item.name.lower()
            if "doc" in name:
                cats["docs"] += 1
            elif "outreach" in name or "community" in name:
                cats["outreach"] += 1
            elif "bug" in name:
                cats["bugs"] += 1
            elif "security" in name or "red-team" in name:
                cats["security"] += 1
            else:
                cats["feature"] += 1
    return dict(cats)


# ── Main badge generation ─────────────────────────────────────────────


def generate_all_badges(data: dict, output_dir: Path) -> None:
    """Generate all badge types and save to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # System badges
    badges = {
        "network_status.json": generate_network_status_badge(data),
        "total_bounties.json": generate_total_bounties_badge(data),
        "weekly_growth.json": generate_weekly_growth_badge(data),
        "top_hunters.json": generate_top_hunters_badge(data.get("hunters", [])),
    }

    # Category badges
    categories = data.get("categories", {})
    for category, count in categories.items():
        badges[f"category_{category}.json"] = generate_category_badge(category, count)

    # Per-hunter badges
    for hunter in data.get("hunters", []):
        slug = make_slug(hunter.get("name", "unknown"))
        badges[f"hunter_{slug}.json"] = generate_hunter_badge(hunter)

    # Write all badges
    for filename, badge_data in badges.items():
        badge_path = output_dir / filename
        with open(badge_path, "w") as f:
            json.dump(badge_data, f, indent=2)
        print(f"Generated: {badge_path}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate dynamic shields.io badges for RustChain bounty program"
    )
    parser.add_argument(
        "--data-file", help="Path to JSON data file (default: auto-detect from repo)"
    )
    parser.add_argument(
        "--output-dir",
        default=".github/badges",
        help="Output directory for badge JSON files (default: .github/badges)",
    )

    args = parser.parse_args()

    try:
        data = load_data(args.data_file)
        output_dir = Path(args.output_dir)
        generate_all_badges(data, output_dir)
        print(f"✅ Successfully generated badges in {output_dir}")
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
