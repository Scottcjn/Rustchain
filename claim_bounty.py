#!/usr/bin/env python3
"""
Script to claim the RustChain bounty by starring the repo and leaving a review comment.
Requirements:
- GitHub personal access token with 'public_repo' scope.
- PyGithub installed (pip install PyGithub).

Usage:
  python claim_bounty.py <wallet_id> "<review comment>"

Example:
  python claim_bounty.py 0xAbC123 "I reviewed the mining module in src/miner.rs. The proof-of-work implementation is clean and well-documented. I received RTC compensation for this review."
"""
import sys
import os
from github import Github

# Configuration
REPO = "Scottcjn/Rustchain"
ISSUE_NUMBER = 1  # The issue where comments must be posted (update if different)

def main():
    if len(sys.argv) < 3:
        print("Usage: claim_bounty.py <wallet_id> \"<comment>\"")
        sys.exit(1)

    wallet_id = sys.argv[1]
    comment = sys.argv[2]

    # Ensure comment includes disclosure
    disclosure = "I received RTC compensation for this review."
    if disclosure not in comment:
        comment += f"\n\n{disclosure}"

    # Get token from environment
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set.")
        sys.exit(1)

    g = Github(token)
    repo = g.get_repo(REPO)

    # Star the repo
    print("Starring repository...")
    user = g.get_user()
    user.add_to_starred(repo)
    print("Starred successfully.")

    # Post comment on the issue
    print("Posting comment...")
    issue = repo.get_issue(ISSUE_NUMBER)
    # Append wallet ID to comment (if not already present)
    if wallet_id not in comment:
        comment += f"\n\nWallet ID: {wallet_id}"
    issue.create_comment(comment)
    print("Comment posted successfully.")

if __name__ == "__main__":
    main()
