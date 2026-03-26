#!/usr/bin/env python3
"""
Vintage AI Miner Video Pipeline - Main Orchestrator
====================================================

Automated pipeline that:
1. Monitors RustChain miner attestations
2. Generates AI video prompts based on miner metadata
3. Generates videos using open backends (LTX-Video, CogVideo, etc.)
4. Auto-uploads to BoTTube platform

Issue: #1855
Bounty: 150 RTC + bonuses
"""

import argparse
import json
import os
import random
import signal
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

# Import pipeline components
from rustchain_client import RustChainClient, create_client
from prompt_generator import VideoPromptGenerator
from video_generator import VideoGenerator, create_generator
from bottube_uploader import BoTTubeUploader, create_uploader


class VintageAIVideoPipeline:
    """
    Main pipeline orchestrator for vintage AI miner videos
    
    Coordinates all components:
    - RustChain API client for miner monitoring
    - Prompt generator for video prompts
    - Video generator for AI video creation
    - BoTTube uploader for auto-publishing
    """

    def __init__(
        self,
        rustchain_url: str = "https://rustchain.org",
        bottube_api_key: Optional[str] = None,
        bottube_url: str = "https://bottube.ai",
        video_backend: str = "demo",
        video_output_dir: str = "./generated_videos",
        verify_ssl: bool = False,
        dry_run: bool = False,
        verbose: bool = True,
    ):
        """
        Initialize the pipeline
        
        Args:
            rustchain_url: RustChain API URL
            bottube_api_key: BoTTube API key for uploads
            bottube_url: BoTTube API URL
            video_backend: Video generation backend
            video_output_dir: Output directory for videos
            verify_ssl: Enable SSL verification
            dry_run: Run without actual uploads
            verbose: Enable verbose logging
        """
        self.rustchain_url = rustchain_url
        self.bottube_api_key = bottube_api_key or os.getenv("BOTTUBE_API_KEY")
        self.bottube_url = bottube_url
        self.video_backend = video_backend
        self.video_output_dir = video_output_dir
        self.verify_ssl = verify_ssl
        self.dry_run = dry_run
        self.verbose = verbose
        
        # Initialize components
        self.log("🚀 Initializing Vintage AI Video Pipeline...")
        
        self.rustchain_client = create_client(
            base_url=rustchain_url,
            verify_ssl=verify_ssl,
        )
        
        self.prompt_generator = VideoPromptGenerator(
            backend=video_backend,
        )
        
        self.video_generator = create_generator(
            backend=video_backend,
            output_dir=video_output_dir,
        )
        
        self.bottube_uploader = create_uploader(
            api_key=bottube_api_key,
            base_url=bottube_url,
        )
        
        # Pipeline state
        self.running = False
        self.stats = {
            "videos_generated": 0,
            "videos_uploaded": 0,
            "errors": 0,
            "start_time": None,
            "last_attestation_check": None,
        }
        
        self.log("✅ Pipeline initialized")

    def log(self, message: str, level: str = "INFO") -> None:
        """Log message with timestamp"""
        if not self.verbose and level == "DEBUG":
            return
        
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        prefix = {
            "INFO": "ℹ️",
            "DEBUG": "🔍",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
        }.get(level, "•")
        
        print(f"[{timestamp}] {prefix} {message}")

    def process_miner(
        self,
        miner_data: Dict[str, Any],
        epoch_info: Optional[Dict[str, Any]] = None,
        upload: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a single miner through the complete pipeline
        
        Args:
            miner_data: Miner information from RustChain
            epoch_info: Current epoch information
            upload: Whether to upload to BoTTube
            
        Returns:
            Processing result
        """
        miner_id = miner_data.get("miner", "unknown")
        short_id = miner_id[:8] if len(miner_id) >= 8 else miner_id
        
        self.log(f"🎬 Processing miner: {short_id}...")
        
        result = {
            "miner_id": miner_id,
            "success": False,
            "steps": {},
        }
        
        try:
            # Step 1: Format miner data for video
            self.log(f"   Step 1: Formatting miner data", "DEBUG")
            formatted_miner = self.rustchain_client.format_miner_for_video(miner_data)
            result["steps"]["format"] = {"success": True}
            
            # Step 2: Generate video prompt
            self.log(f"   Step 2: Generating video prompt", "DEBUG")
            prompt_data = self.prompt_generator.generate_prompt(
                miner_data=formatted_miner,
                epoch_info=epoch_info,
            )
            result["steps"]["prompt"] = {"success": True, "data": prompt_data}
            
            # Step 3: Generate video
            self.log(f"   Step 3: Generating video (backend: {self.video_backend})", "INFO")
            video_result = self.video_generator.generate(
                prompt_data=prompt_data,
            )
            result["steps"]["video_generation"] = video_result
            
            if not video_result.get("success"):
                raise Exception(f"Video generation failed: {video_result.get('error')}")
            
            self.stats["videos_generated"] += 1
            
            # Step 4: Upload to BoTTube (if enabled and not dry-run)
            if upload and not self.dry_run:
                self.log(f"   Step 4: Uploading to BoTTube", "INFO")
                upload_result = self.bottube_uploader.upload_miner_video(
                    miner_data=formatted_miner,
                    video_info=video_result,
                    epoch_info=epoch_info,
                )
                result["steps"]["upload"] = upload_result
                
                if upload_result.get("success"):
                    self.stats["videos_uploaded"] += 1
                    self.log(
                        f"   ✅ Uploaded: {upload_result.get('url')}",
                        "SUCCESS"
                    )
                else:
                    self.log(
                        f"   ⚠️  Upload failed: {upload_result.get('error')}",
                        "WARNING"
                    )
            elif self.dry_run:
                self.log(f"   Step 4: Dry-run (skipping upload)", "DEBUG")
                result["steps"]["upload"] = {"skipped": True, "reason": "dry_run"}
            
            result["success"] = True
            
        except Exception as e:
            self.log(f"   ❌ Error processing miner: {e}", "ERROR")
            result["error"] = str(e)
            self.stats["errors"] += 1
        
        return result

    def run_once(
        self,
        upload: bool = True,
        max_videos: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run pipeline once for all current miners
        
        Args:
            upload: Whether to upload to BoTTube
            max_videos: Maximum number of videos to generate
            
        Returns:
            Batch processing results
        """
        self.log("🔄 Running pipeline iteration...")
        self.stats["last_attestation_check"] = datetime.utcnow().isoformat()
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "miners_processed": 0,
            "videos_generated": 0,
            "videos_uploaded": 0,
            "results": [],
        }
        
        try:
            # Get current miners
            self.log("📊 Fetching miner list from RustChain...")
            miners = self.rustchain_client.get_miners()
            self.log(f"   Found {len(miners)} active miners")
            
            # Get epoch info
            epoch_info = self.rustchain_client.get_epoch()
            self.log(f"   Current epoch: {epoch_info.get('epoch', '?')}")
            
            # Process miners
            miners_to_process = miners
            if max_videos:
                miners_to_process = miners[:max_videos]
                self.log(f"   Processing {len(miners_to_process)} miners (limit: {max_videos})")
            
            for miner in miners_to_process:
                result = self.process_miner(
                    miner_data=miner,
                    epoch_info=epoch_info,
                    upload=upload,
                )
                results["results"].append(result)
                results["miners_processed"] += 1
                
                if result.get("success"):
                    results["videos_generated"] += 1
                    if result.get("steps", {}).get("upload", {}).get("success"):
                        results["videos_uploaded"] += 1
                
                # Small delay between processing
                if miner != miners_to_process[-1]:
                    time.sleep(2.0)
            
        except Exception as e:
            self.log(f"❌ Pipeline iteration failed: {e}", "ERROR")
            results["error"] = str(e)
        
        return results

    def run_continuous(
        self,
        poll_interval: int = 300,  # 5 minutes
        upload: bool = True,
        max_iterations: Optional[int] = None,
    ) -> None:
        """
        Run pipeline continuously, monitoring for new attestations
        
        Args:
            poll_interval: Polling interval in seconds
            upload: Whether to upload to BoTTube
            max_iterations: Maximum iterations (None for infinite)
        """
        self.log("🔄 Starting continuous monitoring mode")
        self.log(f"   Poll interval: {poll_interval}s")
        self.log(f"   Upload enabled: {upload}")
        self.log(f"   Max iterations: {max_iterations or '∞'}")
        
        self.running = True
        self.stats["start_time"] = datetime.utcnow().isoformat()
        
        iteration = 0
        last_processed_miners = set()
        
        try:
            while self.running and (max_iterations is None or iteration < max_iterations):
                iteration += 1
                self.log(f"\n📍 Iteration {iteration}", "INFO")
                
                try:
                    # Get current miners
                    miners = self.rustchain_client.get_miners()
                    current_miner_ids = {m.get("miner") for m in miners}
                    
                    # Find new miners since last check
                    new_miner_ids = current_miner_ids - last_processed_miners
                    
                    if new_miner_ids:
                        self.log(f"🆕 Detected {len(new_miner_ids)} new miner(s)", "SUCCESS")
                        
                        # Process only new miners
                        new_miners = [
                            m for m in miners
                            if m.get("miner") in new_miner_ids
                        ]
                        
                        epoch_info = self.rustchain_client.get_epoch()
                        
                        for miner in new_miners:
                            result = self.process_miner(
                                miner_data=miner,
                                epoch_info=epoch_info,
                                upload=upload,
                            )
                            
                            if result.get("success"):
                                last_processed_miners.add(miner.get("miner"))
                    else:
                        self.log("   No new miners detected")
                    
                    # Update tracked miners
                    last_processed_miners = current_miner_ids & last_processed_miners
                    
                except Exception as e:
                    self.log(f"❌ Iteration error: {e}", "ERROR")
                    self.stats["errors"] += 1
                
                # Wait for next iteration
                if self.running and (max_iterations is None or iteration < max_iterations):
                    self.log(f"   ⏳ Waiting {poll_interval}s for next check...")
                    time.sleep(poll_interval)
            
            self.log("\n⏹️  Continuous monitoring stopped", "INFO")
            
        except KeyboardInterrupt:
            self.log("\n⏹️  Stopped by user", "INFO")
        finally:
            self.running = False
            self.print_stats()

    def generate_demo_videos(
        self,
        count: int = 10,
        upload: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Generate demo videos for bounty deliverable
        
        Args:
            count: Number of demo videos to generate
            upload: Whether to upload to BoTTube
            
        Returns:
            List of generation results
        """
        self.log(f"🎬 Generating {count} demo videos for bounty deliverable...")
        
        results = []
        
        # Create diverse demo miner profiles
        demo_miners = [
            {
                "miner": f"demo{i:03d}eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
                "device_arch": random.choice(["G4", "G3", "G5", "POWER7", "POWER8"]),
                "device_family": random.choice(["PowerPC", "IBM POWER"]),
                "hardware_type": random.choice([
                    "PowerPC G4 (Vintage)",
                    "PowerPC G3 (Retro)",
                    "PowerMac G5 (Aluminum)",
                    "IBM Power7 Server",
                    "IBM Power8 Datacenter",
                ]),
                "antiquity_multiplier": round(random.uniform(1.5, 3.5), 2),
                "entropy_score": 0.0,
                "last_attest": int(time.time()),
                "first_attest": int(time.time()) - 86400,
            }
            for i in range(count)
        ]
        
        epoch_info = {"epoch": 75, "slot": 10800}
        
        for i, miner in enumerate(demo_miners):
            self.log(f"\n📹 Generating demo video {i+1}/{count}")
            result = self.process_miner(
                miner_data=miner,
                epoch_info=epoch_info,
                upload=upload,
            )
            results.append(result)
        
        self.log(f"\n✅ Demo generation complete: {count} videos")
        
        return results

    def print_stats(self) -> None:
        """Print pipeline statistics"""
        print("\n" + "=" * 60)
        print("📊 PIPELINE STATISTICS")
        print("=" * 60)
        print(f"Start time:        {self.stats.get('start_time', 'N/A')}")
        print(f"Videos generated:  {self.stats['videos_generated']}")
        print(f"Videos uploaded:   {self.stats['videos_uploaded']}")
        print(f"Errors:            {self.stats['errors']}")
        print(f"Last check:        {self.stats.get('last_attestation_check', 'N/A')}")
        print("=" * 60)

    def stop(self) -> None:
        """Stop the pipeline"""
        self.log("🛑 Stopping pipeline...")
        self.running = False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Vintage AI Miner Video Pipeline - Issue #1855"
    )
    
    parser.add_argument(
        "--mode",
        choices=["once", "continuous", "demo"],
        default="once",
        help="Pipeline mode: once (single run), continuous (monitoring), demo (generate demos)"
    )
    
    parser.add_argument(
        "--rustchain-url",
        default="https://rustchain.org",
        help="RustChain API URL"
    )
    
    parser.add_argument(
        "--bottube-api-key",
        default=os.getenv("BOTTUBE_API_KEY"),
        help="BoTTube API key (or set BOTTUBE_API_KEY env var)"
    )
    
    parser.add_argument(
        "--video-backend",
        choices=["demo", "ltx-video", "cogvideo", "mochi"],
        default="demo",
        help="Video generation backend"
    )
    
    parser.add_argument(
        "--output-dir",
        default="./generated_videos",
        help="Output directory for generated videos"
    )
    
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=300,
        help="Polling interval in seconds (continuous mode)"
    )
    
    parser.add_argument(
        "--max-videos",
        type=int,
        default=None,
        help="Maximum number of videos to generate"
    )
    
    parser.add_argument(
        "--demo-count",
        type=int,
        default=10,
        help="Number of demo videos to generate (demo mode)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without actual uploads"
    )
    
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Disable uploads to BoTTube"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity"
    )
    
    args = parser.parse_args()
    
    # Create pipeline
    pipeline = VintageAIVideoPipeline(
        rustchain_url=args.rustchain_url,
        bottube_api_key=args.bottube_api_key,
        video_backend=args.video_backend,
        video_output_dir=args.output_dir,
        dry_run=args.dry_run,
        verbose=not args.quiet,
    )
    
    # Handle signals
    def signal_handler(sig, frame):
        pipeline.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run in specified mode
    if args.mode == "once":
        results = pipeline.run_once(
            upload=not args.no_upload,
            max_videos=args.max_videos,
        )
        print("\n📊 Results:")
        print(f"   Miners processed: {results['miners_processed']}")
        print(f"   Videos generated: {results['videos_generated']}")
        print(f"   Videos uploaded: {results['videos_uploaded']}")
        
    elif args.mode == "continuous":
        pipeline.run_continuous(
            poll_interval=args.poll_interval,
            upload=not args.no_upload,
            max_iterations=None,
        )
        
    elif args.mode == "demo":
        results = pipeline.generate_demo_videos(
            count=args.demo_count,
            upload=not args.no_upload,
        )
        success_count = sum(1 for r in results if r.get("success"))
        print(f"\n✅ Demo complete: {success_count}/{len(results)} successful")
    
    # Print final stats
    pipeline.print_stats()


if __name__ == "__main__":
    main()
