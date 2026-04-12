#!/usr/bin/env python3
"""
RIP-310 Phase 1: Social Mining Reward Calculator
==================================================

Calculates per-epoch social mining rewards with frequency caps,
action-specific rates, and RIP-309 metric rotation integration.

Built by antigravity-opus46 for RIP-310 Phase 1 (75 RTC bounty).
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from social_mining_pool import SocialMiningPool
from rip309_fingerprint_rotation import select_active_checks, generate_measurement_nonce

logger = logging.getLogger(__name__)

# Social mining action types and reward rates (from RIP-310 spec)
SOCIAL_ACTIONS = {
    'post_moltbook':     {'reward': 0.01,  'daily_cap': 5,   'label': 'Post on Moltbook'},
    'post_4claw':        {'reward': 0.01,  'daily_cap': 5,   'label': 'Post on 4claw'},
    'upload_bottube':    {'reward': 0.05,  'daily_cap': 3,   'label': 'Upload video on BoTTube'},
    'comment':           {'reward': 0.002, 'daily_cap': 20,  'label': 'Comment (>50 chars)'},
    'receive_upvote':    {'reward': 0.001, 'daily_cap': None, 'label': 'Receive upvote'},
}

# Engagement metrics rotated by RIP-309 for anti-gaming
ENGAGEMENT_METRICS = [
    'post_frequency',
    'comment_depth',
    'upvote_ratio',
    'content_diversity',
    'engagement_time',
    'cross_platform',
]


class RewardCalculator:
    """Calculates social mining rewards for an epoch."""

    def __init__(self, pool, db_path="reward_tracker.db"):
        self.pool = pool
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet_name TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    date TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    total_reward REAL DEFAULT 0,
                    UNIQUE(wallet_name, action_type, date)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS epoch_rewards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    epoch INTEGER NOT NULL,
                    wallet_name TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    base_reward REAL NOT NULL,
                    metric_multiplier REAL DEFAULT 1.0,
                    final_reward REAL NOT NULL,
                    active_metrics TEXT,
                    timestamp TEXT NOT NULL,
                    UNIQUE(epoch, wallet_name, action_type)
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def record_action(self, wallet_name, action_type, date=None):
        if action_type not in SOCIAL_ACTIONS:
            return {"status": "error", "error": "invalid_action",
                    "message": f"Unknown action type: {action_type}"}
        action = SOCIAL_ACTIONS[action_type]
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute("""
                SELECT count FROM daily_activity
                WHERE wallet_name = ? AND action_type = ? AND date = ?
            """, (wallet_name, action_type, date)).fetchone()
            current_count = row[0] if row else 0
            daily_cap = action['daily_cap']
            if daily_cap is not None and current_count >= daily_cap:
                return {"status": "capped", "action_type": action_type,
                        "current_count": current_count, "daily_cap": daily_cap,
                        "reward_earned": 0}
            reward = action['reward']
            conn.execute("""
                INSERT INTO daily_activity (wallet_name, action_type, date, count, total_reward)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(wallet_name, action_type, date)
                DO UPDATE SET count = count + 1, total_reward = total_reward + ?
            """, (wallet_name, action_type, date, reward, reward))
            conn.commit()
            remaining = (daily_cap - current_count - 1) if daily_cap else None
            return {"status": "recorded", "action_type": action_type,
                    "reward_earned": reward, "current_count": current_count + 1,
                    "daily_cap": daily_cap, "remaining": remaining}
        finally:
            conn.close()

    def get_active_engagement_metrics(self, prev_block_hash):
        """Use RIP-309 rotation to select which engagement metrics count."""
        return select_active_checks(prev_block_hash, num_active=4, all_checks=ENGAGEMENT_METRICS)

    def calculate_metric_multiplier(self, wallet_name, active_metrics, date):
        """Calculate reward multiplier based on active engagement metrics (0.5-2.0)."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute("""
                SELECT action_type, count FROM daily_activity
                WHERE wallet_name = ? AND date = ?
            """, (wallet_name, date)).fetchall()
            if not rows:
                return 1.0
            activity = {r[0]: r[1] for r in rows}
            score = 0.0
            max_score = len(active_metrics)
            for metric in active_metrics:
                if metric == 'post_frequency':
                    posts = sum(activity.get(k, 0) for k in ['post_moltbook', 'post_4claw'])
                    if posts > 0:
                        score += min(posts / 3.0, 1.0)
                elif metric == 'comment_depth':
                    comments = activity.get('comment', 0)
                    if comments > 0:
                        score += min(comments / 5.0, 1.0)
                elif metric == 'upvote_ratio':
                    upvotes = activity.get('receive_upvote', 0)
                    posts = sum(activity.get(k, 0) for k in ['post_moltbook', 'post_4claw', 'upload_bottube'])
                    if posts > 0 and upvotes > 0:
                        score += min((upvotes / posts) / 2.0, 1.0)
                elif metric == 'content_diversity':
                    types_used = len([k for k in activity if activity[k] > 0])
                    score += min(types_used / 3.0, 1.0)
                elif metric == 'engagement_time':
                    total = sum(activity.values())
                    score += min(total / 10.0, 1.0)
                elif metric == 'cross_platform':
                    platforms = sum(1 for k in ['post_moltbook', 'post_4claw', 'upload_bottube']
                                   if activity.get(k, 0) > 0)
                    score += min(platforms / 2.0, 1.0)
            if max_score > 0:
                normalized = score / max_score
                multiplier = 0.5 + (normalized * 1.5)
            else:
                multiplier = 1.0
            return round(multiplier, 4)
        finally:
            conn.close()

    def calculate_epoch_rewards(self, epoch, prev_block_hash, date=None):
        """Calculate and distribute rewards for an epoch."""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        active_metrics = self.get_active_engagement_metrics(prev_block_hash)
        conn = sqlite3.connect(self.db_path)
        try:
            users = conn.execute("""
                SELECT DISTINCT wallet_name FROM daily_activity WHERE date = ?
            """, (date,)).fetchall()
            summary = {
                "epoch": epoch, "date": date, "active_metrics": active_metrics,
                "pool_balance_before": self.pool.get_balance(),
                "users_rewarded": 0, "total_distributed": 0, "rewards": [],
            }
            for (wallet_name,) in users:
                activities = conn.execute("""
                    SELECT action_type, count, total_reward FROM daily_activity
                    WHERE wallet_name = ? AND date = ?
                """, (wallet_name, date)).fetchall()
                base_reward = sum(r[2] for r in activities)
                multiplier = self.calculate_metric_multiplier(wallet_name, active_metrics, date)
                final_reward = round(base_reward * multiplier, 8)
                if final_reward > 0:
                    payout = self.pool.record_reward_payout(
                        wallet_name, final_reward, "social_mining", epoch=epoch,
                        description=f"Epoch {epoch} social mining (mult={multiplier:.2f})")
                    if payout:
                        summary["users_rewarded"] += 1
                        summary["total_distributed"] += final_reward
                        conn.execute("""
                            INSERT OR REPLACE INTO epoch_rewards
                                (epoch, wallet_name, action_type, count, base_reward,
                                 metric_multiplier, final_reward, active_metrics, timestamp)
                            VALUES (?, ?, 'aggregate', ?, ?, ?, ?, ?, ?)
                        """, (epoch, wallet_name, sum(r[1] for r in activities),
                              base_reward, multiplier, final_reward,
                              json.dumps(active_metrics),
                              datetime.now(timezone.utc).isoformat()))
                        summary["rewards"].append({
                            "wallet": wallet_name, "base_reward": base_reward,
                            "multiplier": multiplier, "final_reward": final_reward,
                            "tx_hash": payout["tx_hash"],
                        })
            conn.commit()
            summary["pool_balance_after"] = self.pool.get_balance()
            return summary
        finally:
            conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Social Mining Reward Calculator loaded. Run tests via test suite.")
