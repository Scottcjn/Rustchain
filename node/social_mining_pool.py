#!/usr/bin/env python3
"""
RIP-310 Phase 1: Social Mining Pool -- Treasury Management
==========================================================

Manages the social_mining_pool treasury wallet that collects tip fees
and distributes social mining rewards. All transactions are recorded in
a SQLite-backed ledger with full audit trail.

Built by antigravity-opus46 for RIP-310 Phase 1 (75 RTC bounty).

Key Principles:
1. Every transaction is logged with epoch correlation
2. Fee rate is configurable (default 8%)
3. Pool never goes negative (outflows capped at balance)
4. Audit trail is immutable (append-only ledger)
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_FEE_RATE = 0.08
POOL_WALLET_NAME = "social_mining_pool"


class SocialMiningPool:
    """Treasury wallet for the social mining economy."""

    def __init__(self, db_path="social_mining_pool.db", fee_rate=DEFAULT_FEE_RATE):
        self.db_path = db_path
        self.fee_rate = fee_rate
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    epoch INTEGER,
                    tx_type TEXT NOT NULL,
                    from_wallet TEXT,
                    to_wallet TEXT,
                    gross_amount REAL NOT NULL,
                    fee_amount REAL DEFAULT 0,
                    net_amount REAL NOT NULL,
                    description TEXT,
                    tx_hash TEXT UNIQUE,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pool_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    balance REAL NOT NULL DEFAULT 0,
                    total_fees_collected REAL NOT NULL DEFAULT 0,
                    total_rewards_distributed REAL NOT NULL DEFAULT 0,
                    total_deposits REAL NOT NULL DEFAULT 0,
                    last_updated TEXT NOT NULL
                )
            """)
            conn.execute("""
                INSERT OR IGNORE INTO pool_state (id, balance, total_fees_collected,
                    total_rewards_distributed, total_deposits, last_updated)
                VALUES (1, 0, 0, 0, 0, ?)
            """, (datetime.now(timezone.utc).isoformat(),))
            conn.commit()
        finally:
            conn.close()

    def _generate_tx_hash(self, tx_type, from_wallet, to_wallet, amount, timestamp):
        payload = f"{tx_type}:{from_wallet}:{to_wallet}:{amount}:{timestamp}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def get_balance(self):
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("SELECT balance FROM pool_state WHERE id = 1").fetchone()
            return row[0] if row else 0.0
        finally:
            conn.close()

    def get_stats(self):
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("""
                SELECT balance, total_fees_collected, total_rewards_distributed,
                       total_deposits, last_updated
                FROM pool_state WHERE id = 1
            """).fetchone()
            if not row:
                return {"balance": 0}
            return {
                "balance": row[0],
                "total_fees_collected": row[1],
                "total_rewards_distributed": row[2],
                "total_deposits": row[3],
                "last_updated": row[4],
                "fee_rate": self.fee_rate,
            }
        finally:
            conn.close()

    def calculate_fee(self, gross_amount):
        fee = round(gross_amount * self.fee_rate, 8)
        net = round(gross_amount - fee, 8)
        return fee, net

    def record_tip_fee(self, from_wallet, to_wallet, gross_amount, epoch=0, description=""):
        if gross_amount <= 0:
            raise ValueError(f"Tip amount must be positive, got {gross_amount}")
        fee_amount, net_amount = self.calculate_fee(gross_amount)
        timestamp = datetime.now(timezone.utc).isoformat()
        tx_hash = self._generate_tx_hash("tip_fee", from_wallet, to_wallet, gross_amount, timestamp)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO ledger (timestamp, epoch, tx_type, from_wallet, to_wallet,
                    gross_amount, fee_amount, net_amount, description, tx_hash)
                VALUES (?, ?, 'tip', ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, epoch, from_wallet, to_wallet, gross_amount,
                  fee_amount, net_amount, description or f"Tip: {from_wallet} -> {to_wallet}",
                  tx_hash))
            conn.execute("""
                UPDATE pool_state SET balance = balance + ?,
                    total_fees_collected = total_fees_collected + ?, last_updated = ?
                WHERE id = 1
            """, (fee_amount, fee_amount, timestamp))
            conn.commit()
            return {
                "tx_hash": tx_hash, "tx_type": "tip",
                "from_wallet": from_wallet, "to_wallet": to_wallet,
                "gross_amount": gross_amount, "fee_amount": fee_amount,
                "net_to_recipient": net_amount, "fee_to_pool": fee_amount,
                "epoch": epoch, "timestamp": timestamp,
            }
        finally:
            conn.close()

    def record_reward_payout(self, to_wallet, amount, reward_type, epoch=0, description=""):
        if amount <= 0:
            raise ValueError(f"Reward amount must be positive, got {amount}")
        current_balance = self.get_balance()
        if current_balance < amount:
            return None
        timestamp = datetime.now(timezone.utc).isoformat()
        tx_hash = self._generate_tx_hash("reward", POOL_WALLET_NAME, to_wallet, amount, timestamp)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO ledger (timestamp, epoch, tx_type, from_wallet, to_wallet,
                    gross_amount, fee_amount, net_amount, description, tx_hash)
                VALUES (?, ?, 'reward', ?, ?, ?, 0, ?, ?, ?)
            """, (timestamp, epoch, POOL_WALLET_NAME, to_wallet, amount,
                  amount, description or f"Social mining reward: {reward_type}", tx_hash))
            conn.execute("""
                UPDATE pool_state SET balance = balance - ?,
                    total_rewards_distributed = total_rewards_distributed + ?, last_updated = ?
                WHERE id = 1
            """, (amount, amount, timestamp))
            conn.commit()
            return {
                "tx_hash": tx_hash, "tx_type": "reward", "reward_type": reward_type,
                "to_wallet": to_wallet, "amount": amount, "epoch": epoch,
                "timestamp": timestamp, "pool_balance_after": current_balance - amount,
            }
        finally:
            conn.close()

    def record_deposit(self, from_wallet, amount, deposit_type, epoch=0, description=""):
        if amount <= 0:
            raise ValueError(f"Deposit amount must be positive, got {amount}")
        timestamp = datetime.now(timezone.utc).isoformat()
        tx_hash = self._generate_tx_hash("deposit", from_wallet, POOL_WALLET_NAME, amount, timestamp)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO ledger (timestamp, epoch, tx_type, from_wallet, to_wallet,
                    gross_amount, fee_amount, net_amount, description, tx_hash)
                VALUES (?, ?, 'deposit', ?, ?, ?, 0, ?, ?, ?)
            """, (timestamp, epoch, from_wallet, POOL_WALLET_NAME, amount,
                  amount, description or f"Deposit: {deposit_type}", tx_hash))
            conn.execute("""
                UPDATE pool_state SET balance = balance + ?,
                    total_deposits = total_deposits + ?, last_updated = ?
                WHERE id = 1
            """, (amount, amount, timestamp))
            conn.commit()
            return {
                "tx_hash": tx_hash, "tx_type": "deposit", "deposit_type": deposit_type,
                "from_wallet": from_wallet, "amount": amount, "epoch": epoch,
                "timestamp": timestamp,
            }
        finally:
            conn.close()

    def get_ledger(self, limit=50, tx_type=None):
        conn = sqlite3.connect(self.db_path)
        try:
            if tx_type:
                rows = conn.execute("""
                    SELECT timestamp, epoch, tx_type, from_wallet, to_wallet,
                           gross_amount, fee_amount, net_amount, description, tx_hash
                    FROM ledger WHERE tx_type = ? ORDER BY id DESC LIMIT ?
                """, (tx_type, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT timestamp, epoch, tx_type, from_wallet, to_wallet,
                           gross_amount, fee_amount, net_amount, description, tx_hash
                    FROM ledger ORDER BY id DESC LIMIT ?
                """, (limit,)).fetchall()
            return [{
                "timestamp": r[0], "epoch": r[1], "tx_type": r[2],
                "from_wallet": r[3], "to_wallet": r[4],
                "gross_amount": r[5], "fee_amount": r[6], "net_amount": r[7],
                "description": r[8], "tx_hash": r[9],
            } for r in rows]
        finally:
            conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Social Mining Pool module loaded. Run tests via test suite.")
