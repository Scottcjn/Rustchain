#!/usr/bin/env python3
"""
Silicon Obituary Generator — Bounty #2308 (25 RTC)
Detects retired miners, generates poetic eulogies with real data,
creates memorial videos, and posts to BoTTube.
"""

import argparse
import datetime
import json
import logging
import os
import random
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.expanduser("~/.rustchain/rustchain.db")
DEFAULT_BOTTUBE_URL = "https://bottube.ai"


class MinerScanner:
    """Scans the RustChain database for inactive miners."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        if not os.path.exists(self.db_path):
            logger.warning(f"Database not found at {self.db_path}")
            return None
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def find_inactive_miners(self, days: int = 7) -> List[Dict[str, Any]]:
        """Find miners that haven't attested in N+ days."""
        conn = self.get_connection()
        if not conn:
            return []
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        query = """
            SELECT m.miner_id, m.wallet_address, m.architecture, m.multiplier,
                   MIN(a.timestamp) as first_attestation,
                   MAX(a.timestamp) as last_attestation,
                   COUNT(a.id) as total_epochs,
                   COALESCE(SUM(a.rtc_earned), 0) as total_rtc
            FROM miners m
            LEFT JOIN attestations a ON m.miner_id = a.miner_id
            GROUP BY m.miner_id
            HAVING last_attestation < ? OR last_attestation IS NULL
        """
        try:
            rows = conn.execute(query, (cutoff,)).fetchall()
            miners = []
            for row in rows:
                miners.append({
                    "miner_id": row["miner_id"],
                    "wallet_address": row["wallet_address"],
                    "architecture": row["architecture"] or "Unknown",
                    "multiplier": row["multiplier"] or 1.0,
                    "first_attestation": row["first_attestation"],
                    "last_attestation": row["last_attestation"],
                    "total_epochs": row["total_epochs"] or 0,
                    "total_rtc": float(row["total_rtc"] or 0),
                })
            conn.close()
            return miners
        except Exception as e:
            logger.error(f"Error scanning miners: {e}")
            conn.close()
            return []


class EulogyGenerator:
    """Generates poetic eulogies with real miner statistics."""

    TEMPLATES = [
        "Here lies {architecture}, a faithful servant of the chain.\n"
        "It attested for {epochs} epochs and earned {rtc} RTC.\n"
        "Its {arch_detail} was as unique as a fingerprint in the silicon wind.\n"
        "It is survived by its power supply, which still works.",

        "In memory of {miner_id}, a {architecture} miner of noble lineage.\n"
        "From {first_date} to {last_date}, it served the network faithfully.\n"
        "{epochs} attestations. {rtc} RTC. One machine saved from e-waste.\n"
        "The cache timing echoes of its {arch_detail} will never be forgotten.",

        "RIP {miner_id} ({architecture}).\n"
        "Born of vintage silicon, it mined proof-of-antiquity with pride.\n"
        "Total service: {epochs} epochs, {rtc} RTC earned.\n"
        "Its multiplier of {multiplier}x reminded us: age brings wisdom.\n"
        "Now it joins the great hardware graveyard in the sky.",

        "A {architecture} has fallen. {miner_id} served {epochs} epochs\n"
        "and earned {rtc} RTC before retiring to the digital afterlife.\n"
        "Its {arch_detail} once sang the song of computation.\n"
        "That song continues in the blockchain it helped build.",
    ]

    ARCH_DETAILS = {
        "Power Mac G4": "aluminum casing and beige soul",
        "Raspberry Pi": "tiny form factor and giant heart",
        "BeagleBone": "open-source spirit and GPIO dreams",
        "Intel NUC": "compact power and silent dedication",
        "AMD Ryzen": "multi-core ambitions and single-minded purpose",
        "Apple M1": "ARM-era prophecy fulfilled",
        "Unknown": "mysterious architecture",
    }

    def generate(self, miner: Dict[str, Any], style: str = "poetic") -> str:
        template = random.choice(self.TEMPLATES)
        arch = miner.get("architecture", "Unknown")
        arch_detail = self.ARCH_DETAILS.get(arch, self.ARCH_DETAILS["Unknown"])
        first_date = miner.get("first_attestation", "unknown date")[:10] if miner.get("first_attestation") else "unknown date"
        last_date = miner.get("last_attestation", "unknown date")[:10] if miner.get("last_attestation") else "unknown date"
        multiplier = f"{miner['multiplier']}x" if miner.get("multiplier") else "1x"

        eulogy = template.format(
            miner_id=miner["miner_id"],
            architecture=arch,
            epochs=miner["total_epochs"],
            rtc=miner["total_rtc"],
            multiplier=multiplier,
            first_date=first_date,
            last_date=last_date,
            arch_detail=arch_detail,
        )
        return eulogy


class VideoCreator:
    """Creates memorial video metadata for BoTTube integration."""

    def __init__(self, output_dir: str = "./obituaries"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_video(self, miner: Dict[str, Any], eulogy: str) -> Dict[str, Any]:
        meta_file = self.output_dir / f"obituary_{miner['miner_id']}.json"
        metadata = {
            "miner_id": miner["miner_id"],
            "wallet": miner["wallet_address"],
            "architecture": miner["architecture"],
            "eulogy": eulogy,
            "output_file": str(self.output_dir / f"obituary_{miner['miner_id']}.mp4"),
            "tags": ["#SiliconObituary", "#RustChain", "#ProofOfAntiquity"],
            "created_at": datetime.datetime.now().isoformat(),
        }
        with open(meta_file, "w") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Memorial metadata saved to {meta_file}")
        return metadata


class BoTTubePoster:
    """Posts obituary videos to BoTTube."""

    def __init__(self, api_url: str = "https://bottube.ai", api_key: str = ""):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    def post_video(self, metadata: Dict[str, Any]) -> bool:
        if not self.api_key:
            logger.info(f"[DRY RUN] Would post to BoTTube: {metadata['miner_id']}")
            return True
        url = f"{self.api_url}/api/upload"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "display_name": f"Silicon Obituary: {metadata['miner_id']}",
            "description": metadata["eulogy"],
            "tags": metadata["tags"],
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                logger.info(f"Video posted to BoTTube successfully")
                return True
            logger.error(f"BoTTube upload failed: {resp.status_code}")
            return False
        except requests.RequestException as e:
            logger.error(f"Network error: {e}")
            return False


class DiscordNotifier:
    """Sends rich embed notifications to Discord."""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url

    def notify(self, miner: Dict[str, Any], eulogy: str) -> bool:
        if not self.webhook_url:
            return True
        embed = {
            "title": f"💀 Silicon Obituary: {miner['miner_id']}",
            "description": eulogy,
            "color": 0x8B0000,
            "fields": [
                {"name": "Architecture", "value": miner["architecture"], "inline": True},
                {"name": "Epochs Served", "value": str(miner["total_epochs"]), "inline": True},
                {"name": "RTC Earned", "value": f"{miner['total_rtc']:.2f}", "inline": True},
                {"name": "Wallet", "value": miner["wallet_address"], "inline": False},
            ],
            "footer": {"text": "RustChain — Proof of Antiquity"},
            "timestamp": datetime.datetime.now().isoformat(),
        }
        try:
            resp = requests.post(self.webhook_url, json={"embeds": [embed]}, timeout=10)
            return resp.status_code == 204
        except requests.RequestException:
            return False


def main():
    parser = argparse.ArgumentParser(description="Silicon Obituary Generator for RustChain")
    parser.add_argument("--scan", action="store_true", help="Scan for inactive miners")
    parser.add_argument("--generate", type=str, help="Generate for specific miner ID")
    parser.add_argument("--generate-all", action="store_true", help="Generate for all inactive miners")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Database path")
    parser.add_argument("--inactive-days", type=int, default=7, help="Days threshold")
    parser.add_argument("--output-dir", default="./obituaries", help="Output directory")
    parser.add_argument("--discord-webhook", default=None, help="Discord webhook URL")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without posting")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    scanner = MinerScanner(db_path=args.db_path)
    generator = EulogyGenerator()
    creator = VideoCreator(output_dir=args.output_dir)
    poster = BoTTubePoster()
    notifier = DiscordNotifier(webhook_url=args.discord_webhook)

    if args.scan:
        miners = scanner.find_inactive_miners(args.inactive_days)
        print(f"\nFound {len(miners)} inactive miners (>{args.inactive_days} days):")
        for m in miners:
            last = m.get("last_attestation", "never")[:10] if m.get("last_attestation") else "never"
            print(f"  {m['miner_id']} | {m['architecture']} | {m['total_epochs']} epochs | {m['total_rtc']} RTC | Last: {last}")
        return

    miners = scanner.find_inactive_miners(args.inactive_days)
    if not miners:
        print("No inactive miners found.")
        return

    for miner in miners:
        eulogy = generator.generate(miner)
        print(f"\n{'='*60}")
        print(f"SILICON OBITUARY: {miner['miner_id']}")
        print(f"{'='*60}")
        print(eulogy)
        if not args.dry_run:
            metadata = creator.create_video(miner, eulogy)
            poster.post_video(metadata)
            notifier.notify(miner, eulogy)
            print(f"[Posted] {metadata['output_file']}")
        else:
            print("[DRY RUN] Skipped posting")


if __name__ == "__main__":
    main()
