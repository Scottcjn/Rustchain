#!/usr/bin/env python3
"""
Autonomous Bounty Hunter Agent - Main Entry Point

Scans RustChain bounties, evaluates feasibility, implements solutions, and claims rewards.
"""

import os
import sys
import json
import time
import argparse
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from bounty_scanner import BountyScanner
from llm_evaluator import LLMEvaluator
from task_executor import TaskExecutor
from bounty_claimer import BountyClaimer
from logger import setup_logger


class AutonomousBountyAgent:
    """Main agent that coordinates the bounty hunting workflow."""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.logger = setup_logger()
        
        # Initialize components
        self.scanner = BountyScanner(
            repo=self.config['target_repository'],
            min_bounty=self.config['min_bounty_rtc'],
            logger=self.logger
        )
        
        self.evaluator = LLMEvaluator(
            provider=self.config['llm_provider'],
            model=self.config['llm_model'],
            max_tokens=self.config['max_tokens'],
            temperature=self.config['temperature'],
            logger=self.logger
        )
        
        self.executor = TaskExecutor(
            wallet=self.config['rtc_wallet'],
            logger=self.logger
        )
        
        self.claimer = BountyClaimer(
            wallet=self.config['rtc_wallet'],
            logger=self.logger
        )

    def _load_config(self, config_path: str = None) -> Dict:
        """Load configuration from file or environment."""
        config = {
            'rtc_wallet': os.getenv('RTC_WALLET', 'zhaog100'),
            'min_bounty_rtc': int(os.getenv('MIN_BOUNTY_RTC', '25')),
            'max_complexity': int(os.getenv('MAX_COMPLEXITY', '8')),
            'target_repository': os.getenv('TARGET_REPOSITORY', 'Scottcjn/rustchain-bounties'),
            'llm_provider': os.getenv('LLM_PROVIDER', 'claude'),
            'llm_model': os.getenv('LLM_MODEL', 'claude-3-5-sonnet-20240620'),
            'max_tokens': int(os.getenv('MAX_TOKENS', '4000')),
            'temperature': float(os.getenv('TEMPERATURE', '0.7')),
        }
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
        
        return config

    def run(self, autonomous: bool = True, bounty_id: int = None, dry_run: bool = False) -> bool:
        """Run the bounty hunting workflow."""
        self.logger.info("🤖 Autonomous Bounty Hunter Agent Starting...")
        
        try:
            # Step 1: Scan for bounties
            self.logger.info("🔍 Scanning for open bounties...")
            if bounty_id:
                bounties = self.scanner.get_specific_bounty(bounty_id)
            else:
                bounties = self.scanner.scan_open_bounties()
            
            if not bounties:
                self.logger.warning("❌ No bounties found")
                return False
            
            self.logger.info(f"📋 Found {len(bounties)} bounties")
            
            for bounty in bounties:
                self.logger.info(f"\n🎯 Processing bounty #{bounty['number']}: {bounty['title']}")
                
                # Step 2: Evaluate feasibility
                self.logger.info("🧠 Evaluating feasibility...")
                evaluation = self.evaluator.evaluate_bounty(bounty)
                
                if not evaluation['recommended']:
                    self.logger.info(f"⏭️ Skipping: {evaluation['reason']}")
                    continue
                
                self.logger.info(f"✅ Recommended: {evaluation['confidence']:.1%} confidence")
                
                if dry_run:
                    self.logger.info("🏁 Dry run complete - would implement")
                    continue
                
                # Step 3: Execute task
                self.logger.info("🛠️ Implementing solution...")
                result = self.executor.execute_bounty(bounty, evaluation)
                
                if not result['success']:
                    self.logger.error(f"❌ Implementation failed: {result['error']}")
                    continue
                
                # Step 4: Claim bounty
                self.logger.info("💰 Claiming bounty...")
                claim_result = self.claimer.claim_bounty(
                    bounty=bounty,
                    pr_url=result['pr_url'],
                    implementation=result['summary']
                )
                
                if claim_result['success']:
                    self.logger.info(f"🎉 Success! Claimed {bounty['reward_rtc']} RTC")
                    self.logger.info(f"   PR: {result['pr_url']}")
                    self.logger.info(f"   Wallet: {self.config['rtc_wallet']}")
                else:
                    self.logger.error(f"❌ Claim failed: {claim_result['error']}")
                
                # Rate limiting
                if autonomous:
                    time.sleep(3600)  # Wait 1 hour between bounties
            
            return True
            
        except Exception as e:
            self.logger.error(f"💥 Agent crashed: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Autonomous Bounty Hunter Agent')
    parser.add_argument('--autonomous', action='store_true', help='Run in autonomous mode')
    parser.add_argument('--bounty', type=int, help='Process specific bounty ID')
    parser.add_argument('--dry-run', action='store_true', help='Evaluate without implementing')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--config', type=str, help='Configuration file path')
    
    args = parser.parse_args()
    
    # Initialize agent
    agent = AutonomousBountyAgent(config_path=args.config)
    
    # Run
    success = agent.run(
        autonomous=args.autonomous,
        bounty_id=args.bounty,
        dry_run=args.dry_run
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()