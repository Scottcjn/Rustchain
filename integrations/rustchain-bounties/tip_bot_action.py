#!/usr/bin/env python3
"""
GitHub Action script to process tip commands.
Called by the tip-bot.yml workflow.
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from integrations.rustchain-bounties.tip_bot import TipBot


def main():
    """Process tip command from GitHub event"""
    
    # Get event payload
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        print("Error: GITHUB_EVENT_PATH not set")
        return 1
    
    with open(event_path, "r") as f:
        payload = json.load(f)
    
    # Get event name
    event_name = os.getenv("GITHUB_EVENT_NAME", "issue_comment")
    
    # Get GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("Error: GITHUB_TOKEN not set")
        return 1
    
    # Get payout wallet (default to split createkr-wallet)
    payout_wallet = os.getenv(
        "TIP_BOT_WALLET",
        "RTC1d48d848a5aa5ecf2c5f01aa5fb64837daaf2f35"
    )
    
    # Initialize bot
    bot = TipBot(
        github_token=github_token,
        payout_wallet=payout_wallet,
        dry_run=os.getenv("TIP_BOT_DRY_RUN", "false").lower() == "true",
    )
    
    # Process webhook
    action = bot.handle_webhook(event_name, payload)
    
    if action:
        # Post response comment
        from github import Github
        
        gh = Github(github_token)
        repo = gh.get_repo(action["repo"])
        issue = repo.get_issue(action["issue_number"])
        
        try:
            issue.create_comment(action["body"])
            print(f"Posted tip response to #{action['issue_number']}")
        except Exception as e:
            print(f"Error posting comment: {e}")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
