#!/usr/bin/env python3
"""
RustChain GitHub Tip Bot

Handles /tip commands in GitHub issues for bounty payouts.
Supports command patterns:
  /tip @username <amount> RTC
  /tip claim @username <amount> RTC
  /tip status
  /tip help
"""

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


@dataclass
class TipRecord:
    """Record of a tip transaction"""
    issue_number: int
    from_user: str
    to_user: str
    amount_rtc: float
    timestamp: str
    tx_hash: str = ""
    status: str = "pending"  # pending, completed, failed
    memo: str = ""


@dataclass
class BountyState:
    """State of the bounty system"""
    total_distributed: float = 0.0
    tips: List[TipRecord] = field(default_factory=list)
    pending_claims: Dict[int, Dict] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "total_distributed": self.total_distributed,
            "tips": [
                {
                    "issue_number": t.issue_number,
                    "from_user": t.from_user,
                    "to_user": t.to_user,
                    "amount_rtc": t.amount_rtc,
                    "timestamp": t.timestamp,
                    "tx_hash": t.tx_hash,
                    "status": t.status,
                    "memo": t.memo,
                }
                for t in self.tips
            ],
            "pending_claims": self.pending_claims,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "BountyState":
        state = cls()
        state.total_distributed = data.get("total_distributed", 0.0)
        state.tips = [
            TipRecord(
                issue_number=t["issue_number"],
                from_user=t["from_user"],
                to_user=t["to_user"],
                amount_rtc=t["amount_rtc"],
                timestamp=t["timestamp"],
                tx_hash=t.get("tx_hash", ""),
                status=t.get("status", "pending"),
                memo=t.get("memo", ""),
            )
            for t in data.get("tips", [])
        ]
        state.pending_claims = data.get("pending_claims", {})
        return state


class TipBot:
    """GitHub Tip Bot for RustChain bounties"""
    
    TIP_PATTERN = re.compile(
        r"/tip\s+(?:claim\s+)?(@?\w+)\s+(\d+(?:\.\d+)?)\s*(RTC|rtc)?",
        re.IGNORECASE
    )
    
    def __init__(
        self,
        github_token: str,
        payout_wallet: str,
        state_file: Optional[str] = None,
        dry_run: bool = False,
    ):
        self.github_token = github_token
        self.payout_wallet = payout_wallet
        self.dry_run = dry_run
        self.state_file = state_file or "bounty_state.json"
        self.state = self._load_state()
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "rustchain-tip-bot/1.0",
        })
    
    def _load_state(self) -> BountyState:
        """Load state from file"""
        path = Path(self.state_file)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return BountyState.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return BountyState()
    
    def _save_state(self):
        """Save state to file"""
        path = Path(self.state_file)
        path.write_text(
            json.dumps(self.state.to_dict(), indent=2),
            encoding="utf-8"
        )
    
    def verify_webhook_signature(
        self, payload: bytes, signature: str, secret: str
    ) -> bool:
        """Verify GitHub webhook signature"""
        if not signature or not secret:
            return False
        
        expected = "sha256=" + hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
    
    def parse_tip_command(self, comment_body: str) -> Optional[Tuple[str, float]]:
        """Parse /tip command from comment body"""
        if not comment_body:
            return None
        
        for line in comment_body.split("\n"):
            line = line.strip()
            if line.startswith("/tip"):
                match = self.TIP_PATTERN.match(line)
                if match:
                    recipient = match.group(1).lstrip("@")
                    amount = float(match.group(2))
                    return (recipient, amount)
        
        return None
    
    def get_issue(self, repo: str, issue_number: int) -> Optional[Dict]:
        """Get issue details"""
        url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[Error] Failed to get issue: {e}")
            return None
    
    def get_user(self, username: str) -> Optional[Dict]:
        """Get GitHub user details"""
        url = f"https://api.github.com/users/{username.lstrip('@')}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[Error] Failed to get user: {e}")
            return None
    
    def post_comment(self, repo: str, issue_number: int, body: str) -> bool:
        """Post comment to issue"""
        url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
        try:
            resp = self.session.post(url, json={"body": body}, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            print(f"[Error] Failed to post comment: {e}")
            return False
    
    def generate_tx_hash(self, issue_number: int, recipient: str, amount: float) -> str:
        """Generate a deterministic tx hash for tracking"""
        data = f"{issue_number}:{recipient}:{amount}:{self.payout_wallet}"
        return "0x" + hashlib.sha256(data.encode()).hexdigest()[:40]
    
    def process_tip(
        self,
        repo: str,
        issue_number: int,
        commenter: str,
        comment_body: str,
        comment_id: int,
    ) -> Optional[str]:
        """
        Process a tip command from a comment.
        Returns response message or None if no action needed.
        """
        tip_data = self.parse_tip_command(comment_body)
        if not tip_data:
            return None
        
        recipient, amount = tip_data
        
        # Validate amount
        if amount <= 0:
            return "❌ Invalid tip amount. Must be positive."
        
        if amount > 1000:
            return "❌ Tip amount exceeds maximum (1000 RTC). Contact admin for larger tips."
        
        # Validate recipient
        user_data = self.get_user(recipient)
        if not user_data:
            return f"❌ User @{recipient} not found on GitHub."
        
        recipient_username = user_data.get("login", recipient)
        
        # Check permissions (commenter must be repo collaborator or issue author)
        issue = self.get_issue(repo, issue_number)
        if not issue:
            return "❌ Issue not found."
        
        issue_author = issue.get("user", {}).get("login", "")
        is_authorized = (
            commenter == issue_author or
            self._is_collaborator(repo, commenter)
        )
        
        if not is_authorized and not self._is_admin(commenter):
            return "❌ Only issue author or collaborators can issue tips."
        
        # Generate tx hash
        tx_hash = self.generate_tx_hash(issue_number, recipient_username, amount)
        
        # Record tip
        tip = TipRecord(
            issue_number=issue_number,
            from_user=commenter,
            to_user=recipient_username,
            amount_rtc=amount,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tx_hash=tx_hash,
            status="completed" if not self.dry_run else "pending",
            memo=f"Tip for issue #{issue_number}",
        )
        
        self.state.tips.append(tip)
        self.state.total_distributed += amount
        self._save_state()
        
        # Format response
        if self.dry_run:
            response = (
                f"✅ **Tip Recorded (Dry Run)**\n\n"
                f"- **From:** @{commenter}\n"
                f"- **To:** @{recipient_username}\n"
                f"- **Amount:** {amount:.2f} RTC\n"
                f"- **Issue:** #{issue_number}\n"
                f"- **TX Hash:** `{tx_hash}`\n"
                f"- **Status:** Pending (dry run mode)\n"
                f"- **Payout Wallet:** `{self.payout_wallet}`\n\n"
                f"_Tip will be processed when dry run is disabled._"
            )
        else:
            response = (
                f"✅ **Tip Sent!**\n\n"
                f"- **From:** @{commenter}\n"
                f"- **To:** @{recipient_username}\n"
                f"- **Amount:** {amount:.2f} RTC\n"
                f"- **Issue:** #{issue_number}\n"
                f"- **TX Hash:** `{tx_hash}`\n"
                f"- **Payout Wallet:** `{self.payout_wallet}`\n\n"
                f"_Bounty payout will be processed in the next distribution cycle._"
            )
        
        return response
    
    def _is_collaborator(self, repo: str, username: str) -> bool:
        """Check if user is a collaborator"""
        url = f"https://api.github.com/repos/{repo}/collaborators/{username}"
        try:
            resp = self.session.get(url, timeout=10)
            return resp.status_code == 204
        except Exception:
            return False
    
    def _is_admin(self, username: str) -> bool:
        """Check if user is admin (configured via env)"""
        admins = os.getenv("TIP_BOT_ADMINS", "").split(",")
        return username in admins
    
    def get_status(self, repo: str) -> str:
        """Get tip bot status"""
        total_tips = len(self.state.tips)
        total_distributed = self.state.total_distributed
        
        recent_tips = self.state.tips[-5:] if self.state.tips else []
        recent_lines = []
        for tip in recent_tips:
            recent_lines.append(
                f"- @{tip.to_user}: {tip.amount_rtc:.2f} RTC (#{tip.issue_number})"
            )
        
        recent_text = "\n".join(recent_lines) if recent_lines else "No tips yet."
        
        return (
            f"📊 **RustChain Tip Bot Status**\n\n"
            f"- **Total Tips:** {total_tips}\n"
            f"- **Total Distributed:** {total_distributed:.2f} RTC\n"
            f"- **Payout Wallet:** `{self.payout_wallet}`\n"
            f"- **Mode:** {'Dry Run' if self.dry_run else 'Live'}\n\n"
            f"**Recent Tips:**\n{recent_text}"
        )
    
    def get_help(self) -> str:
        """Get help message"""
        return (
            "🤖 **RustChain Tip Bot Commands**\n\n"
            "```\n"
            "/tip @username <amount> RTC    - Send a tip to a user\n"
            "/tip claim @user <amt> RTC     - Claim a bounty tip\n"
            "/tip status                    - Show bot status\n"
            "/tip help                      - Show this help\n"
            "```\n\n"
            "**Examples:**\n"
            "- `/tip @contributor 50 RTC` - Tip 50 RTC\n"
            "- `/tip status` - Check distribution stats\n\n"
            f"**Payout Wallet:** `{self.payout_wallet}`\n\n"
            "_Tips are recorded on-chain and distributed in the next cycle._"
        )
    
    def handle_webhook(self, event: str, payload: Dict) -> Optional[Dict]:
        """
        Handle GitHub webhook event.
        Returns action to take (comment to post) or None.
        """
        if event != "issue_comment":
            return None
        
        action = payload.get("action", "")
        if action != "created":
            return None
        
        issue = payload.get("issue", {})
        issue_number = issue.get("number")
        if not issue_number:
            return None
        
        comment = payload.get("comment", {})
        comment_body = comment.get("body", "")
        commenter = comment.get("user", {}).get("login", "")
        comment_id = comment.get("id", 0)
        
        # Skip bot comments
        if commenter.endswith("[bot]"):
            return None
        
        repo = payload.get("repository", {}).get("full_name", "")
        if not repo:
            return None
        
        # Check for /tip command
        response = self.process_tip(repo, issue_number, commenter, comment_body, comment_id)
        
        if response:
            return {
                "repo": repo,
                "issue_number": issue_number,
                "body": response,
            }
        
        return None


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RustChain GitHub Tip Bot")
    parser.add_argument("--token", help="GitHub token")
    parser.add_argument("--wallet", default="RTC1d48d848a5aa5ecf2c5f01aa5fb64837daaf2f35",
                       help="Payout wallet address")
    parser.add_argument("--state-file", default="bounty_state.json",
                       help="State file path")
    parser.add_argument("--dry-run", action="store_true",
                       help="Run in dry-run mode")
    parser.add_argument("--test-parse", type=str,
                       help="Test parsing a tip command")
    parser.add_argument("--status", action="store_true",
                       help="Show bot status")
    
    args = parser.parse_args()
    
    token = args.token or os.getenv("GITHUB_TOKEN")
    if not token and not args.test_parse:
        print("Error: GITHUB_TOKEN required")
        return 1
    
    bot = TipBot(
        github_token=token or "dummy",
        payout_wallet=args.wallet,
        state_file=args.state_file,
        dry_run=args.dry_run,
    )
    
    if args.test_parse:
        result = bot.parse_tip_command(args.test_parse)
        if result:
            print(f"Parsed: @{result[0]} {result[1]:.2f} RTC")
        else:
            print("No tip command found")
        return 0
    
    if args.status:
        print(bot.get_status("Scottcjn/Rustchain"))
        return 0
    
    print("Tip bot initialized. Use --test-parse or --status for testing.")
    print(f"Payout wallet: {args.wallet}")
    return 0


if __name__ == "__main__":
    exit(main())
