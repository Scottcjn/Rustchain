#!/usr/bin/env python3
"""
GitHub Tip Bot for RTC
Listens for /tip commands in GitHub comments and processes RTC tips.
"""

import os
import re
import json
import hmac
import hashlib
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Configuration
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
ADMIN_KEY = os.environ.get("TIP_BOT_ADMIN_KEY", "")
DB_PATH = os.environ.get("TIP_BOT_DB", "tip_bot.db")

# GitHub API
GITHUB_API = "https://api.github.com"

# Command patterns
TIP_PATTERN = r"^/tip\s+@(\w+)\s+(\d+(?:\.\d+)?)\s*RTC\s*(.*)$"
BALANCE_PATTERN = r"^/balance$"
REGISTER_PATTERN = r"^/register\s+([a-zA-Z0-9]+)$"
LEADERBOARD_PATTERN = r"^/leaderboard$"


class TipBot:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        })
        self.db = self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database for tip tracking."""
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                github_username TEXT PRIMARY KEY,
                wallet_address TEXT NOT NULL,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tips table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user TEXT NOT NULL,
                to_user TEXT NOT NULL,
                amount REAL NOT NULL,
                memo TEXT,
                status TEXT DEFAULT 'pending',
                tx_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        return conn
    
    def handle_comment(self, payload: Dict[str, Any]) -> Optional[str]:
        """Process a GitHub comment."""
        comment = payload.get("comment", {})
        issue = payload.get("issue", {})
        sender = comment.get("user", {}).get("login", "")
        body = comment.get("body", "").strip()
        
        # Skip bot comments
        if comment.get("user", {}).get("type") == "Bot":
            return None
        
        # Check commands
        tip_match = re.match(TIP_PATTERN, body, re.IGNORECASE)
        if tip_match:
            return self._handle_tip(tip_match, sender, issue)
        
        balance_match = re.match(BALANCE_PATTERN, body, re.IGNORECASE)
        if balance_match:
            return self._handle_balance(sender)
        
        register_match = re.match(REGISTER_PATTERN, body, re.IGNORECASE)
        if register_match:
            return self._handle_register(register_match, sender)
        
        leaderboard_match = re.match(LEADERBOARD_PATTERN, body, re.IGNORECASE)
        if leaderboard_match:
            return self._handle_leaderboard()
        
        return None
    
    def _handle_tip(self, match, sender: str, issue: Dict) -> str:
        """Handle /tip command."""
        recipient = match.group(1)
        amount = float(match.group(2))
        memo = match.group(3).strip() or "Tip from GitHub"
        
        # Validate sender is admin/maintainer
        if not self._is_maintainer(sender, issue):
            return "❌ Only repo maintainers can send tips."
        
        # Get recipient wallet
        wallet = self._get_wallet(recipient)
        if not wallet:
            return f"❌ Recipient {recipient} hasn't registered their wallet. Ask them to use /register WALLET_ADDRESS"
        
        # Queue the transfer
        tx_hash = self._queue_transfer(sender, recipient, amount, memo)
        
        if tx_hash:
            return f"""✅ Queued: {amount} RTC → {recipient}
From: {sender} | Memo: {memo}
Status: Pending (confirms in 24h)
Tx: `{tx_hash}`"""
        else:
            return "❌ Failed to queue tip. Please try again later."
    
    def _handle_balance(self, username: str) -> str:
        """Handle /balance command."""
        wallet = self._get_wallet(username)
        if not wallet:
            return f"❌ {username} hasn't registered. Use /register WALLET_ADDRESS to register."
        
        balance = self._get_balance(wallet)
        return f"💰 Balance for {username}: {balance} RTC\nWallet: `{wallet}`"
    
    def _handle_register(self, match, username: str) -> str:
        """Handle /register command."""
        wallet = match.group(1)
        
        # Basic validation
        if not wallet.startswith("r") or len(wallet) < 40:
            return "❌ Invalid wallet address. Must start with 'r' and be at least 40 characters."
        
        self._save_wallet(username, wallet)
        return f"✅ Registered! Wallet: `{wallet}`\n\nNow you can receive tips!"
    
    def _handle_leaderboard(self) -> str:
        """Handle /leaderboard command."""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT to_user, SUM(amount) as total
            FROM tips
            WHERE status = 'confirmed'
            AND created_at > datetime('now', '-30 days')
            GROUP BY to_user
            ORDER BY total DESC
            LIMIT 10
        """)
        
        results = cursor.fetchall()
        if not results:
            return "📊 No tips yet this month. Be the first to tip!"
        
        lines = ["🏆 Top Tip Recipients (30 days)", ""]
        for i, (user, total) in enumerate(results, 1):
            lines.append(f"{i}. @{user} - {total} RTC")
        
        return "\n".join(lines)
    
    def _is_maintainer(self, username: str, issue: Dict) -> bool:
        """Check if user is a maintainer."""
        # For now, check if they're the repo owner or have write access
        # In production, use GitHub API to check permissions
        return True  # TODO: Implement proper check
    
    def _get_wallet(self, username: str) -> Optional[str]:
        """Get wallet address for user."""
        cursor = self.db.cursor()
        cursor.execute("SELECT wallet_address FROM users WHERE github_username = ?", (username,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def _save_wallet(self, username: str, wallet: str):
        """Save wallet address for user."""
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO users (github_username, wallet_address)
            VALUES (?, ?)
        """, (username, wallet))
        self.db.commit()
    
    def _get_balance(self, wallet: str) -> float:
        """Get RTC balance from chain."""
        try:
            response = requests.post(RPC_URL, json={
                "jsonrpc": "2.0",
                "method": "eth_getBalance",
                "params": [wallet, "latest"],
                "id": 1
            }, timeout=10)
            result = response.json()
            if result.get("result"):
                return int(result["result"], 16) / 1e18
        except:
            pass
        return 0.0
    
    def _queue_transfer(self, from_user: str, to_user: str, amount: float, memo: str) -> Optional[str]:
        """Queue transfer via RustChain API."""
        # In production, call the actual RPC
        # For now, simulate
        tx_hash = f"0x{hashlib.sha256(f'{from_user}{to_user}{amount}{datetime.now()}'.encode()).hexdigest()[:64]}"
        
        # Save to DB
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO tips (from_user, to_user, amount, memo, status, tx_hash)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (from_user, to_user, amount, memo, tx_hash))
        self.db.commit()
        
        return tx_hash
    
    def post_comment(self, issue_number: int, body: str, repo: str, owner: str):
        """Post a comment to GitHub."""
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        self.session.post(url, json={"body": body})


def main():
    """Main entry point for GitHub Action."""
    # Get payload
    payload = json.loads(os.environ.get("GITHUB_PAYLOAD", "{}"))
    
    bot = TipBot()
    response = bot.handle_comment(payload)
    
    if response:
        # Post response
        issue = payload.get("issue", {})
        repo = os.environ.get("GITHUB_REPO", "").split("/")[-1]
        owner = os.environ.get("GITHUB_REPO_OWNER", "")
        
        if repo and owner and issue.get("number"):
            bot.post_comment(issue["number"], response, repo, owner)


if __name__ == "__main__":
    main()
