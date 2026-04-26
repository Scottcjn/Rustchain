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
                issue_number=data["issue_number"],
                title=data["title"],
                description=data["description"],
                reward_rtc=int(data["reward_rtc"]),  # Ensure integer conversion
                status=data.get("status", "open"),
                claimant=data.get("claimant"),
                claimed_at=claimed_at,
                paid_at=paid_at,
                pr_url=data.get("pr_url"),
                labels=data.get("labels", []),
            )
        except (KeyError, ValueError, TypeError) as e:
            raise ValueError(f"Invalid data for Bounty: {e}") from e