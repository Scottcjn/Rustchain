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
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.bounties: Dict[int, Bounty] = {}
        self.load()

    def load(self):
        """Load bounties from JSON file"""
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text())
            self.bounties = {item["issue_number"]: Bounty.from_dict(item) for item in data}
        except (json.JSONDecodeError, KeyError, OSError) as e:
            print(f"⚠️ Failed to load bounty data: {e}")
            self.bounties = {}

    def save(self):
        """Persist bounties to JSON file"""
        try:
            serialized = [b.to_dict() for b in self.bounties.values()]
            self.storage_path.write_text(json.dumps(serialized, indent=2))
        except OSError as e:
            print(f"⚠️ Failed to save bounty data: {e}")
            raise

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

    def list_bounties(self, status: Optional[str] = None) -> List[Bounty]:
        bounties = list(self.bounties.values())
        if status is not None:
            bounties = [b for b in bounties if b.status == status]
        return bounties


def main():
    """Sync bounties from GitHub and update tracker state"""
    node_url = os.environ.get("INPUT_NODE_URL", "https://rustchain.org")
    repo = os.environ.get("REPO", "rustchain/bounties")
    token = os.environ.get("GITHUB_TOKEN")

    if not token:
        print("⚠️ GITHUB_TOKEN is required")
        return

    tracker_path = os.environ.get("TRACKER_PATH", "bounties.json")
    tracker = BountyTracker(tracker_path)

    # Fetch open bounty issues from GitHub
    issues_url = f"https://api.github.com/repos/{repo}/issues"
    request = Request(issues_url)
    request.add_header("Authorization", f"token {token}")
    request.add_header("Accept", "application/vnd.github.v3+json")

    try:
        response = urlopen(request)
        issues = json.load(response)
    except HTTPError as e:
        print(f"⚠️ Failed to fetch issues: {e}")
        return

    updated = False
    for issue in issues:
        if "bounty" not in [label.get("name", "").lower() for label in issue.get("labels", [])]:
            continue

        issue_number = issue["number"]
        existing = tracker.get_bounty(issue_number)

        # Extract bounty amount from title: "[Bounty: 500] Fix login bug"
        reward_rtc = 0
        title = issue["title"]
        if "[bounty:" in title.lower():
            try:
                reward_part = title.split("[bounty:")[1].split("]")[0]
                reward_rtc = int(reward_part.strip())
            except (IndexError, ValueError):
                pass

        # Create or update bounty
        if not existing:
            bounty = Bounty(
                issue_number=issue_number,
                title=title,
                description=issue.get("body", "")[:500],
                reward_rtc=reward_rtc,
                labels=[label["name"] for label in issue.get("labels", [])],
            )
            tracker.add_bounty(bounty)
            updated = True
        else:
            # Sync labels and title in case of edits
            if existing.title != title or set(existing.labels) != {label["name"] for label in issue.get("labels", [])}:
                existing.title = title
                existing.labels = [label["name"] for label in issue.get("labels", [])]
                # Re-extract reward if title changed
                if "[bounty:" in title.lower():
                    try:
                        reward_part = title.split("[bounty:")[1].split("]")[0]
                        existing.reward_rtc = int(reward_part.strip())
                    except (IndexError, ValueError):
                        pass
                tracker.update_bounty(existing)
                updated = True

    if updated:
        print("✅ Bounty tracker updated")
    else:
        print("✅ Bounty tracker is up to date")