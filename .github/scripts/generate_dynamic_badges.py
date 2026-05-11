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
    - category_<name>.json    — Per-category bounty count for categories in data
    - hunter_<slug>.json      — Per-hunter badge (collision-safe slug)
"""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


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
    names = " | ".join(
        f"{h.get('name', '?')} ({h.get('total_rtc', 0)})"
        for h in top3
    )
    return badge("🏆 Top Hunters", names, COLORS["gold"])


def generate_category_badge(category: str, count: int) -> dict:
    """Category-specific badge (docs, outreach, bugs, etc.)."""
    label, color = CATEGORY_LABELS.get(category, (f"{category} Bounties", COLORS["grey"]))
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


# ── Validation ───────────────────────────────────────────────────────


def validate_badge(b: dict) -> List[str]:
    """Validate a badge dict against the shields.io endpoint schema.

    Returns list of errors (empty = valid).
    """
    errors: list[str] = []
    if b.get("schemaVersion") != 1:
        errors.append(f"schemaVersion must be 1, got {b.get('schemaVersion')}")
    if not b.get("label"):
        errors.append("label is required and must be non-empty")
    if "message" not in b:
        errors.append("message is required")
    if not isinstance(b.get("message"), str):
        errors.append(f"message must be string, got {type(b.get('message'))}")
    return errors


# ── Main ─────────────────────────────────────────────────────────────


def generate_all_badges(data: dict, output_dir: str = ".github/badges") -> List[str]:
    """Generate all badge JSON files. Returns list of written paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    written: list[str] = []

    # 1. Network status
    _write(out / "network_status.json", generate_network_status_badge(data), written)

    # 2. Total bounties
    _write(out / "total_bounties.json", generate_total_bounties_badge(data), written)

    # 3. Weekly growth
    _write(out / "weekly_growth.json", generate_weekly_growth_badge(data), written)

    # 4. Top hunters summary
    _write(
        out / "top_hunters.json",
        generate_top_hunters_badge(data.get("hunters", [])),
        written,
    )

    # 5. Category badges
    for cat, count in data.get("categories", {}).items():
        if count > 0:
            _write(
                out / f"category_{cat}.json",
                generate_category_badge(cat, count),
                written,
            )

    # 6. Per-hunter badges (collision-safe slugs)
    slugs_seen: set[str] = set()
    for hunter in data.get("hunters", []):
        slug = make_slug(hunter.get("name", "unknown"))
        # Extra collision safety: append counter if duplicate
        base_slug = slug
        counter = 2
        while slug in slugs_seen:
            slug = f"{base_slug}-{counter}"
            counter += 1
        slugs_seen.add(slug)

        _write(out / f"hunter_{slug}.json", generate_hunter_badge(hunter), written)

    # Write manifest
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "badge_count": len(written),
        "badges": [os.path.basename(p) for p in written],
        "schema_version": BADGE_SCHEMA_VERSION,
    }
    manifest_path = str(out / "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    written.append(manifest_path)

    return written


def _write(path: Path, badge_data: dict, written: list) -> None:
    """Write badge JSON after validation."""
    errors = validate_badge(badge_data)
    if errors:
        print(f"WARN: Skipping {path.name}: {errors}", file=sys.stderr)
        return
    with open(path, "w") as f:
        json.dump(badge_data, f, indent=2)
    written.append(str(path))


def main():
    parser = argparse.ArgumentParser(description="Generate dynamic shields.io badges")
    parser.add_argument("--data-file", help="Path to bounty data JSON")
    parser.add_argument(
        "--output-dir", default=".github/badges", help="Output directory"
    )
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing badges")
    args = parser.parse_args()

    if args.validate_only:
        badge_dir = Path(args.output_dir)
        if not badge_dir.exists():
            print("No badges directory found")
            sys.exit(1)
        errors_total = 0
        for f in sorted(badge_dir.glob("*.json")):
            if f.name == "manifest.json":
                continue
            with open(f) as fh:
                data = json.load(fh)
            errs = validate_badge(data)
            if errs:
                print(f"FAIL {f.name}: {errs}")
                errors_total += len(errs)
            else:
                print(f"OK   {f.name}")
        sys.exit(1 if errors_total else 0)

    data = load_data(args.data_file)
    written = generate_all_badges(data, args.output_dir)
    print(f"Generated {len(written)} badge files in {args.output_dir}/")
    for path in written:
        print(f"  {path}")


if __name__ == "__main__":
    main()
