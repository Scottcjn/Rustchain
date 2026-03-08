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
    reward_rtc: float
    status: str = "open"  # open, claimed, completed, paid
    claimant: Optional[str] = None
    claimed_at: Optional[str] = None
    paid_at: Optional[str] = None
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
            "claimed_at": self.claimed_at,
            "paid_at": self.paid_at,
            "pr_url": self.pr_url,
            "labels": self.labels,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Bounty":
        return cls(
            issue_number=data.get("issue_number", 0),
            title=data.get("title", ""),
            description=data.get("description", ""),
            reward_rtc=data.get("reward_rtc", 0.0),
            status=data.get("status", "open"),
            claimant=data.get("claimant"),
            claimed_at=data.get("claimed_at"),
            paid_at=data.get("paid_at"),
            pr_url=data.get("pr_url"),
            labels=data.get("labels", []),
        )


class BountyTracker:
    """Track and manage RustChain bounties"""
    
    BOUNTY_LABELS = ["bounty", "bounty-claim", "bounty-open"]
    
    def __init__(
        self,
        github_token: str,
        repo: str = "Scottcjn/Rustchain",
        state_file: Optional[str] = None,
    ):
        self.github_token = github_token
        self.repo = repo
        self.state_file = state_file or "bounty_tracker_state.json"
        self.bounties: Dict[int, Bounty] = {}
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "rustchain-bounty-tracker/1.0",
        })
        self._load_state()
    
    def _load_state(self):
        """Load state from file"""
        path = Path(self.state_file)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for b_data in data.get("bounties", []):
                    bounty = Bounty.from_dict(b_data)
                    self.bounties[bounty.issue_number] = bounty
            except (json.JSONDecodeError, KeyError):
                pass
    
    def _save_state(self):
        """Save state to file"""
        path = Path(self.state_file)
        data = {
            "bounties": [b.to_dict() for b in self.bounties.values()],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    
    def scan_bounties(self) -> List[Bounty]:
        """Scan repo for bounty issues"""
        url = f"https://api.github.com/search/issues"
        params = {
            "q": f"repo:{self.repo} is:issue state:open label:bounty",
            "per_page": 100,
        }
        
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            for item in data.get("items", []):
                issue_number = item.get("number")
                if issue_number in self.bounties:
                    continue
                
                # Parse reward from issue body or labels
                reward = self._parse_reward(item.get("body", ""), item.get("labels", []))
                
                bounty = Bounty(
                    issue_number=issue_number,
                    title=item.get("title", ""),
                    description=item.get("body", "")[:500],
                    reward_rtc=reward,
                    labels=[l.get("name") for l in item.get("labels", [])],
                )
                self.bounties[issue_number] = bounty
            
            self._save_state()
            return list(self.bounties.values())
            
        except Exception as e:
            print(f"[Error] Failed to scan bounties: {e}")
            return []
    
    def _parse_reward(self, body: str, labels: List[Dict]) -> float:
        """Parse reward amount from issue body or labels"""
        import re
        
        # Try to parse from body
        patterns = [
            r"(\d+(?:\.\d+)?)\s*RTC",
            r"reward[:\s]+(\d+(?:\.\d+)?)",
            r"bounty[:\s]+(\d+(?:\.\d+)?)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, body or "", re.IGNORECASE)
            if match:
                return float(match.group(1))
        
        # Default rewards by label
        label_names = [l.get("name", "") for l in labels] if isinstance(labels[0], dict) else labels
        
        if "bounty-critical" in label_names:
            return 150.0
        elif "bounty-major" in label_names:
            return 100.0
        elif "bounty-standard" in label_names:
            return 50.0
        elif "bounty-micro" in label_names:
            return 10.0
        
        return 25.0  # Default
    
    def claim_bounty(
        self,
        issue_number: int,
        claimant: str,
        pr_url: Optional[str] = None,
    ) -> Optional[Bounty]:
        """Mark a bounty as claimed"""
        if issue_number not in self.bounties:
            return None
        
        bounty = self.bounties[issue_number]
        bounty.status = "claimed"
        bounty.claimant = claimant
        bounty.claimed_at = datetime.now(timezone.utc).isoformat()
        bounty.pr_url = pr_url
        
        self._save_state()
        return bounty
    
    def complete_bounty(self, issue_number: int) -> Optional[Bounty]:
        """Mark a bounty as completed (ready for payout)"""
        if issue_number not in self.bounties:
            return None
        
        bounty = self.bounties[issue_number]
        bounty.status = "completed"
        
        self._save_state()
        return bounty
    
    def mark_paid(self, issue_number: int) -> Optional[Bounty]:
        """Mark a bounty as paid"""
        if issue_number not in self.bounties:
            return None
        
        bounty = self.bounties[issue_number]
        bounty.status = "paid"
        bounty.paid_at = datetime.now(timezone.utc).isoformat()
        
        self._save_state()
        return bounty
    
    def get_pending_claims(self) -> List[Bounty]:
        """Get all pending claims"""
        return [
            b for b in self.bounties.values()
            if b.status in ("claimed", "completed")
        ]
    
    def get_total_pending(self) -> float:
        """Get total RTC pending for payout"""
        return sum(b.reward_rtc for b in self.get_pending_claims())
    
    def get_summary(self) -> str:
        """Get bounty summary"""
        total = len(self.bounties)
        open_count = sum(1 for b in self.bounties.values() if b.status == "open")
        claimed_count = sum(1 for b in self.bounties.values() if b.status == "claimed")
        completed_count = sum(1 for b in self.bounties.values() if b.status == "completed")
        paid_count = sum(1 for b in self.bounties.values() if b.status == "paid")
        pending_rtc = self.get_total_pending()
        
        return (
            f"📊 **RustChain Bounty Summary**\n\n"
            f"- **Total Bounties:** {total}\n"
            f"- **Open:** {open_count}\n"
            f"- **Claimed:** {claimed_count}\n"
            f"- **Completed:** {completed_count}\n"
            f"- **Paid:** {paid_count}\n"
            f"- **Pending Payout:** {pending_rtc:.2f} RTC\n"
        )


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RustChain Bounty Tracker")
    parser.add_argument("--token", help="GitHub token")
    parser.add_argument("--repo", default="Scottcjn/Rustchain", help="GitHub repo")
    parser.add_argument("--state-file", default="bounty_tracker_state.json",
                       help="State file path")
    parser.add_argument("--scan", action="store_true", help="Scan for bounties")
    parser.add_argument("--summary", action="store_true", help="Show summary")
    parser.add_argument("--pending", action="store_true", help="Show pending claims")
    
    args = parser.parse_args()
    
    token = args.token or os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN required")
        return 1
    
    tracker = BountyTracker(
        github_token=token,
        repo=args.repo,
        state_file=args.state_file,
    )
    
    if args.scan:
        bounties = tracker.scan_bounties()
        print(f"Found {len(bounties)} bounties")
        for b in bounties[:10]:
            print(f"  #{b.issue_number}: {b.title[:50]} ({b.reward_rtc} RTC)")
        return 0
    
    if args.summary:
        print(tracker.get_summary())
        return 0
    
    if args.pending:
        pending = tracker.get_pending_claims()
        if not pending:
            print("No pending claims")
        else:
            for b in pending:
                print(f"  #{b.issue_number}: {b.claimant} - {b.reward_rtc} RTC")
        return 0
    
    print("Bounty tracker initialized. Use --scan, --summary, or --pending.")
    return 0


if __name__ == "__main__":
    exit(main())
