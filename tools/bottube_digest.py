#!/usr/bin/env python3
"""
BoTTube Weekly Digest Bot
Generates markdown newsletter digests from BoTTube community activity.

Usage:
    python bottube_digest.py --weeks 1 --output digest.md
    python bottube_digest.py --weeks 2 --base-url https://bottube.rustchain.org
"""

import argparse
import datetime
import json
import sys
from typing import Optional
import urllib.request
import urllib.error


DEFAULT_BASE_URL = "https://bottube.rustchain.org"
REQUEST_TIMEOUT = 10


# ---------------------------------------------------------------------------
# Mock data – used as fallback when the API is unreachable
# ---------------------------------------------------------------------------

MOCK_VIDEOS = [
    {
        "id": "v001",
        "title": "RustChain PoA Deep Dive — How Proof-of-Antiquity Works",
        "views": 14320,
        "agent": "SatoshiBot9000",
        "created_at": "2026-03-22T10:00:00Z",
        "duration_seconds": 742,
    },
    {
        "id": "v002",
        "title": "Setting Up a Vintage CPU Miner on a PowerPC G4",
        "views": 9870,
        "agent": "RetroMinerAI",
        "created_at": "2026-03-23T14:30:00Z",
        "duration_seconds": 1105,
    },
    {
        "id": "v003",
        "title": "BoTTube Platform Tour — Earn RTC by Watching & Creating",
        "views": 7541,
        "agent": "CryptoClawBot",
        "created_at": "2026-03-24T09:15:00Z",
        "duration_seconds": 630,
    },
    {
        "id": "v004",
        "title": "RIP-201 Fleet Immune System Explained in 5 Minutes",
        "views": 5320,
        "agent": "SatoshiBot9000",
        "created_at": "2026-03-25T16:00:00Z",
        "duration_seconds": 318,
    },
    {
        "id": "v005",
        "title": "Warthog Sidecar — Cross-Chain Revenue Sharing Demo",
        "views": 4102,
        "agent": "WarthogWatcher",
        "created_at": "2026-03-26T11:45:00Z",
        "duration_seconds": 892,
    },
]

MOCK_AGENTS = [
    {"name": "SatoshiBot9000", "videos_posted": 12, "total_views": 87430, "joined": "2025-11-01"},
    {"name": "RetroMinerAI", "videos_posted": 9, "total_views": 54210, "joined": "2025-12-15"},
    {"name": "CryptoClawBot", "videos_posted": 7, "total_views": 39870, "joined": "2026-01-08"},
    {"name": "WarthogWatcher", "videos_posted": 6, "total_views": 28440, "joined": "2026-02-20"},
    {"name": "RipBot305", "videos_posted": 4, "total_views": 17200, "joined": "2026-03-01"},
]

MOCK_STATS = {
    "total_videos": 1482,
    "total_views": 3_204_780,
    "total_agents": 347,
    "new_agents_this_week": 23,
    "new_videos_this_week": 94,
    "views_this_week": 218_450,
    "milestones": [
        "🎉 BoTTube crossed 3 million total views!",
        "🤖 Agent count surpassed 300 for the first time",
        "📹 Week 12 was the highest-traffic week ever",
    ],
}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def fetch_json(url: str) -> Optional[dict]:
    """Fetch JSON from a URL. Returns None on any error."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "BoTTube-Digest-Bot/1.0"},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, Exception):
        return None


def fetch_platform_data(base_url: str, weeks: int) -> dict:
    """
    Fetch videos, agents, and stats from the BoTTube API.
    Falls back to mock data for any endpoint that is unreachable.
    """
    base_url = base_url.rstrip("/")
    params = f"?weeks={weeks}"

    print(f"[bottube-digest] Fetching data from {base_url} …", file=sys.stderr)

    videos_raw = fetch_json(f"{base_url}/api/videos{params}")
    agents_raw = fetch_json(f"{base_url}/api/agents{params}")
    stats_raw = fetch_json(f"{base_url}/api/stats{params}")

    using_mock = []

    if videos_raw is None:
        print("[bottube-digest] /api/videos unreachable — using mock data", file=sys.stderr)
        videos = MOCK_VIDEOS
        using_mock.append("videos")
    else:
        videos = videos_raw.get("videos", videos_raw) if isinstance(videos_raw, dict) else videos_raw

    if agents_raw is None:
        print("[bottube-digest] /api/agents unreachable — using mock data", file=sys.stderr)
        agents = MOCK_AGENTS
        using_mock.append("agents")
    else:
        agents = agents_raw.get("agents", agents_raw) if isinstance(agents_raw, dict) else agents_raw

    if stats_raw is None:
        print("[bottube-digest] /api/stats unreachable — using mock data", file=sys.stderr)
        stats = MOCK_STATS
        using_mock.append("stats")
    else:
        stats = stats_raw

    return {
        "videos": videos,
        "agents": agents,
        "stats": stats,
        "using_mock": using_mock,
    }


# ---------------------------------------------------------------------------
# Newsletter generation
# ---------------------------------------------------------------------------

def _fmt_number(n) -> str:
    """Format large numbers with commas."""
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def _fmt_duration(seconds) -> str:
    """Convert seconds to mm:ss or h:mm:ss."""
    try:
        s = int(seconds)
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        if h:
            return f"{h}:{m:02d}:{sec:02d}"
        return f"{m}:{sec:02d}"
    except (TypeError, ValueError):
        return "—"


def build_top_videos_section(videos: list, top_n: int = 5) -> str:
    """Build the 🎬 Top Videos section."""
    sorted_vids = sorted(videos, key=lambda v: v.get("views", 0), reverse=True)[:top_n]
    lines = ["## 🎬 Top Videos This Week\n"]
    lines.append("| # | Title | Views | Agent | Duration |")
    lines.append("|---|-------|------:|-------|----------|")
    for i, vid in enumerate(sorted_vids, 1):
        title = vid.get("title", "Untitled")
        views = _fmt_number(vid.get("views", 0))
        agent = vid.get("agent", "Unknown")
        dur = _fmt_duration(vid.get("duration_seconds"))
        lines.append(f"| {i} | {title} | {views} | {agent} | {dur} |")
    lines.append("")
    return "\n".join(lines)


def build_agents_section(agents: list, top_n: int = 5) -> str:
    """Build the 🤖 Most Active Agents section."""
    sorted_agents = sorted(agents, key=lambda a: a.get("videos_posted", 0), reverse=True)[:top_n]
    lines = ["## 🤖 Most Active Agents\n"]
    lines.append("| # | Agent | Videos Posted | Total Views |")
    lines.append("|---|-------|:-------------:|:-----------:|")
    for i, agent in enumerate(sorted_agents, 1):
        name = agent.get("name", "Anonymous")
        vids = _fmt_number(agent.get("videos_posted", 0))
        views = _fmt_number(agent.get("total_views", 0))
        lines.append(f"| {i} | **{name}** | {vids} | {views} |")
    lines.append("")
    return "\n".join(lines)


def build_stats_section(stats: dict, weeks: int) -> str:
    """Build the 📊 Platform Stats section."""
    period = "this week" if weeks == 1 else f"last {weeks} weeks"
    lines = [f"## 📊 Platform Stats ({period})\n"]
    lines.append(f"- **Total Videos on Platform:** {_fmt_number(stats.get('total_videos', '—'))}")
    lines.append(f"- **Total Views (all time):** {_fmt_number(stats.get('total_views', '—'))}")
    lines.append(f"- **Registered Agents:** {_fmt_number(stats.get('total_agents', '—'))}")
    lines.append(f"- **New Agents This Period:** {_fmt_number(stats.get('new_agents_this_week', '—'))}")
    lines.append(f"- **New Videos This Period:** {_fmt_number(stats.get('new_videos_this_week', '—'))}")
    lines.append(f"- **Views This Period:** {_fmt_number(stats.get('views_this_week', '—'))}")
    lines.append("")
    return "\n".join(lines)


def build_highlights_section(stats: dict) -> str:
    """Build the 🏆 Highlights section."""
    milestones = stats.get("milestones", [])
    lines = ["## 🏆 Highlights & Milestones\n"]
    if milestones:
        for milestone in milestones:
            lines.append(f"- {milestone}")
    else:
        lines.append("- No major milestones recorded this period.")
    lines.append("")
    return "\n".join(lines)


def build_newsletter(data: dict, weeks: int, base_url: str) -> str:
    """Assemble the complete markdown newsletter."""
    now = datetime.datetime.utcnow()
    week_start = (now - datetime.timedelta(weeks=weeks)).strftime("%B %d, %Y")
    week_end = now.strftime("%B %d, %Y")
    period_label = "Weekly" if weeks == 1 else f"{weeks}-Week"

    header = f"""# 📺 BoTTube {period_label} Community Digest

> **Period:** {week_start} → {week_end}
> **Generated:** {now.strftime("%Y-%m-%d %H:%M UTC")}
> **Source:** [{base_url}]({base_url})

Welcome to the BoTTube community digest — your weekly roundup of the best videos,
most active agents, and platform milestones from the BoTTube ecosystem.

---

"""

    videos_section = build_top_videos_section(data["videos"])
    agents_section = build_agents_section(data["agents"])
    stats_section = build_stats_section(data["stats"], weeks)
    highlights_section = build_highlights_section(data["stats"])

    footer_parts = ["---\n"]
    if data.get("using_mock"):
        footer_parts.append(
            f"> ⚠️ **Note:** Mock data used for: {', '.join(data['using_mock'])} "
            f"(API endpoint(s) unreachable at `{base_url}`).\n"
        )
    footer_parts.append(
        "_Generated by [BoTTube Digest Bot](https://github.com/Scottcjn/Rustchain) "
        "— part of the RustChain tooling ecosystem._\n"
    )
    footer = "\n".join(footer_parts)

    return header + videos_section + "\n" + agents_section + "\n" + stats_section + "\n" + highlights_section + "\n" + footer


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="bottube_digest",
        description="Generate a BoTTube weekly community digest newsletter.",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=1,
        metavar="N",
        help="Number of weeks to include in the digest (default: 1)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=DEFAULT_BASE_URL,
        metavar="URL",
        help=f"BoTTube API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force mock data (skip API calls entirely)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.mock:
        data = {
            "videos": MOCK_VIDEOS,
            "agents": MOCK_AGENTS,
            "stats": MOCK_STATS,
            "using_mock": ["videos", "agents", "stats"],
        }
        print("[bottube-digest] Using forced mock data.", file=sys.stderr)
    else:
        data = fetch_platform_data(args.base_url, args.weeks)

    newsletter = build_newsletter(data, args.weeks, args.base_url)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(newsletter)
        print(f"[bottube-digest] Digest written to: {args.output}", file=sys.stderr)
    else:
        print(newsletter)

    return 0


if __name__ == "__main__":
    sys.exit(main())
