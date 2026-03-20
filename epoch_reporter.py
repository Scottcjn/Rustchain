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
            CREATE TABLE IF NOT EXISTS reported_epochs (
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
    except Exception as e:
        logger.error(f"Error fetching epoch data: {e}")
        return None


def get_active_miners(node_url: str = NODE_URL) -> Optional[List[Dict]]:
    """Fetch active miners data from RustChain node"""
    try:
        response = requests.get(f"{node_url}/miners", timeout=10, verify=False)
        if response.ok:
            return response.json()
        else:
            logger.error(f"Failed to fetch miners data: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error fetching miners data: {e}")
        return None


def format_epoch_summary(epoch_data: Dict, miners_data: List[Dict] = None) -> str:
    """Format epoch data into a summary message"""
    epoch_num = epoch_data.get('epoch', 'N/A')
    total_rtc = epoch_data.get('total_distributed', 0.0)
    miner_count = epoch_data.get('miner_count', 0)
    block_height = epoch_data.get('block_height', 'N/A')
    total_mined = epoch_data.get('total_mined', 0.0)

    summary = f"📊 Epoch {epoch_num} Complete\n\n"
    summary += f"💰 {total_rtc:.4f} RTC distributed to {miner_count} miners\n"
    summary += f"📦 Block height: {block_height}\n"
    summary += f"💎 Total RTC mined: {total_mined:.4f}\n\n"

    if miners_data:
        # Sort miners by earnings and show top earner
        sorted_miners = sorted(miners_data, key=lambda x: x.get('earnings', 0), reverse=True)
        if sorted_miners:
            top_miner = sorted_miners[0]
            summary += f"🏆 Top earner: {top_miner.get('id', 'N/A')} ({top_miner.get('earnings', 0):.4f} RTC)\n"

    summary += f"Explorer: {NODE_URL}/explorer"
    return summary


def is_epoch_posted(epoch_num: int, db_path: str = DB_PATH) -> bool:
    """Check if epoch has already been posted"""
    with sqlite3.connect(db_path) as conn:
        result = conn.execute(
            "SELECT epoch_number FROM reported_epochs WHERE epoch_number = ?",
            (epoch_num,)
        ).fetchone()
        return result is not None


def mark_epoch_posted(epoch_num: int, platforms: List[str], total_rtc: float, miner_count: int, db_path: str = DB_PATH) -> None:
    """Mark epoch as posted to prevent duplicates"""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO reported_epochs (epoch_number, platforms_posted, total_rtc, miner_count) VALUES (?, ?, ?, ?)",
            (epoch_num, ','.join(platforms), total_rtc, miner_count)
        )
        conn.commit()


class EpochReporter:
    def __init__(self, db_path: str = DB_PATH, discord_webhook: str = None, moltbook_api: str = None, twitter_config: Dict = None):
        self.db_path = db_path
        self.discord_webhook = discord_webhook or DISCORD_WEBHOOK
        self.moltbook_api = moltbook_api
        self.twitter_config = twitter_config
        self.setup_database()

    def setup_database(self):
        """Initialize SQLite database for epoch tracking"""
        setup_database(self.db_path)

    def fetch_current_epoch(self) -> Optional[Dict]:
        """Fetch current epoch data from RustChain node"""
        return get_epoch_data()

    def fetch_miners_data(self) -> Optional[List[Dict]]:
        """Fetch active miners data"""
        return get_active_miners()

    def post_to_discord(self, message: str) -> bool:
        """Post message to Discord webhook"""
        if not self.discord_webhook:
            logger.warning("Discord webhook not configured")
            return False

        try:
            payload = {"content": message}
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            return response.ok
        except Exception as e:
            logger.error(f"Failed to post to Discord: {e}")
            return False

    def post_to_moltbook(self, message: str) -> bool:
        """Post message to Moltbook API"""
        if not self.moltbook_api:
            logger.warning("Moltbook API not configured")
            return False

        try:
            payload = {"content": message, "type": "epoch_update"}
            headers = {"Authorization": f"Bearer {MOLTBOOK_API_KEY}"} if MOLTBOOK_API_KEY else {}
            response = requests.post(self.moltbook_api, json=payload, headers=headers, timeout=10)
            return response.ok
        except Exception as e:
            logger.error(f"Failed to post to Moltbook: {e}")
            return False

    def run_once(self) -> bool:
        """Run one iteration of epoch checking and reporting"""
        epoch_data = self.fetch_current_epoch()
        if not epoch_data:
            logger.warning("Could not fetch epoch data")
            return False

        epoch_num = epoch_data.get('epoch')
        if not epoch_num:
            logger.warning("No epoch number in response")
            return False

        if is_epoch_posted(epoch_num, self.db_path):
            logger.info(f"Epoch {epoch_num} already posted")
            return False

        # Fetch miners data for detailed summary
        miners_data = self.fetch_miners_data()

        # Format summary message
        summary = format_epoch_summary(epoch_data, miners_data)

        # Post to enabled platforms
        posted_platforms = []

        if ENABLE_DISCORD and self.post_to_discord(summary):
            posted_platforms.append('discord')
            logger.info(f"Posted epoch {epoch_num} to Discord")

        if ENABLE_MOLTBOOK and self.post_to_moltbook(summary):
            posted_platforms.append('moltbook')
            logger.info(f"Posted epoch {epoch_num} to Moltbook")

        if posted_platforms:
            mark_epoch_posted(
                epoch_num,
                posted_platforms,
                epoch_data.get('total_distributed', 0.0),
                epoch_data.get('miner_count', 0),
                self.db_path
            )
            logger.info(f"Successfully posted epoch {epoch_num} to {', '.join(posted_platforms)}")
            return True
        else:
            logger.warning(f"Failed to post epoch {epoch_num} to any platform")
            return False

    def run(self):
        """Main loop for continuous epoch monitoring"""
        logger.info("Starting epoch reporter bot")

        while True:
            try:
                self.run_once()
                time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                logger.info("Shutting down epoch reporter bot")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    reporter = EpochReporter()
    reporter.run()
