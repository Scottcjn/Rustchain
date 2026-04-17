#!/usr/bin/env python3
"""
Bounty Scanner - Lists and filters RustChain bounties
"""

import os
import json
import subprocess
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class BountyScanner:
    """Scans RustChain bounty repository for open issues."""

    def __init__(self, repo: str, min_bounty: int = 25, logger=None):
        self.repo = repo
        self.min_bounty = min_bounty
        self.logger = logger

    def scan_open_bounties(self) -> List[Dict]:
        """Scan for open bounties matching criteria."""
        try:
            # Use gh CLI to list issues
            cmd = [
                'gh', 'issue', 'list',
                '-R', self.repo,
                '-l', 'bounty',
                '--json', 'number,title,body,labels,createdAt,updatedAt'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                if self.logger:
                    self.logger.error(f"GitHub CLI error: {result.stderr}")
                return []
            
            issues = json.loads(result.stdout)
            bounties = []
            
            for issue in issues:
                bounty_info = self._parse_bounty_info(issue)
                if bounty_info and bounty_info['reward_rtc'] >= self.min_bounty:
                    bounties.append(bounty_info)
            
            # Sort by reward (highest first)
            bounties.sort(key=lambda x: x['reward_rtc'], reverse=True)
            
            if self.logger:
                self.logger.info(f"📊 Found {len(bounties)} bounties ≥{self.min_bounty} RTC")
            
            return bounties
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error scanning bounties: {e}")
            return []

    def get_specific_bounty(self, bounty_id: int) -> List[Dict]:
        """Get a specific bounty by ID."""
        try:
            cmd = [
                'gh', 'issue', 'view', str(bounty_id),
                '-R', self.repo,
                '--json', 'number,title,body,labels,createdAt,updatedAt'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                if self.logger:
                    self.logger.error(f"GitHub CLI error: {result.stderr}")
                return []
            
            issue = json.loads(result.stdout)
            bounty_info = self._parse_bounty_info(issue)
            
            if bounty_info:
                return [bounty_info]
            return []
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting bounty {bounty_id}: {e}")
            return []

    def _parse_bounty_info(self, issue: Dict) -> Optional[Dict]:
        """Parse bounty information from GitHub issue."""
        try:
            # Extract reward from title or labels
            reward_rtc = self._extract_reward(issue['title'], issue['labels'])
            
            # Skip if not a bounty or reward too low
            if not reward_rtc or reward_rtc < self.min_bounty:
                return None
            
            # Check if already claimed
            if self._is_claimed(issue):
                return None
            
            # Calculate age
            created = datetime.fromisoformat(issue['createdAt'].replace('Z', '+00:00'))
            age_days = (datetime.now().replace(tzinfo=created.tzinfo) - created).days
            
            return {
                'number': issue['number'],
                'title': issue['title'],
                'body': issue['body'],
                'labels': [l['name'] for l in issue['labels']],
                'created_at': issue['createdAt'],
                'updated_at': issue['updatedAt'],
                'reward_rtc': reward_rtc,
                'age_days': age_days,
                'url': f"https://github.com/{self.repo}/issues/{issue['number']}"
            }
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error parsing bounty: {e}")
            return None

    def _extract_reward(self, title: str, labels: List[Dict]) -> Optional[int]:
        """Extract reward amount from title or labels."""
        # Check title for bounty amount
        import re
        
        # Pattern: "[BOUNTY: 100 RTC]"
        match = re.search(r'\[BOUNTY:\s*(\d+)\s*RTC\]', title, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Pattern: "Reward: 100 RTC"
        match = re.search(r'Reward:\s*(\d+)\s*RTC', title, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Check labels
        for label in labels:
            name = label['name'].lower()
            if 'critical' in name:
                return 200  # Default for critical
            elif 'major' in name:
                return 50   # Default for major
            elif 'minor' in name:
                return 10   # Default for minor
        
        return None

    def _is_claimed(self, issue: Dict) -> bool:
        """Check if bounty is already claimed."""
        # Look for closed status or claim labels
        closed_labels = ['claimed', 'paid', 'completed', 'closed']
        
        for label in issue['labels']:
            if any(cl in label['name'].lower() for cl in closed_labels):
                return True
        
        # Check if issue is closed
        # Note: gh issue list only shows open issues by default
        # So if we got it, it's likely open
        
        return False