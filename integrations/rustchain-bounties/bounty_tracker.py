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
    """Manages persistence and operations on bounties"""
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.bounties: Dict[int, Bounty] = {}
        self._load()

    def _load(self):
        """Load bounties from JSON file"""
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text())
            for item in data:
                bounty = Bounty.from_dict(item)
                self.bounties[bounty.issue_number] = bounty
        except (json.JSONDecodeError, KeyError, OSError) as e:
            print(f"❌ Failed to load bounty data: {e}")
            raise

    def _save(self):
        """Persist bounties to JSON file"""
        try:
            serialized = [b.to_dict() for b in self.bounties.values()]
            self.storage_path.write_text(json.dumps(serialized, indent=2))
        except (OSError, TypeError) as e:
            print(f"❌ Failed to save bounty data: {e}")
            raise

    def get_bounty(self, issue_number: int) -> Optional[Bounty]:
        return self.bounties.get(issue_number)

    def create_bounty(self, bounty: Bounty):
        if bounty.issue_number in self.bounties:
            raise ValueError(f"Bounty for issue #{bounty.issue_number} already exists")
        self.bounties[bounty.issue_number] = bounty
        self._save()

    def update_bounty(self, bounty: Bounty):
        if bounty.issue_number not in self.bounties:
            raise ValueError(f"No bounty found for issue #{bounty.issue_number}")
        self.bounties[bounty.issue_number] = bounty
        self._save()

    def list_bounties(self, status: Optional[str] = None) -> List[Bounty]:
        filtered = self.bounties.values()
        if status is not None:
            filtered = [b for b in filtered if b.status == status]
        return sorted(filtered, key=lambda b: b.issue_number)


def post_bounty_update(bounty: Bounty, webhook_url: str):
    """Send bounty update to external webhook"""
    payload = bounty.to_dict()
    req = Request(webhook_url, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req) as res:
            res.read()
    except HTTPError as e:
        print(f"❌ Webhook delivery failed: {e}")
        raise


def main():
    """Run bounty tracker operations based on environment inputs"""
    # Get inputs from environment
    mode = os.environ.get("MODE", "")
    storage_path = os.environ.get("STORAGE_PATH", "bounties.json")
    webhook_url = os.environ.get("WEBHOOK_URL", "")

    tracker = BountyTracker(storage_path)

    if mode == "create":
        issue_number = int(os.environ["ISSUE_NUMBER"])
        title = os.environ["TITLE"]
        description = os.environ["DESCRIPTION"]
        reward_rtc = int(os.environ["REWARD_RTC"])
        labels = os.environ.get("LABELS", "").split(",") if os.environ.get("LABELS") else []

        bounty = Bounty(
            issue_number=issue_number,
            title=title,
            description=description,
            reward_rtc=reward_rtc,
            labels=[label.strip() for label in labels if label.strip()]
        )
        tracker.create_bounty(bounty)
        if webhook_url:
            post_bounty_update(bounty, webhook_url)

    elif mode == "claim":
        issue_number = int(os.environ["ISSUE_NUMBER"])
        claimant = os.environ["CLAIMANT"]
        bounty = tracker.get_bounty(issue_number)
        if not bounty:
            raise ValueError(f"No bounty found for issue #{issue_number}")
        if bounty.status != "open":
            raise ValueError(f"Bounty #{issue_number} is not open")
        bounty.status = "claimed"
        bounty.claimant = claimant
        bounty.claimed_at = datetime.now(timezone.utc)
        tracker.update_bounty(bounty)
        if webhook_url:
            post_bounty_update(bounty, webhook_url)

    elif mode == "complete":
        issue_number = int(os.environ["ISSUE_NUMBER"])
        pr_url = os.environ["PR_URL"]
        bounty = tracker.get_bounty(issue_number)
        if not bounty:
            raise ValueError(f"No bounty found for issue #{issue_number}")
        if bounty.status != "claimed":
            raise ValueError(f"Bounty #{issue_number} is not claimed")
        bounty.status = "completed"
        bounty.pr_url = pr_url
        tracker.update_bounty(bounty)
        if webhook_url:
            post_bounty_update(bounty, webhook_url)

    elif mode == "pay":
        issue_number = int(os.environ["ISSUE_NUMBER"])
        bounty = tracker.get_bounty(issue_number)
        if not bounty:
            raise ValueError(f"No bounty found for issue #{issue_number}")
        if bounty.status != "completed":
            raise ValueError(f"Bounty #{issue_number} is not completed")
        bounty.status = "paid"
        bounty.paid_at = datetime.now(timezone.utc)
        tracker.update_bounty(bounty)
        if webhook_url:
            post_bounty_update(bounty, webhook_url)

    elif mode == "list":
        status_filter = os.environ.get("FILTER_STATUS")
        bounties = tracker.list_bounties(status=status_filter)
        for b in bounties:
            print(f"#{b.issue_number} {b.title} [{b.status}] ({b.reward_rtc} RTC)")

    else:
        print(f"❌ Unknown mode: {mode}")
        exit(1)