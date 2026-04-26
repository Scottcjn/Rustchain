// File: integrations/rustchain-bounties/bounty_tracker.py
#!/usr/bin/env python3
"""
RustChain Bounty Tracker

Manages bounty issues, claims, and payouts.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


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
        try:
            claimed_at_val = data.get("claimed_at")
            claimed_at = datetime.fromisoformat(claimed_at_val) if claimed_at_val else None

            paid_at_val = data.get("paid_at")
            paid_at = datetime.fromisoformat(paid_at_val) if paid_at_val else None

            return cls(
                issue_number=int(data["issue_number"]),
                title=str(data["title"]),
                description=str(data["description"]),
                reward_rtc=int(data["reward_rtc"]),  # Ensure integer conversion
                status=str(data.get("status", "open")),
                claimant=str(data.get("claimant")) if data.get("claimant") is not None else None,
                claimed_at=claimed_at,
                paid_at=paid_at,
                pr_url=str(data.get("pr_url")) if data.get("pr_url") is not None else None,
                labels=[str(label) for label in data.get("labels", [])],
            )
        except (KeyError, ValueError, TypeError) as e:
            raise ValueError(f"Invalid data for Bounty: {e}")


def load_bounty_definitions() -> List[Bounty]:
    """Load bounty definitions from file."""
    bounty_definitions_path = Path(__file__).parent / "bounty_definitions.json"
    
    if not bounty_definitions_path.exists():
        print(f"⚠️ Bounty definitions not found at {bounty_definitions_path}")
        return []
    
    with open(bounty_definitions_path, "r") as f:
        return [Bounty.from_dict(bounty) for bounty in json.load(f)]


def get_bounty(issue_number: int) -> Bounty:
    """Get bounty by issue number."""
    bounty_definitions = load_bounty_definitions()
    for bounty in bounty_definitions:
        if bounty.issue_number == issue_number:
            return bounty
    return None


def update_bounty_status(issue_number: int, status: str) -> None:
    """Update bounty status."""
    bounty = get_bounty(issue_number)
    if bounty:
        bounty.status = status
        # Save bounty definitions to file
        bounty_definitions_path = Path(__file__).parent / "bounty_definitions.json"
        with open(bounty_definitions_path, "w") as f:
            json.dump([bounty.to_dict() for bounty in load_bounty_definitions()], f)


def main():
    """Main entry point."""
    # Get inputs from environment
    issue_number = os.environ.get("INPUT_ISSUE_NUMBER", "")
    status = os.environ.get("INPUT_STATUS", "")
    
    if not all([issue_number, status]):
        print("⚠️ Missing required environment variables. Skipping update.")
        return
    
    update_bounty_status(int(issue_number), status)


if __name__ == "__main__":
    main()