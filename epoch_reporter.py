// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import sqlite3
import requests
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_PATH = 'epoch_reporter.db'
BASE_URL = 'https://50.28.86.131'

# Platform webhooks from environment
DISCORD_WEBHOOK = os.environ.get('DISCORD_WEBHOOK')
MOLTBOOK_WEBHOOK = os.environ.get('MOLTBOOK_WEBHOOK')
X_WEBHOOK = os.environ.get('X_WEBHOOK')

# Polling interval (seconds)
POLL_INTERVAL = int(os.environ.get('EPOCH_POLL_INTERVAL', '60'))

class EpochReporter:
    def __init__(self):
        self.init_db()

    def init_db(self):
        """Initialize SQLite database for tracking posted epochs"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS posted_epochs (
                    epoch_number INTEGER PRIMARY KEY,
                    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    platforms TEXT,
                    summary TEXT
                )
            ''')
            conn.commit()

    def get_epoch_data(self) -> Optional[Dict[str, Any]]:
        """Fetch current epoch data from API"""
        try:
            response = requests.get(f'{BASE_URL}/epoch', verify=False, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch epoch data: {e}")
        return None

    def get_miners_data(self) -> Optional[Dict[str, Any]]:
        """Fetch active miners data"""
        try:
            response = requests.get(f'{BASE_URL}/miners', verify=False, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch miners data: {e}")
        return None

    def get_blockchain_stats(self) -> Optional[Dict[str, Any]]:
        """Fetch blockchain statistics"""
        try:
            response = requests.get(f'{BASE_URL}/stats', verify=False, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch blockchain stats: {e}")
        return None

    def is_epoch_posted(self, epoch_number: int) -> bool:
        """Check if epoch has already been posted"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT epoch_number FROM posted_epochs WHERE epoch_number = ?', (epoch_number,))
            return cursor.fetchone() is not None

    def mark_epoch_posted(self, epoch_number: int, platforms: list, summary: str):
        """Mark epoch as posted to avoid duplicates"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO posted_epochs (epoch_number, platforms, summary)
                VALUES (?, ?, ?)
            ''', (epoch_number, ','.join(platforms), summary))
            conn.commit()

    def categorize_miners(self, miners_data: list) -> Dict[str, int]:
        """Categorize miners by hardware type"""
        categories = {
            'G4': 0,
            'G5': 0,
            'POWER8': 0,
            'modern': 0
        }

        for miner in miners_data:
            name = miner.get('name', '').lower()
            if 'g4' in name:
                categories['G4'] += 1
            elif 'g5' in name:
                categories['G5'] += 1
            elif 'power8' in name or 'p8' in name:
                categories['POWER8'] += 1
            else:
                categories['modern'] += 1

        return categories

    def format_epoch_summary(self, epoch_data: Dict[str, Any], miners_data: list, stats_data: Dict[str, Any]) -> str:
        """Format epoch completion summary message"""
        epoch_number = epoch_data.get('epoch_number', 0)
        rtc_distributed = epoch_data.get('rewards_distributed', 0)
        active_miners_count = len(miners_data)

        # Find top earner
        top_earner = None
        max_reward = 0
        for miner in miners_data:
            reward = miner.get('epoch_reward', 0)
            if reward > max_reward:
                max_reward = reward
                top_earner = miner

        # Categorize miners
        miner_categories = self.categorize_miners(miners_data)

        # Build category string
        category_parts = []
        for cat, count in miner_categories.items():
            if count > 0:
                category_parts.append(f"{count} {cat}")
        category_str = ', '.join(category_parts)

        # Get blockchain stats
        block_height = stats_data.get('block_height', 'N/A')
        total_rtc = stats_data.get('total_rtc_mined', 0)

        # Format top earner info
        top_earner_info = "N/A"
        if top_earner:
            name = top_earner.get('name', 'Unknown')
            multiplier = top_earner.get('multiplier', 1.0)
            hardware = 'G4' if 'g4' in name.lower() else 'modern'
            top_earner_info = f"{name} ({max_reward:.3f} RTC, {hardware} {multiplier}x)"

        summary = f"""📊 Epoch {epoch_number} Complete

💰 {rtc_distributed:.1f} RTC distributed to {active_miners_count} miners
🏆 Top earner: {top_earner_info}
⛏️ Active miners: {active_miners_count} ({category_str})
📦 Block height: {block_height}
💎 Total RTC mined: {total_rtc:.1f}

Explorer: {BASE_URL}/explorer"""

        return summary

    def post_to_discord(self, message: str) -> bool:
        """Post message to Discord via webhook"""
        if not DISCORD_WEBHOOK:
            return False

        try:
            payload = {'content': message}
            response = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
            return response.status_code == 204
        except Exception as e:
            logger.error(f"Failed to post to Discord: {e}")
            return False

    def post_to_moltbook(self, message: str) -> bool:
        """Post message to Moltbook via webhook"""
        if not MOLTBOOK_WEBHOOK:
            return False

        try:
            payload = {'text': message}
            response = requests.post(MOLTBOOK_WEBHOOK, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to post to Moltbook: {e}")
            return False

    def post_to_x(self, message: str) -> bool:
        """Post message to X/Twitter via webhook"""
        if not X_WEBHOOK:
            return False

        try:
            payload = {'status': message}
            response = requests.post(X_WEBHOOK, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to post to X: {e}")
            return False

    def post_summary(self, summary: str) -> list:
        """Post summary to all configured platforms"""
        posted_platforms = []

        if self.post_to_discord(summary):
            posted_platforms.append('Discord')
            logger.info("Posted to Discord successfully")

        if self.post_to_moltbook(summary):
            posted_platforms.append('Moltbook')
            logger.info("Posted to Moltbook successfully")

        if self.post_to_x(summary):
            posted_platforms.append('X')
            logger.info("Posted to X successfully")

        return posted_platforms

    def check_and_post_epoch(self):
        """Main function to check for new epoch and post if needed"""
        epoch_data = self.get_epoch_data()
        if not epoch_data:
            logger.warning("Could not fetch epoch data")
            return

        epoch_number = epoch_data.get('epoch_number')
        if not epoch_number:
            logger.warning("No epoch number in response")
            return

        # Check if epoch already posted
        if self.is_epoch_posted(epoch_number):
            logger.debug(f"Epoch {epoch_number} already posted")
            return

        # Get additional data
        miners_data = self.get_miners_data() or []
        stats_data = self.get_blockchain_stats() or {}

        # Format summary
        summary = self.format_epoch_summary(epoch_data, miners_data, stats_data)

        # Post to platforms
        posted_platforms = self.post_summary(summary)

        if posted_platforms:
            self.mark_epoch_posted(epoch_number, posted_platforms, summary)
            logger.info(f"Posted epoch {epoch_number} summary to {', '.join(posted_platforms)}")
        else:
            logger.warning(f"Failed to post epoch {epoch_number} to any platform")

    def run(self):
        """Main loop - continuously monitor for new epochs"""
        logger.info("Starting Epoch Reporter Bot")
        logger.info(f"Polling every {POLL_INTERVAL} seconds")

        platforms_configured = []
        if DISCORD_WEBHOOK: platforms_configured.append('Discord')
        if MOLTBOOK_WEBHOOK: platforms_configured.append('Moltbook')
        if X_WEBHOOK: platforms_configured.append('X')

        if not platforms_configured:
            logger.error("No platform webhooks configured. Set DISCORD_WEBHOOK, MOLTBOOK_WEBHOOK, or X_WEBHOOK environment variables.")
            return

        logger.info(f"Configured platforms: {', '.join(platforms_configured)}")

        while True:
            try:
                self.check_and_post_epoch()
                time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                logger.info("Shutting down Epoch Reporter Bot")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(POLL_INTERVAL)

def main():
    reporter = EpochReporter()
    reporter.run()

if __name__ == '__main__':
    main()
