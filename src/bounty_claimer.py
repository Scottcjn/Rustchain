#!/usr/bin/env python3
"""
Bounty Claimer - Claims bounties after successful implementation
"""

import os
import json
import subprocess
import time
from typing import Dict, Optional


class BountyClaimer:
    """Claims bounties after successful implementation."""

    def __init__(self, wallet: str, logger=None):
        self.wallet = wallet
        self.logger = logger
        self.claimed_bounties = []

    def claim_bounty(self, bounty: Dict, pr_url: str, implementation: str) -> Dict:
        """Claim a bounty after implementation."""
        try:
            if self.logger:
                self.logger.info(f"💰 Claiming bounty #{bounty['number']} ({bounty['reward_rtc']} RTC)")
            
            # Add wallet to PR (if not already there)
            self._ensure_wallet_in_pr(bounty['number'], pr_url)
            
            # Add claim comment
            claim_comment = f"""🎉 **Bounty Claim**

**Wallet**: {self.wallet}
**Reward**: {bounty['reward_rtc']} RTC
**Implementation**: {implementation}
**PR**: {pr_url}

This bounty has been implemented by an autonomous AI agent.
"""
            
            cmd = [
                'gh', 'issue', 'comment', str(bounty['number']),
                '--repo', 'Scottcjn/rustchain-bounties',
                '--body', claim_comment
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f'Failed to add claim comment: {result.stderr}',
                    'claim_url': None
                }
            
            # Record claim
            claim_record = {
                'bounty_id': bounty['number'],
                'reward_rtc': bounty['reward_rtc'],
                'pr_url': pr_url,
                'wallet': self.wallet,
                'claimed_at': time.time(),
                'status': 'claimed'
            }
            
            self.claimed_bounties.append(claim_record)
            self._save_claims()
            
            if self.logger:
                self.logger.info(f"✅ Bounty claimed successfully!")
                self.logger.info(f"   Bounty: #{bounty['number']}")
                self.logger.info(f"   Reward: {bounty['reward_rtc']} RTC")
                self.logger.info(f"   Wallet: {self.wallet}")
                self.logger.info(f"   PR: {pr_url}")
            
            return {
                'success': True,
                'error': None,
                'claim_url': f"https://github.com/Scottcjn/rustchain-bounties/issues/{bounty['number']}"
            }
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"Bounty claim error: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'claim_url': None
            }

    def _ensure_wallet_in_pr(self, bounty_id: int, pr_url: str):
        """Ensure wallet is mentioned in PR."""
        try:
            # Extract PR number from URL
            import re
            pr_match = re.search(r'/pull/(\d+)', pr_url)
            if not pr_match:
                return
            
            pr_number = pr_match.group(1)
            
            # Add wallet comment to PR
            wallet_comment = f"🔑 **Wallet for Bounty Payout**: {self.wallet}"
            
            cmd = [
                'gh', 'pr', 'comment', pr_number,
                '--repo', 'Scottcjn/rustchain-bounties',
                '--body', wallet_comment
            ]
            
            subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to add wallet to PR: {e}")

    def _save_claims(self):
        """Save claim records to file."""
        try:
            claims_file = os.path.expanduser('~/.bounty_claims.json')
            
            # Load existing claims
            existing_claims = []
            if os.path.exists(claims_file):
                with open(claims_file, 'r') as f:
                    existing_claims = json.load(f)
            
            # Add new claims
            existing_claims.extend(self.claimed_bounties)
            
            # Save
            with open(claims_file, 'w') as f:
                json.dump(existing_claims, f, indent=2, default=str)
            
            # Clear in-memory records
            self.claimed_bounties = []
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to save claims: {e}")

    def get_total_earnings(self) -> int:
        """Get total earnings from claimed bounties."""
        try:
            claims_file = os.path.expanduser('~/.bounty_claims.json')
            
            if not os.path.exists(claims_file):
                return 0
            
            with open(claims_file, 'r') as f:
                claims = json.load(f)
            
            return sum(claim.get('reward_rtc', 0) for claim in claims)
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get earnings: {e}")
            return 0

    def get_claim_history(self) -> list:
        """Get history of claimed bounties."""
        try:
            claims_file = os.path.expanduser('~/.bounty_claims.json')
            
            if not os.path.exists(claims_file):
                return []
            
            with open(claims_file, 'r') as f:
                return json.load(f)
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get claim history: {e}")
            return []