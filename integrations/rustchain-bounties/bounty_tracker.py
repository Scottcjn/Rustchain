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
    """Manages lifecycle of bounties via GitHub and internal state"""
    
    def __init__(self, github_token: str, repo: str, state_file: Path):
        self.github_token = github_token
        self.repo = repo
        self.state_file = state_file
        self.bounties: Dict[int, Bounty] = self._load_state()

    def _load_state(self) -> Dict[int, Bounty]:
        """Load bounty state from JSON file"""
        if not self.state_file.exists():
            return {}
        try:
            data = json.loads(self.state_file.read_text())
            return {item["issue_number"]: Bounty.from_dict(item) for item in data}
        except (json.JSONDecodeError, KeyError, OSError) as e:
            print(f"⚠️ Failed to load bounty state: {e}")
            return {}

    def _save_state(self):
        """Persist current bounties to disk"""
        data = [b.to_dict() for b in self.bounties.values()]
        self.state_file.write_text(json.dumps(data, indent=2))

    def fetch_issue(self, issue_number: int) -> Optional[Dict[str, Any]]:
        """Fetch issue details from GitHub API"""
        url = f"https://api.github.com/repos/{self.repo}/issues/{issue_number}"
        request = Request(url)
        request.add_header("Authorization", f"token {self.github_token}")
        request.add_header("Accept", "application/vnd.github.v3+json")
        try:
            with urlopen(request) as response:
                return json.load(response)
        except HTTPError as e:
            print(f"⚠️ GitHub API error: {e}")
            return None

    def create_bounty(self, issue_number: int) -> bool:
        """Create a new bounty from an issue"""
        issue = self.fetch_issue(issue_number)
        if not issue:
            return False
        if issue_number in self.bounties:
            print(f"⚠️ Bounty already exists for issue #{issue_number}")
            return False
        labels = [label["name"] for label in issue.get("labels", [])]
        bounty = Bounty(
            issue_number=issue_number,
            title=issue["title"],
            description=issue["body"] or "",
            reward_rtc=self._parse_reward_from_labels(labels),
            labels=labels,
        )
        self.bounties[issue_number] = bounty
        self._save_state()
        print(f"✅ Created bounty for issue #{issue_number}")
        return True

    def _parse_reward_from_labels(self, labels: List[str]) -> int:
        """Extract RTC reward from label (e.g., 'bounty-500')"""
        for label in labels:
            if label.startswith("bounty-"):
                try:
                    return int(label.split("-")[1])
                except ValueError:
                    continue
        return 0

    def claim_bounty(self, issue_number: int, claimant: str) -> bool:
        """Claim an open bounty"""
        bounty = self.bounties.get(issue_number)
        if not bounty:
            print(f"⚠️ No bounty found for issue #{issue_number}")
            return False
        if bounty.status != "open":
            print(f"⚠️ Bounty #{issue_number} is not open (status: {bounty.status})")
            return False
        bounty.status = "claimed"
        bounty.claimant = claimant
        bounty.claimed_at = datetime.now(timezone.utc)
        self._save_state()
        print(f"✅ {claimant} claimed bounty #{issue_number}")
        return True

    def complete_bounty(self, issue_number: int, pr_url: str) -> bool:
        """Mark bounty as completed with PR reference"""
        bounty = self.bounties.get(issue_number)
        if not bounty:
            print(f"⚠️ No bounty found for issue #{issue_number}")
            return False
        if bounty.status != "claimed":
            print(f"⚠️ Bounty #{issue_number} is not claimed (status: {bounty.status})")
            return False
        bounty.status = "completed"
        bounty.pr_url = pr_url
        self._save_state()
        print(f"✅ Bounty #{issue_number} completed with PR {pr_url}")
        return True

    def pay_bounty(self, issue_number: int) -> bool:
        """Mark bounty as paid and record payout time"""
        bounty = self.bounties.get(issue_number)
        if not bounty:
            print(f"⚠️ No bounty found for issue #{issue_number}")
            return False
        if bounty.status != "completed":
            print(f"⚠️ Bounty #{issue_number} is not completed (status: {bounty.status})")
            return False
        bounty.status = "paid"
        bounty.paid_at = datetime.now(timezone.utc)
        self._save_state()
        print(f"✅ Bounty #{issue_number} paid to {bounty.claimant}")
        return True


def main():
    """Main entry point for bounty tracker"""
    github_token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("REPO", "rust-lang/rust")
    state_file_path = os.environ.get("STATE_FILE", "./bounties.json")

    if not github_token:
        print("⚠️ GITHUB_TOKEN environment variable is required")
        return

    state_file = Path(state_file_path)
    tracker = BountyTracker(github_token, repo, state_file)

    command = os.environ.get("COMMAND")
    if not command:
        print("⚠️ COMMAND environment variable is required")
        return

    issue_number_str = os.environ.get("ISSUE_NUMBER")
    if not issue_number_str:
        print("⚠️ ISSUE_NUMBER environment variable is required")
        return
    try:
        issue_number = int(issue_number_str)
    except ValueError:
        print("⚠️ ISSUE_NUMBER must be an integer")
        return

    if command == "create":
        tracker.create_bounty(issue_number)
    elif command == "claim":
        claimant = os.environ.get("CLAIMANT")
        if not claimant:
            print("⚠️ CLAIMANT environment variable is required for claim")
            return
        tracker.claim_bounty(issue_number, claimant)
    elif command == "complete":
        pr_url = os.environ.get("PR_URL")
        if not pr_url:
            print("⚠️ PR_URL environment variable is required for completion")
            return
        tracker.complete_bounty(issue_number, pr_url)
    elif command == "pay":
        tracker.pay_bounty(issue_number)
    else:
        print(f"⚠️ Unknown command: {command}")