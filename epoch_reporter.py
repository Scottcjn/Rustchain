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


def setup_database(db_path: str = DB_PATH) -> None:
    """Initialize SQLite database for epoch tracking"""
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_epochs (
                epoch_number INTEGER PRIMARY KEY,
                reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                platforms_posted TEXT,
                total_rtc REAL,
                miner_count INTEGER
            )
        """)
        conn.commit()


def get_epoch_data(node_url: str = NODE_URL) -> Optional[Dict]:
    """Fetch current epoch data from RustChain node"""
    try:
        response = requests.get(f"{node_url}/epoch", timeout=10, verify=False)
        if response.ok:
            return response.json()
        else:
            logger.error(f"Failed to fetch epoch data: {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.error(f"Error fetching epoch data: {e}")
        return None


def get_active_miners(node_url: str = NODE_URL) -> List[Dict]:
    """Fetch active miner data from RustChain node"""
    try:
        response = requests.get(f"{node_url}/miners", timeout=10, verify=False)
        if response.ok:
            return response.json().get('miners', [])
        else:
            logger.error(f"Failed to fetch miner data: {response.status_code}")
            return []
    except requests.RequestException as e:
        logger.error(f"Error fetching miner data: {e}")
        return []


def is_epoch_posted(epoch_num: int, db_path: str = DB_PATH) -> bool:
    """Check if epoch has already been posted"""
    try:
        with sqlite3.connect(db_path) as conn:
            result = conn.execute(
                "SELECT epoch_number FROM posted_epochs WHERE epoch_number = ?",
                (epoch_num,)
            ).fetchone()
            return result is not None
    except sqlite3.OperationalError as e:
        logger.error(f"Database error checking epoch: {e}")
        return False


def mark_epoch_posted(epoch_num: int, total_rtc: float, miner_count: int, platforms: str = "", db_path: str = DB_PATH) -> None:
    """Mark epoch as posted to avoid duplicates"""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO posted_epochs (epoch_number, platforms_posted, total_rtc, miner_count) VALUES (?, ?, ?, ?)",
            (epoch_num, platforms, total_rtc, miner_count)
        )
        conn.commit()


def format_epoch_summary(epoch_data: Dict, miners: List[Dict], node_url: str = NODE_URL) -> str:
    """Format epoch data into a readable summary"""
    epoch_num = epoch_data.get('epoch', 0)
    total_rtc = epoch_data.get('total_distributed', 0.0)
    miner_count = len(miners)
    block_height = epoch_data.get('block_height', 0)
    total_mined = epoch_data.get('total_mined', 0.0)

    # Find top earner
    top_miner = "N/A"
    top_earnings = 0.0
    if miners:
        top_earner = max(miners, key=lambda x: x.get('earnings', 0))
        top_earnings = top_earner.get('earnings', 0)
        top_miner = top_earner.get('miner_id', 'N/A')[:8] if top_miner != "N/A" else "N/A"

    explorer_url = f"{node_url}/explorer"

    summary = f"📊 Epoch {epoch_num} Complete\n\n"
    summary += f"💰 {total_rtc:.4f} RTC distributed to {miner_count} miners\n"
    summary += f"📦 Block height: {block_height}\n"
    summary += f"💎 Total RTC mined: {total_mined:.4f}\n\n"

    if miners and top_earnings > 0:
        summary += f"🏆 Top earner: {top_miner} ({top_earnings:.4f} RTC)\n"

    summary += f"Explorer: {explorer_url}"

    return summary


class EpochReporter:
    """Main epoch reporter class"""

    def __init__(self, db_path: str = DB_PATH, discord_webhook: str = None,
                 moltbook_api: str = None, twitter_config: Dict = None):
        self.db_path = db_path
        self.discord_webhook = discord_webhook
        self.moltbook_api = moltbook_api
        self.twitter_config = twitter_config or {}
        setup_database(db_path)

    def check_new_epoch(self) -> Optional[Dict]:
        """Check for new epoch and return data if found"""
        epoch_data = get_epoch_data()
        if not epoch_data:
            return None

        epoch_num = epoch_data.get('epoch')
        if not epoch_num or is_epoch_posted(epoch_num, self.db_path):
            return None

        return epoch_data

    def post_to_discord(self, message: str) -> bool:
        """Post message to Discord webhook"""
        if not self.discord_webhook:
            return False

        try:
            payload = {"content": message}
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            return response.ok
        except requests.RequestException as e:
            logger.error(f"Discord post error: {e}")
            return False

    def post_to_moltbook(self, message: str) -> bool:
        """Post message to Moltbook API"""
        if not self.moltbook_api:
            return False

        try:
            payload = {"content": message, "type": "epoch_update"}
            headers = {"Authorization": f"Bearer {MOLTBOOK_API_KEY}"}
            response = requests.post(self.moltbook_api, json=payload, headers=headers, timeout=10)
            return response.ok
        except requests.RequestException as e:
            logger.error(f"Moltbook post error: {e}")
            return False

    def run_epoch_check(self) -> None:
        """Run single epoch check and post if new epoch found"""
        epoch_data = self.check_new_epoch()
        if not epoch_data:
            return

        miners = get_active_miners()
        summary = format_epoch_summary(epoch_data, miners)

        # Post to enabled platforms
        platforms_posted = []

        if ENABLE_DISCORD and self.post_to_discord(summary):
            platforms_posted.append("discord")

        if ENABLE_MOLTBOOK and self.post_to_moltbook(summary):
            platforms_posted.append("moltbook")

        # Mark epoch as posted
        mark_epoch_posted(
            epoch_data['epoch'],
            epoch_data.get('total_distributed', 0.0),
            len(miners),
            ",".join(platforms_posted),
            self.db_path
        )

        logger.info(f"Posted epoch {epoch_data['epoch']} summary to: {platforms_posted}")

    def run_continuous(self) -> None:
        """Run continuous epoch monitoring"""
        logger.info("Starting epoch reporter bot...")

        while True:
            try:
                self.run_epoch_check()
                time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                logger.info("Shutting down epoch reporter bot...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    reporter = EpochReporter(
        discord_webhook=DISCORD_WEBHOOK,
        moltbook_api=os.getenv("MOLTBOOK_API_URL", "https://moltbook.com/api/posts")
    )
    reporter.run_continuous()
