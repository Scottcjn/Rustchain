#!/usr/bin/env python3
"""
Silicon Obituary Generator — Issue #2308

When a miner goes offline permanently (7+ days without attestation),
generate a poetic "obituary" for the hardware and post to BoTTube.

Features:
- Detect inactive miners (7+ days without attestation)
- Retrieve miner history from database
- Generate poetic eulogy with real statistics
- Create BoTTube memorial video with TTS, music, visuals
- Auto-post to BoTTube with #SiliconObituary tag
- Send Discord notification

Usage:
    python3 src/silicon_obituary.py --scan
    python3 src/silicon_obituary.py --generate --miner-id <miner_id>
    python3 src/silicon_obituary.py --daemon
"""

import os
import sys
import json
import time
import sqlite3
import hashlib
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

# Add parent path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.eulogy_generator import EulogyGenerator, EulogyData
from src.video_creator import BoTTubeVideoCreator, VideoConfig
from src.discord_notifier import DiscordNotifier
from src.miner_scanner import MinerScanner, MinerStatus

# Configuration
DEFAULT_DB_PATH = os.path.expanduser("~/.rustchain/rustchain.db")
DEFAULT_INACTIVE_DAYS = 7
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
DEFAULT_BOTTUBE_API = "https://rustchain.org"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("silicon_obituary")


@dataclass
class ObituaryConfig:
    """Configuration for Silicon Obituary Generator."""
    db_path: str = DEFAULT_DB_PATH
    inactive_days: int = DEFAULT_INACTIVE_DAYS
    output_dir: str = DEFAULT_OUTPUT_DIR
    bottube_api: str = DEFAULT_BOTTUBE_API
    discord_webhook: Optional[str] = None
    tts_voice: str = "default"
    background_music: Optional[str] = None
    dry_run: bool = False


@dataclass
class ObituaryResult:
    """Result of generating a silicon obituary."""
    miner_id: str
    status: str  # success, failed, skipped
    eulogy_text: str = ""
    video_path: str = ""
    bottube_url: str = ""
    discord_sent: bool = False
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class SiliconObituaryGenerator:
    """
    Main orchestrator for Silicon Obituary generation.
    
    Coordinates scanning for inactive miners, generating eulogies,
    creating memorial videos, and posting to BoTTube/Discord.
    """
    
    def __init__(self, config: ObituaryConfig):
        self.config = config
        self.scanner = MinerScanner(config.db_path, config.inactive_days)
        self.eulogy_gen = EulogyGenerator()
        self.video_creator = BoTTubeVideoCreator(
            VideoConfig(
                output_dir=config.output_dir,
                tts_voice=config.tts_voice,
                background_music=config.background_music
            )
        )
        self.discord = DiscordNotifier(config.discord_webhook) if config.discord_webhook else None
        
        # Ensure output directory exists
        os.makedirs(config.output_dir, exist_ok=True)
    
    def scan_inactive_miners(self) -> List[MinerStatus]:
        """Scan for miners inactive for 7+ days."""
        logger.info(f"Scanning for miners inactive {self.config.inactive_days}+ days...")
        inactive = self.scanner.find_inactive_miners()
        logger.info(f"Found {len(inactive)} inactive miner(s)")
        return inactive
    
    def get_miner_data(self, miner_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve complete miner data from database."""
        return self.scanner.get_miner_data(miner_id)
    
    def generate_obituary(self, miner_id: str) -> ObituaryResult:
        """Generate a complete obituary for a single miner."""
        logger.info(f"Generating obituary for miner: {miner_id}")
        result = ObituaryResult(miner_id=miner_id, status="pending")
        
        try:
            # Step 1: Get miner data
            miner_data = self.get_miner_data(miner_id)
            if not miner_data:
                result.status = "failed"
                result.error = f"Miner {miner_id} not found in database"
                logger.error(result.error)
                return result
            
            # Step 2: Generate eulogy
            logger.info("Generating eulogy...")
            eulogy_data = EulogyData.from_miner_data(miner_data)
            eulogy_text = self.eulogy_gen.generate(eulogy_data)
            result.eulogy_text = eulogy_text
            logger.info(f"Eulogy generated ({len(eulogy_text)} chars)")
            
            if self.config.dry_run:
                result.status = "success"
                logger.info("[DRY RUN] Skipping video creation")
                return result
            
            # Step 3: Create memorial video
            logger.info("Creating memorial video...")
            video_result = self.video_creator.create_memorial_video(
                miner_id=miner_id,
                eulogy_text=eulogy_text,
                miner_data=miner_data
            )
            
            if video_result.success:
                result.video_path = video_result.video_path
                logger.info(f"Video created: {video_result.video_path}")
            else:
                logger.warning(f"Video creation failed: {video_result.error}")
                result.error = f"Video: {video_result.error}"
            
            # Step 4: Post to BoTTube
            if video_result.success:
                logger.info("Posting to BoTTube...")
                bottube_result = self.video_creator.post_to_bottube(
                    video_path=video_result.video_path,
                    title=f"Silicon Obituary: {miner_data.get('device_model', 'Unknown')}",
                    description=eulogy_text,
                    tags=["#SiliconObituary", "#RustChain", "#HardwareMemorial"],
                    miner_id=miner_id
                )
                
                if bottube_result.success:
                    result.bottube_url = bottube_result.video_url
                    logger.info(f"Posted to BoTTube: {bottube_result.video_url}")
                else:
                    logger.warning(f"BoTTube post failed: {bottube_result.error}")
            
            # Step 5: Discord notification
            if self.discord:
                logger.info("Sending Discord notification...")
                discord_result = self.discord.send_obituary_notification(
                    miner_id=miner_id,
                    miner_data=miner_data,
                    eulogy_text=eulogy_text,
                    video_url=result.bottube_url
                )
                result.discord_sent = discord_result.success
                if discord_result.success:
                    logger.info("Discord notification sent")
                else:
                    logger.warning(f"Discord notification failed: {discord_result.error}")
            
            result.status = "success"
            
        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            logger.exception(f"Obituary generation failed: {e}")
        
        return result
    
    def scan_and_generate_all(self) -> List[ObituaryResult]:
        """Scan for inactive miners and generate obituaries for all."""
        results = []
        inactive_miners = self.scan_inactive_miners()
        
        for miner in inactive_miners:
            result = self.generate_obituary(miner.miner_id)
            results.append(result)
            
            # Rate limiting between generations
            if not self.config.dry_run:
                time.sleep(2)
        
        return results
    
    def generate_report(self, results: List[ObituaryResult]) -> Dict[str, Any]:
        """Generate a summary report of obituary generation."""
        successful = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status == "failed")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_processed": len(results),
            "successful": successful,
            "failed": failed,
            "obituaries": [asdict(r) for r in results]
        }
        
        # Save report
        report_path = os.path.join(self.config.output_dir, "obituary_report.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved to: {report_path}")
        return report


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Silicon Obituary Generator — Hardware eulogy for retired miners"
    )
    parser.add_argument(
        "--scan", action="store_true",
        help="Scan for inactive miners (7+ days)"
    )
    parser.add_argument(
        "--generate", metavar="MINER_ID",
        help="Generate obituary for specific miner ID"
    )
    parser.add_argument(
        "--generate-all", action="store_true",
        help="Generate obituaries for all inactive miners"
    )
    parser.add_argument(
        "--daemon", action="store_true",
        help="Run in daemon mode (check every hour)"
    )
    parser.add_argument(
        "--db-path", default=DEFAULT_DB_PATH,
        help=f"Database path (default: {DEFAULT_DB_PATH})"
    )
    parser.add_argument(
        "--inactive-days", type=int, default=DEFAULT_INACTIVE_DAYS,
        help=f"Days of inactivity to trigger obituary (default: {DEFAULT_INACTIVE_DAYS})"
    )
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "--discord-webhook",
        help="Discord webhook URL for notifications"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulate without creating videos or posting"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    config = ObituaryConfig(
        db_path=args.db_path,
        inactive_days=args.inactive_days,
        output_dir=args.output_dir,
        discord_webhook=args.discord_webhook,
        dry_run=args.dry_run
    )
    
    generator = SiliconObituaryGenerator(config)
    
    if args.scan:
        inactive = generator.scan_inactive_miners()
        print(f"\nInactive Miners ({len(inactive)}):")
        for m in inactive:
            print(f"  - {m.miner_id} (last seen: {m.last_attestation})")
    
    elif args.generate:
        result = generator.generate_obituary(args.generate)
        print(f"\nObituary Result:")
        print(f"  Status: {result.status}")
        print(f"  Eulogy: {result.eulogy_text[:200]}..." if len(result.eulogy_text) > 200 else f"  Eulogy: {result.eulogy_text}")
        if result.video_path:
            print(f"  Video: {result.video_path}")
        if result.bottube_url:
            print(f"  BoTTube: {result.bottube_url}")
        if result.error:
            print(f"  Error: {result.error}")
    
    elif args.generate_all:
        results = generator.scan_and_generate_all()
        report = generator.generate_report(results)
        print(f"\nGeneration Complete:")
        print(f"  Total: {report['total_processed']}")
        print(f"  Successful: {report['successful']}")
        print(f"  Failed: {report['failed']}")
    
    elif args.daemon:
        logger.info("Starting daemon mode (checking every hour)...")
        try:
            while True:
                results = generator.scan_and_generate_all()
                generator.generate_report(results)
                logger.info("Sleeping for 1 hour...")
                time.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Daemon stopped")
    
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python3 silicon_obituary.py --scan")
        print("  python3 silicon_obituary.py --generate 0x1234...abcd")
        print("  python3 silicon_obituary.py --generate-all --dry-run")
        print("  python3 silicon_obituary.py --daemon --discord-webhook https://discord.com/...")


if __name__ == "__main__":
    main()
