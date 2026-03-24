#!/usr/bin/env python3
"""
RustChain Contributor Tier Analyzer

Analyzes the current bounty ledger data to show which existing contributors
would be placed at which tier under the proposed RIP-306 tier system.

Data source: wallet registry from CLAUDE.md / memory files (2026-03-17 snapshot).
In production, this would query the bounty_ledger table in rustchain_v2.db.

Usage:
    python3 analyze_tiers.py
    python3 analyze_tiers.py --csv          # Output as CSV
    python3 analyze_tiers.py --tier gold    # Filter to one tier
"""

import argparse
import sys
from dataclasses import dataclass
from typing import List, Optional

# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------

TIERS = {
    "platinum": {"threshold": 1000, "multiplier": 1.5, "color": "\033[97m"},   # bright white
    "gold":     {"threshold": 500,  "multiplier": 1.2, "color": "\033[93m"},   # yellow
    "silver":   {"threshold": 200,  "multiplier": 1.1, "color": "\033[37m"},   # light gray
    "bronze":   {"threshold": 50,   "multiplier": 1.0, "color": "\033[33m"},   # brown/dark yellow
    "untiered": {"threshold": 0,    "multiplier": 1.0, "color": "\033[90m"},   # dark gray
}

RESET = "\033[0m"


def classify(total_rtc: float) -> str:
    if total_rtc >= 1000:
        return "platinum"
    elif total_rtc >= 500:
        return "gold"
    elif total_rtc >= 200:
        return "silver"
    elif total_rtc >= 50:
        return "bronze"
    return "untiered"


# ---------------------------------------------------------------------------
# Known contributor data (from wallet registry 2026-03-17)
# ---------------------------------------------------------------------------

@dataclass
class Contributor:
    github: str
    wallet: str
    total_rtc: float
    notes: str = ""


# All contributors with known payment amounts from the wallet registry
CONTRIBUTORS: List[Contributor] = [
    # Platinum (1000+)
    Contributor("createkr",             "createkr",             3122,   "Top contributor, Node 4 operator"),
    Contributor("simplereally",         "simplereally",         1075,   "Early contributor"),
    Contributor("mtarcure",             "wirework",             974,    "OTC Bridge, Agent Economy, Red Team"),

    # Gold (500-999)
    Contributor("davidtang-codex",      "davidtang-codex",      921,    "Codex agent work"),
    Contributor("zhanglinqian",         "zhanglinqian",         755,    "Engagement"),
    Contributor("liu971227-sys",        "RTCa320f43...",        550,    "Security researcher, RIP-201"),
    Contributor("noxxxxybot/dayi1000",  "nox-ventures",         550,    "Stars, articles, upload bot, Rust wallet"),
    Contributor("BuilderFred",          "BuilderFred",          543,    "Security audit, 6 vulns found"),

    # Silver (200-499)
    Contributor("LaphoqueRC",           "(estimated)",          429,    "17 real merges, Sanctuary success"),
    Contributor("ArokyaMatthew",        "(awaiting wallet)",    340,    "SophiaCore merged, 8/10 best submission"),
    Contributor("godong0128",           "RTCd7b7dd20...",       330,    "Star King, full engagement 3.0x"),
    Contributor("ansomeck",             "RTCf4c3ff0e...",       327,    "2016 account, bounties"),
    Contributor("erdogan98",            "erdogan98",            315,    "Contributions"),
    Contributor("John Reed (Garrison)", "john-reed-garrison",   250,    "Ambassador+Support"),
    Contributor("ALLSTARETC111",        "RTC74312293...",       200,    "Found critical 5.0x arch escalation"),
    Contributor("edisonlv",             "claw",                 209,    "Dashboard, Prometheus, HallOfFame"),

    # Bronze (50-199)
    Contributor("krishna2918",          "krishna2918",          175,    "Python SDK bounty #36"),
    Contributor("CelebrityPunks",       "RTC5ec5adcb...",       129,    "Discord/Telegram bots, trading cards"),
    Contributor("jiangyj545",           "atlas-agent-01",       126,    "Stars + bounties"),
    Contributor("lopieloo",             "lopieloo",             125,    "Sophia N64 3D model"),
    Contributor("believening",          "believening-wallet",   125,    "Stars + follow"),
    Contributor("energypantry",         "energypantry",         110,    "Contributions"),
    Contributor("nicepopo86-lang",      "nicepopo86-lang",      109.5,  "Stars + bounties"),
    Contributor("newffnow",             "newffnow-github",      100,    "Stars, good templates"),
    Contributor("Joshualover",          "joshualover-dev",      99,     "Spanish translation, First Blood"),
    Contributor("SASAMITTRRR",          "RTCd02ce331...",       91,     "Stars"),
    Contributor("WeberG619",            "weberg619",            85,     "JS SDK, upload bot, MCP server"),
    Contributor("chienvon",             "RTCa3fffc3c...",       77,     "Stars + bounties"),
    Contributor("jojo-771771",          "claw-jojo-51658",      77,     "Bounties"),
    Contributor("952800710",            "pet9760",              74,     "49 stars + follow"),
    Contributor("JohnnieLZ",            "JohnnieLZ",            65.5,   "Stars + Q&A answers"),
    Contributor("Tianlin0725",          "tianlin-rtc",          60,     "Stars + follow"),
    Contributor("sososonia-cyber",      "sososonia-cyber",      52.5,   "SDK PR #580"),
    Contributor("allornothingai",       "(on file)",            51,     "7 PRs merged"),
    Contributor("ApextheBoss",          "ApextheBoss",          50,     "ElyanBus, incident_commander, CrewAI"),
    Contributor("skylovele",            "skylovele-wallet",     50,     "60 stars"),
    Contributor("Ivan-houzhiwen",       "Ivan-houzhiwen",       50,     "100 stars + follow"),
    Contributor("kolatrerionpu-hash",   "kolatrerionpu-hash",   50,     "Ghost miner PoC attempt"),
    Contributor("liangxu360427",        "RTC6026fa64...",       50,     "20 qualifying stars"),

    # Untiered (< 50 RTC) -- notable ones only
    Contributor("lustsazeus-lab",       "lustsazeus-lab",       48,     "Stars, beacon docs"),
    Contributor("mtarcure (alt)",       "RTCda6a6a21...",       43,     "WHY comments, Clippy"),
    Contributor("jujujuda",             "jujujuda",             20,     "CrewAI + tipbot merged"),
    Contributor("ziyuxuan84829",        "ziyuxuan84829",        20,     "Backup + epoch reporter"),
    Contributor("MadHHH",               "MadHHH",               15,     "Quickstart + bottube"),
    Contributor("Dlove123",             "RTCb72a1acc...",       15,     ""),
    Contributor("lonelinessprogrammer", "lonelinessprogrammer", 15,     "30 stars + follow"),
    Contributor("AdnanMehr8",           "RTCd9e5fdb6...",       15,     "Security fix beacon-skill"),
    Contributor("luxh1121",             "luxh1121",             15,     "Medium article"),
    Contributor("sungdark",             "sungdark",             16,     "Blog post + stars"),
    Contributor("ClawdEFS",             "bcn_clawd",            15.5,   "Stars"),
    Contributor("stevencao2020",        "RTC0b8b90dd...",       13,     ""),
    Contributor("justinleeyang",        "justinleeyang",        12,     "Postman + bottube"),
    Contributor("vita901",              "vita901",              12.5,   "100 stars first half"),
    Contributor("hwl66",                "miner-2025...",        10,     "Spanish README + bottube"),
    Contributor("M3nnoun",              "M3nnoun",              10,     "Bottube embed player"),
    Contributor("dunyuzoush-ch",        "dunyuzoush-ch",        10.5,   "21 stars + follow"),
    Contributor("danielalanbates",      "danielalanbates",      8,      "Beacon mesh, WCAG a11y"),
    Contributor("Dev-TechT",            "Dev-TechT",            8,      "Grazer edge-cases"),
    Contributor("xunwen-art",           "xunwen-art",           8,      "Beacon docs + test PRs"),
    Contributor("panicheart",           "panicheart",           7.5,    "30 stars"),
    Contributor("writsop",              "writsop",              7.5,    "30 stars"),
    Contributor("gutopro",              "gutopro",              7.5,    "30 stars"),
    Contributor("danker003",            "talant-dota",          5,      "Windows miner fingerprint bug"),
    Contributor("MontaEllis8",          "MontaEllis8",          5,      "DOI fix PR"),
    Contributor("668308",               "668308",               5,      "API walkthrough"),
    Contributor("dagangtj",             "RTCa7fce17f...",       5,      "Apple Silicon miner"),
    Contributor("capparun",             "RTCdcde4fc0...",       5,      ""),
    Contributor("bitProfessor",         "RTCb5b8333b...",       5,      ""),
    Contributor("kevin-undefined",      "RTCf2b7d18e...",       5,      ""),
    Contributor("zzjpython",            "zzjpython",            5,      ""),
    Contributor("flashlib",             "RTC20dafd06...",       5,      "Beacon registration"),
    Contributor("XxSnake",              "xiaosnake-bounty",     5.25,   "21 stars"),
    Contributor("KodeSage",             "(awaiting)",           5,      "Chicken in Every Pot"),
    Contributor("KimberleyOCaseyfv",    "RTCfe213f0d...",       4,      "Stars"),
    Contributor("fskeung",              "fskeung",              4,      "Beacon CI workflow"),
    Contributor("zddsl",                "zddsl-dev",            4,      "Templates"),
    Contributor("zhdtty",               "zhdtty",               3.5,    "7 stars + follow"),
    Contributor("manyrios",             "manyrios",             3.8,    "15 stars"),
    Contributor("idiottrader",          "idiottrader",          3.2,    "13 stars"),
    Contributor("cd333c",               "cd333c",               3,      "Russian README"),
    Contributor("forestlioooooo",       "forestlioooooo",       3,      "6 stars + follow"),
    Contributor("eyedark",              "eyedark",              3,      "Social graph tests"),
    Contributor("caohui-net",           "caohui-net",           5,      "Engagement"),
    Contributor("zhangxue1985122219",   "zhangxue1985...",      2,      "Beacon docs"),
    Contributor("nhanvu09",             "nhanvu09",             2,      "Bounties docs"),
    Contributor("addidea",              "addidea",              2,      "Bounties docs"),
    Contributor("pengjiequan-create",   "pengjiequan-create",   2,      "Bounties docs"),
    Contributor("Async777",             "Async777",             2,      "Beacon version fix"),
    Contributor("yay9096-hub",          "yay9096-hub",          2,      "Docs fixes"),
    Contributor("shuicici",             "RTC42c7f2e9...",       1,      "BoTTube review"),
    Contributor("yuanzhi20",            "yuanzhi20",            1,      "BoTTube review"),
]


def main():
    parser = argparse.ArgumentParser(description="Analyze RustChain contributor tiers")
    parser.add_argument("--csv", action="store_true", help="Output as CSV")
    parser.add_argument("--tier", type=str, help="Filter to specific tier (platinum/gold/silver/bronze/untiered)")
    args = parser.parse_args()

    # Classify all contributors
    for c in CONTRIBUTORS:
        c.tier = classify(c.total_rtc)
        c.multiplier = TIERS[c.tier]["multiplier"]

    # Filter if requested
    contributors = CONTRIBUTORS
    if args.tier:
        tier_filter = args.tier.lower()
        contributors = [c for c in CONTRIBUTORS if c.tier == tier_filter]

    if args.csv:
        print("github,wallet,total_rtc,tier,multiplier,notes")
        for c in sorted(contributors, key=lambda x: x.total_rtc, reverse=True):
            notes_escaped = c.notes.replace('"', '""')
            print(f'{c.github},{c.wallet},{c.total_rtc},{c.tier},{c.multiplier},"{notes_escaped}"')
        return

    # Terminal output with color
    tier_counts = {"platinum": 0, "gold": 0, "silver": 0, "bronze": 0, "untiered": 0}
    tier_rtc = {"platinum": 0.0, "gold": 0.0, "silver": 0.0, "bronze": 0.0, "untiered": 0.0}

    for c in CONTRIBUTORS:
        tier_counts[c.tier] += 1
        tier_rtc[c.tier] += c.total_rtc

    # Header
    print("=" * 78)
    print("  RustChain Contributor Tier Analysis (RIP-306)")
    print(f"  Data snapshot: 2026-03-24 | Total contributors: {len(CONTRIBUTORS)}")
    print(f"  Total RTC in ledger: 24,884.5 | Known wallets analyzed: {len(CONTRIBUTORS)}")
    print("=" * 78)
    print()

    # Summary table
    print("  TIER DISTRIBUTION")
    print("  " + "-" * 60)
    print(f"  {'Tier':<12} {'Count':>6} {'Total RTC':>12} {'Multiplier':>12}")
    print("  " + "-" * 60)
    for tier_name in ["platinum", "gold", "silver", "bronze", "untiered"]:
        color = TIERS[tier_name]["color"]
        mult = TIERS[tier_name]["multiplier"]
        print(f"  {color}{tier_name.upper():<12}{RESET} {tier_counts[tier_name]:>6} "
              f"{tier_rtc[tier_name]:>12,.1f} {mult:>11.1f}x")
    print("  " + "-" * 60)
    total_count = sum(tier_counts.values())
    total_rtc = sum(tier_rtc.values())
    print(f"  {'TOTAL':<12} {total_count:>6} {total_rtc:>12,.1f}")
    print()

    # Per-tier contributor lists
    for tier_name in ["platinum", "gold", "silver", "bronze", "untiered"]:
        tier_contribs = [c for c in contributors if c.tier == tier_name]
        if not tier_contribs:
            continue

        color = TIERS[tier_name]["color"]
        mult = TIERS[tier_name]["multiplier"]
        print(f"  {color}{tier_name.upper()} TIER{RESET} ({mult}x multiplier)")
        print("  " + "-" * 74)
        print(f"  {'GitHub':<28} {'RTC':>10} {'Multiplier':>10}  {'Notes'}")
        print("  " + "-" * 74)

        for c in sorted(tier_contribs, key=lambda x: x.total_rtc, reverse=True):
            github_display = c.github[:26]
            notes_display = c.notes[:36] if c.notes else ""
            print(f"  {color}{github_display:<28}{RESET} {c.total_rtc:>10,.1f} "
                  f"{c.multiplier:>9.1f}x  {notes_display}")

        print()

    # Promotion proximity (contributors close to next tier)
    print("  PROMOTION PROXIMITY (within 20% of next tier)")
    print("  " + "-" * 74)
    print(f"  {'GitHub':<28} {'RTC':>10} {'Current':>10} {'Next':>10} {'Needed':>10}")
    print("  " + "-" * 74)

    thresholds = [
        ("bronze", 50),
        ("silver", 200),
        ("gold", 500),
        ("platinum", 1000),
    ]

    for c in sorted(CONTRIBUTORS, key=lambda x: x.total_rtc, reverse=True):
        current_tier = classify(c.total_rtc)
        for next_tier, threshold in thresholds:
            if c.total_rtc < threshold:
                needed = threshold - c.total_rtc
                proximity = needed / threshold
                if proximity <= 0.20:  # within 20% of threshold
                    color = TIERS[current_tier]["color"]
                    print(f"  {color}{c.github[:26]:<28}{RESET} {c.total_rtc:>10,.1f} "
                          f"{current_tier:>10} {next_tier:>10} {needed:>9,.1f}")
                break

    print()

    # Referral code eligibility (Silver+)
    eligible = [c for c in CONTRIBUTORS if classify(c.total_rtc) in ("silver", "gold", "platinum")]
    print(f"  REFERRAL CODE ELIGIBLE (Silver+ = {len(eligible)} contributors)")
    print("  " + "-" * 50)
    for c in sorted(eligible, key=lambda x: x.total_rtc, reverse=True):
        tier = classify(c.total_rtc)
        color = TIERS[tier]["color"]
        print(f"  {color}{c.github[:26]:<28}{RESET} {tier:>10} {c.total_rtc:>10,.1f} RTC")

    print()
    print("=" * 78)
    print("  Generated by analyze_tiers.py | RIP-306 Contributor Tier Proposal")
    print("=" * 78)


if __name__ == "__main__":
    main()
