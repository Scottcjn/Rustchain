# SPDX-License-Identifier: MIT

"""
Epoch Reporter Bot - Monitors RustChain epochs and posts summaries to multiple platforms.
Tracks epoch changes, fetches miner data, and posts formatted summaries.
"""

import json
import os
import sqlite3
import time
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Configuration
NODE_URL = os.getenv("NODE_URL", "https://50.28.86.131")
DB_PATH = os.getenv("EPOCH_DB_PATH", "epoch_reporter.db")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))  # seconds
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Platform configuration
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
MOLTBOOK_API_KEY = os.getenv("MOLTBOOK_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Enable/disable platforms
ENABLE_DISCORD = os.getenv("ENABLE_DISCORD", "true").lower() == "true"
ENABLE_MOLTBOOK = os.getenv("ENABLE_MOLTBOOK", "true").lower() == "true"
ENABLE_TWITTER = os.getenv("ENABLE_TWITTER", "false").lower() == "true"

logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)


class EpochReporter:
    def __init__(self):
        self.setup_database()

    def setup_database(self):
        """Initialize SQLite database for epoch tracking"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reported_epochs (
                    epoch_number INTEGER PRIMARY KEY,
                    reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    platforms_posted TEXT,
                    total_rtc REAL,
                    miner_count INTEGER
                )
            """)
            conn.commit()

    def fetch_current_epoch(self) -> Optional[Dict]:
        """Fetch current epoch data from RustChain node"""
        try:
            response = requests.get(f"{NODE_URL}/epoch", timeout=10, verify=False)
            if response.ok:
                return response.json()
            logger.warning(f"Epoch API returned {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Failed to fetch epoch data: {e}")
        return None

    def fetch_active_miners(self) -> List[Dict]:
        """Fetch active miners list"""
        try:
            response = requests.get(f"{NODE_URL}/miners", timeout=10, verify=False)
            if response.ok:
                miners_data = response.json()
                return miners_data.get("miners", []) if isinstance(miners_data, dict) else miners_data
        except Exception as e:
            logger.error(f"Failed to fetch miners: {e}")
        return []

    def fetch_blockchain_info(self) -> Dict:
        """Fetch current blockchain statistics"""
        try:
            response = requests.get(f"{NODE_URL}/stats", timeout=10, verify=False)
            if response.ok:
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch blockchain stats: {e}")
        return {}

    def is_epoch_reported(self, epoch_num: int) -> bool:
        """Check if epoch has already been reported"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM reported_epochs WHERE epoch_number = ?",
                (epoch_num,)
            )
            return cursor.fetchone() is not None

    def mark_epoch_reported(self, epoch_num: int, platforms: List[str],
                          total_rtc: float, miner_count: int):
        """Mark epoch as reported in database"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO reported_epochs
                (epoch_number, platforms_posted, total_rtc, miner_count)
                VALUES (?, ?, ?, ?)
            """, (epoch_num, ",".join(platforms), total_rtc, miner_count))
            conn.commit()

    def categorize_miners(self, miners: List[Dict]) -> Dict:
        """Categorize miners by hardware type"""
        categories = {
            "g4": [],
            "g5": [],
            "power8": [],
            "modern": []
        }

        for miner in miners:
            miner_id = miner.get("miner_id", "").lower()
            if "g4" in miner_id:
                categories["g4"].append(miner)
            elif "g5" in miner_id:
                categories["g5"].append(miner)
            elif "power8" in miner_id or "pwr8" in miner_id:
                categories["power8"].append(miner)
            else:
                categories["modern"].append(miner)

        return categories

    def find_top_earner(self, miners: List[Dict]) -> Optional[Tuple[Dict, float]]:
        """Find the top earning miner from the list"""
        top_miner = None
        max_earnings = 0.0

        for miner in miners:
            earnings = float(miner.get("amount_rtc", 0))
            if earnings > max_earnings:
                max_earnings = earnings
                top_miner = miner

        return (top_miner, max_earnings) if top_miner else None

    def format_epoch_summary(self, epoch_data: Dict, miners: List[Dict],
                           blockchain_stats: Dict) -> str:
        """Format epoch data into readable summary"""
        epoch_num = epoch_data.get("epoch", 0)
        total_rtc = sum(float(m.get("amount_rtc", 0)) for m in miners)
        miner_count = len(miners)

        # Categorize miners
        categories = self.categorize_miners(miners)
        cat_counts = {k: len(v) for k, v in categories.items()}

        # Find top earner
        top_earner_info = self.find_top_earner(miners)
        top_earner_text = "None"
        if top_earner_info:
            top_miner, earnings = top_earner_info
            miner_id = top_miner.get("miner_id", "unknown")
            multiplier = ""
            if "g4" in miner_id.lower():
                multiplier = " (G4 2.5x)"
            elif "g5" in miner_id.lower():
                multiplier = " (G5 3.0x)"
            top_earner_text = f"{miner_id} ({earnings:.3f} RTC{multiplier})"

        # Hardware breakdown
        hw_parts = []
        if cat_counts["g4"] > 0:
            hw_parts.append(f"{cat_counts['g4']} G4")
        if cat_counts["g5"] > 0:
            hw_parts.append(f"{cat_counts['g5']} G5")
        if cat_counts["power8"] > 0:
            hw_parts.append(f"{cat_counts['power8']} POWER8")
        if cat_counts["modern"] > 0:
            hw_parts.append(f"{cat_counts['modern']} modern")

        hw_breakdown = f"({', '.join(hw_parts)})" if hw_parts else ""

        # Blockchain stats
        block_height = blockchain_stats.get("block_height", "unknown")
        total_mined = blockchain_stats.get("total_rtc_issued", 0)

        summary = f"""📊 Epoch {epoch_num} Complete

💰 {total_rtc:.1f} RTC distributed to {miner_count} miners
🏆 Top earner: {top_earner_text}
⛏️ Active miners: {miner_count} {hw_breakdown}
📦 Block height: {block_height:,}
💎 Total RTC mined: {total_mined:.1f}

Explorer: {NODE_URL}/explorer"""

        return summary

    def post_to_discord(self, content: str) -> bool:
        """Post summary to Discord via webhook"""
        if not ENABLE_DISCORD or not DISCORD_WEBHOOK:
            return False

        try:
            payload = {"content": content}
            response = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
            if response.ok:
                logger.info("Posted to Discord successfully")
                return True
            else:
                logger.error(f"Discord post failed: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"Discord posting error: {e}")
        return False

    def post_to_moltbook(self, content: str) -> bool:
        """Post summary to Moltbook"""
        if not ENABLE_MOLTBOOK or not MOLTBOOK_API_KEY:
            return False

        try:
            headers = {"Authorization": f"Bearer {MOLTBOOK_API_KEY}"}
            payload = {"status": content, "visibility": "public"}
            response = requests.post("https://moltbook.com/api/v1/statuses",
                                   json=payload, headers=headers, timeout=10)
            if response.ok:
                logger.info("Posted to Moltbook successfully")
                return True
            else:
                logger.error(f"Moltbook post failed: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"Moltbook posting error: {e}")
        return False

    def post_to_twitter(self, content: str) -> bool:
        """Post summary to Twitter/X"""
        if not ENABLE_TWITTER or not TWITTER_BEARER_TOKEN:
            return False

        try:
            headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
            payload = {"text": content}
            response = requests.post("https://api.twitter.com/2/tweets",
                                   json=payload, headers=headers, timeout=10)
            if response.ok:
                logger.info("Posted to Twitter successfully")
                return True
            else:
                logger.error(f"Twitter post failed: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"Twitter posting error: {e}")
        return False

    def post_epoch_summary(self, summary: str, epoch_num: int,
                          total_rtc: float, miner_count: int):
        """Post epoch summary to all enabled platforms"""
        posted_platforms = []

        if self.post_to_discord(summary):
            posted_platforms.append("discord")

        if self.post_to_moltbook(summary):
            posted_platforms.append("moltbook")

        if self.post_to_twitter(summary):
            posted_platforms.append("twitter")

        if posted_platforms:
            self.mark_epoch_reported(epoch_num, posted_platforms, total_rtc, miner_count)
            logger.info(f"Epoch {epoch_num} reported to: {', '.join(posted_platforms)}")
        else:
            logger.warning(f"Failed to post epoch {epoch_num} to any platform")

    def check_and_report_epoch(self):
        """Main logic to check for new epochs and report them"""
        epoch_data = self.fetch_current_epoch()
        if not epoch_data:
            logger.debug("Could not fetch epoch data")
            return

        epoch_num = epoch_data.get("epoch", 0)
        if epoch_num == 0:
            logger.debug("Invalid epoch number received")
            return

        if self.is_epoch_reported(epoch_num):
            logger.debug(f"Epoch {epoch_num} already reported")
            return

        logger.info(f"New epoch detected: {epoch_num}")

        # Fetch additional data
        miners = self.fetch_active_miners()
        blockchain_stats = self.fetch_blockchain_info()

        if not miners:
            logger.warning(f"No miners data for epoch {epoch_num}")
            return

        # Generate and post summary
        summary = self.format_epoch_summary(epoch_data, miners, blockchain_stats)
        total_rtc = sum(float(m.get("amount_rtc", 0)) for m in miners)

        logger.info(f"Posting epoch {epoch_num} summary:\n{summary}")
        self.post_epoch_summary(summary, epoch_num, total_rtc, len(miners))

    def run(self):
        """Main run loop"""
        logger.info("Starting Epoch Reporter Bot")
        logger.info(f"Polling interval: {POLL_INTERVAL}s")
        logger.info(f"Platforms enabled - Discord: {ENABLE_DISCORD}, "
                   f"Moltbook: {ENABLE_MOLTBOOK}, Twitter: {ENABLE_TWITTER}")

        while True:
            try:
                self.check_and_report_epoch()
            except Exception as e:
                logger.error(f"Error in main loop: {e}")

            time.sleep(POLL_INTERVAL)


def main():
    reporter = EpochReporter()
    reporter.run()


if __name__ == "__main__":
    main()
