// File: integrations/rustchain-bounties/bounty_tracker.py
#!/usr/bin/env python3
"""
RustChain Bounty Tracker

Manages bounty issues, claims, and payouts.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Bounty:
    """Bounty definition"""
    issue_number: int
    title: str
    description: str
    reward_rtc: int  # Use integer to avoid floating-point precision issues
    status: str = "open"  # open, claimed, completed, paid
    claimant: Optional[str] = None
    claimed_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    pr_url: Optional[str] = None
    labels: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "issue_number": self.issue_number,
            "title": self.title,
            "description": self.description,
            "reward_rtc": self.reward_rtc,
            "status": self.status,
            "claimant": self.claimant,
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "pr_url": self.pr_url,
            "labels": self.labels,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Bounty":
        claimed_at_val = data.get("claimed_at")
        claimed_at = datetime.fromisoformat(claimed_at_val) if claimed_at_val else None

        paid_at_val = data.get("paid_at")
        paid_at = datetime.fromisoformat(paid_at_val) if paid_at_val else None

        return cls(
            issue_number=data["issue_number"],
            title=data["title"],
            description=data["description"],
            reward_rtc=data["reward_rtc"],
            status=data.get("status", "open"),
            claimant=data.get("claimant"),
            claimed_at=claimed_at,
            paid_at=paid_at,
            pr_url=data.get("pr_url"),
            labels=data.get("labels", []),
        )


class BountyTracker:
    """Manages persistence and state of bounties"""

    def __init__(self, data_file: str = "bounties.json"):
        self.data_file = Path(data_file)
        self.bounties: Dict[int, Bounty] = {}
        self.load()

    def load(self):
        """Load bounties from disk"""
        if not self.data_file.exists():
            return

        try:
            with open(self.data_file, "r") as f:
                data = json.load(f)
                for item in data:
                    bounty = Bounty.from_dict(item)
                    self.bounties[bounty.issue_number] = bounty
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️ Failed to load bounty data: {e}")

    def save(self):
        """Persist bounties to disk"""
        try:
            with open(self.data_file, "w") as f:
                json.dump([b.to_dict() for b in self.bounties.values()], f, indent=2)
        except OSError as e:
            print(f"⚠️ Failed to save bounty data: {e}")

    def get_bounty(self, issue_number: int) -> Optional[Bounty]:
        return self.bounties.get(issue_number)

    def add_bounty(self, bounty: Bounty):
        self.bounties[bounty.issue_number] = bounty
        self.save()

    def update_bounty(self, bounty: Bounty):
        if bounty.issue_number not in self.bounties:
            raise ValueError(f"Bounty {bounty.issue_number} does not exist")
        self.bounties[bounty.issue_number] = bounty
        self.save()


def main():
    """Sync bounties with GitHub and process claims"""
    node_url = os.environ.get("INPUT_NODE_URL", "https://rustchain.org")
    repo = os.environ.get("REPO", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")

    if not repo or not github_token:
        print("⚠️ Missing REPO or GITHUB_TOKEN. Skipping bounty sync.")
        return

    tracker = BountyTracker()

    # Fetch open bounty issues from GitHub
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    url = f"https://api.github.com/repos/{repo}/issues"
    req = Request(url, headers=headers)
    
    try:
        with urlopen(req) as response:
            issues = json.load(response)
    except HTTPError as e:
        print(f"⚠️ Failed to fetch issues: {e}")
        return

    # Process each issue with bounty label
    for issue in issues:
        if "bounty" not in [label["name"] for label in issue.get("labels", [])]:
            continue

        issue_number = issue["number"]
        title = issue["title"]
        body = issue["body"] or ""
        reward_rtc = 100  # Default reward; could be parsed from body

        # Extract reward from body if specified
        for line in body.splitlines():
            if "Reward:" in line:
                try:
                    reward_rtc = int(line.split("Reward:")[1].strip().split()[0])
                except (IndexError, ValueError):
                    pass
                break

        if issue_number not in tracker.bounties:
            bounty = Bounty(
                issue_number=issue_number,
                title=title,
                description=body,
                reward_rtc=reward_rtc,
                labels=[label["name"] for label in issue.get("labels", [])],
            )
            tracker.add_bounty(bounty)
        else:
            bounty = tracker.get_bounty(issue_number)
            if bounty and bounty.status == "open" and bounty.claimant:
                # If claimant has submitted a PR, mark as completed
                if bounty.pr_url:
                    bounty.status = "completed"
                    tracker.update_bounty(bounty)

    # Payout completed bounties via RustChain
    for bounty in tracker.bounties.values():
        if bounty.status != "completed" or not bounty.claimant or bounty.paid_at:
            continue

        payout_data = {
            "to": bounty.claimant,
            "amount": bounty.reward_rtc,
            "reason": f"Bounty for issue #{bounty.issue_number}",
            "issue_number": bounty.issue_number,
            "schema": "bounty-payout/v1",
        }

        payout_url = f"{node_url}/api/payout"
        req = Request(payout_url, data=json.dumps(payout_data).encode(), headers=headers, method="POST")

        try:
            with urlopen(req) as response:
                result = json.load(response)
                if response.status == 200:
                    bounty.status = "paid"
                    bounty.paid_at = datetime.now(timezone.utc)
                    tracker.update_bounty(bounty)
                    print(f"✅ Paid {bounty.reward_rtc} RTC to {bounty.claimant} for issue #{bounty.issue_number}")
        except HTTPError as e:
            print(f"⚠️ Payout failed for issue #{bounty.issue_number}: {e}")