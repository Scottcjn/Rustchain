#!/usr/bin/env python3
"""
RIP-310 Phase 1: Social Mining Tip Handler
============================================

Handles /tip @username <amount> RTC commands with Beacon ID verification,
fee collection, and transaction logging.

Built by antigravity-opus46 for RIP-310 Phase 1 (75 RTC bounty).
"""

import hashlib
import json
import logging
import re
import sqlite3
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from social_mining_pool import SocialMiningPool

logger = logging.getLogger(__name__)

MIN_TIP_AMOUNT = 0.01
MAX_TIP_AMOUNT = 1000.0
RATE_LIMIT_SECONDS = 10


class BeaconVerifier:
    """Verifies Beacon IDs for tip participants."""

    def __init__(self, db_path="beacon_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS beacon_ids (
                    wallet_name TEXT PRIMARY KEY,
                    beacon_id TEXT NOT NULL,
                    hardware_attested INTEGER DEFAULT 0,
                    fingerprint_hash TEXT,
                    registered_at TEXT,
                    last_verified TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def register_beacon(self, wallet_name, beacon_id, hardware_attested=False, fingerprint_hash=""):
        conn = sqlite3.connect(self.db_path)
        try:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO beacon_ids
                    (wallet_name, beacon_id, hardware_attested, fingerprint_hash, registered_at, last_verified)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (wallet_name, beacon_id, int(hardware_attested), fingerprint_hash, now, now))
            conn.commit()
            return True
        finally:
            conn.close()

    def verify_beacon(self, wallet_name):
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("""
                SELECT beacon_id, hardware_attested FROM beacon_ids WHERE wallet_name = ?
            """, (wallet_name,)).fetchone()
            if not row:
                return False, f"No Beacon ID registered for wallet '{wallet_name}'"
            return True, row[0]
        finally:
            conn.close()


class TipHandler:
    """
    Handles tip commands between RustChain users.

    Flow: Parse -> Verify Beacon IDs -> Rate limit -> Calculate fee -> Record -> Confirm
    """

    TIP_PATTERN = re.compile(r'^/tip\s+@?(\w+)\s+([\d.]+)\s*(?:RTC|rtc)?$', re.IGNORECASE)

    def __init__(self, pool, verifier, db_path="tip_history.db"):
        self.pool = pool
        self.verifier = verifier
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tip_rate_limits (
                    wallet_name TEXT PRIMARY KEY,
                    last_tip_time REAL NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def parse_tip_command(self, command):
        command = command.strip()
        match = self.TIP_PATTERN.match(command)
        if not match:
            return False, None, f"Invalid tip format. Use: /tip @username <amount> RTC"
        recipient = match.group(1)
        try:
            amount = float(match.group(2))
        except ValueError:
            return False, None, f"Invalid amount: '{match.group(2)}'"
        return True, {"recipient": recipient, "amount": amount}, None

    def check_rate_limit(self, wallet_name):
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("""
                SELECT last_tip_time FROM tip_rate_limits WHERE wallet_name = ?
            """, (wallet_name,)).fetchone()
            if row:
                elapsed = time.time() - row[0]
                if elapsed < RATE_LIMIT_SECONDS:
                    return False, f"Rate limited. Try again in {RATE_LIMIT_SECONDS - elapsed:.0f}s"
            return True, None
        finally:
            conn.close()

    def _update_rate_limit(self, wallet_name):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO tip_rate_limits (wallet_name, last_tip_time) VALUES (?, ?)
            """, (wallet_name, time.time()))
            conn.commit()
        finally:
            conn.close()

    def execute_tip(self, from_wallet, command, epoch=0, platform="moltbook"):
        parsed, data, error = self.parse_tip_command(command)
        if not parsed:
            return {"status": "error", "error": "parse_failed", "message": error}

        recipient = data["recipient"]
        amount = data["amount"]

        if amount < MIN_TIP_AMOUNT:
            return {"status": "error", "error": "below_minimum",
                    "message": f"Minimum tip is {MIN_TIP_AMOUNT} RTC"}
        if amount > MAX_TIP_AMOUNT:
            return {"status": "error", "error": "above_maximum",
                    "message": f"Maximum tip is {MAX_TIP_AMOUNT} RTC"}
        if from_wallet == recipient:
            return {"status": "error", "error": "self_tip", "message": "Cannot tip yourself"}

        tipper_ok, tipper_result = self.verifier.verify_beacon(from_wallet)
        if not tipper_ok:
            return {"status": "error", "error": "tipper_no_beacon", "message": tipper_result}

        recipient_ok, recipient_result = self.verifier.verify_beacon(recipient)
        if not recipient_ok:
            return {"status": "error", "error": "recipient_no_beacon", "message": recipient_result}

        rate_ok, rate_msg = self.check_rate_limit(from_wallet)
        if not rate_ok:
            return {"status": "error", "error": "rate_limited", "message": rate_msg}

        description = f"Tip on {platform}: {from_wallet} -> {recipient}"
        tx = self.pool.record_tip_fee(from_wallet, recipient, amount, epoch, description)
        self._update_rate_limit(from_wallet)

        return {
            "status": "success",
            "message": f"Tipped {recipient} {tx['net_to_recipient']:.4f} RTC "
                       f"(fee: {tx['fee_amount']:.4f} RTC to pool)",
            "transaction": tx, "platform": platform,
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Social Mining Tip Handler loaded. Run tests via test suite.")
