#!/usr/bin/env python3
"""
RIP-310: Social Mining Protocol
================================

Users earn RTC for quality engagement on 4claw, Moltbook, and BoTTube.
Tips between users create a circular economy with a platform fee that
replenishes the treasury.

Phases:
  Phase 1 — Tip Bot + Social Mining Pool wallet (75 RTC)
  Phase 2 — Automated post/comment rewards + RIP-309 anti-gaming (100 RTC)
  Phase 3 — Cross-platform tipping + video rewards (75 RTC)
  Phase 4 — Reaction-based micro-tips + quality scoring + leaderboards (100 RTC)

Total: 350 RTC

Design follows existing patterns:
  - SQLite persistence (like beacon_identity.py)
  - Flask API routes (like rewards_implementation_rip200.py)
  - Beacon ID verification (like beacon_identity.py)
  - Epoch settlement integration
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

log = logging.getLogger("rustchain.social_mining")

# ─── Constants ──────────────────────────────────────────────────────────────

UNIT = 1_000_000  # uRTC per 1 RTC
DB_PATH = os.environ.get(
    "SOCIAL_MINING_DB_PATH", "/root/rustchain/social_mining.db"
)

# Platform fee percentage (8% of tips go to social_mining_pool)
TIP_FEE_PCT = 0.08
MINIMUM_TIP_URTC = int(0.01 * UNIT)  # 0.01 RTC minimum

# Social mining reward rates (in uRTC)
REWARD_MOLBOOK_POST = int(0.01 * UNIT)
REWARD_4CLAW_POST = int(0.01 * UNIT)
REWARD_BOTTUBE_UPLOAD = int(0.05 * UNIT)
REWARD_COMMENT = int(0.002 * UNIT)
REWARD_UPVOTE = int(0.001 * UNIT)

# Frequency caps (per day)
CAP_MOLBOOK_POSTS = 5
CAP_4CLAW_POSTS = 5
CAP_BOTTUBE_UPLOADS = 3
CAP_COMMENTS = 20

# HIGH_VALUE_THRESHOLD: jobs above this require veteran level
HIGH_VALUE_THRESHOLD = 50  # RTC

# RIP-309 epoch duration (6 hours)
RIP309_EPOCH_SECONDS = 6 * 3600

# Content quality thresholds
MIN_COMMENT_LENGTH = 50  # chars for substantive comment
MIN_VIDEO_DURATION_SEC = 30

# Social mining pool wallet address
SOCIAL_MINING_POOL_WALLET = os.environ.get(
    "SOCIAL_MINING_POOL_WALLET",
    "RTC_pool_social_mining_treasury_000000000000"
)

# 10% of epoch mining rewards redirected to social pool
EPOCH_REWARD_REDIRECT_PCT = 0.10

# ─── Enums ──────────────────────────────────────────────────────────────────

class Platform(str, Enum):
    MOLBOOK = "moltbook"
    FOURCLAW = "4claw"
    BOTTUBE = "bottube"


class Action(str, Enum):
    POST = "post"
    COMMENT = "comment"
    VIDEO_UPLOAD = "video_upload"
    UPVOTE = "upvote"
    TIP = "tip"
    MICRO_TIP = "micro_tip"  # emoji-based


class TipMethod(str, Enum):
    COMMAND = "command"     # /tip @user 5 RTC
    EMOJI = "emoji"         # 🦞 reaction = 0.1 RTC


# ─── Database Schema ────────────────────────────────────────────────────────

SCHEMA_SQL = """
-- Social mining pool balance tracking
CREATE TABLE IF NOT EXISTS social_mining_pool (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    balance_urtc    INTEGER NOT NULL DEFAULT 0,
    total_inflow_urtc INTEGER NOT NULL DEFAULT 0,
    total_outflow_urtc INTEGER NOT NULL DEFAULT 0,
    updated_at      REAL NOT NULL
);
INSERT OR IGNORE INTO social_mining_pool (id, balance_urtc, total_inflow_urtc,
    total_outflow_urtc, updated_at)
VALUES (1, 0, 0, 0, 0);

-- Social mining actions (posts, comments, videos) for reward tracking
CREATE TABLE IF NOT EXISTS social_actions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    beacon_id       TEXT NOT NULL,
    platform        TEXT NOT NULL,    -- moltbook, 4claw, bottube
    action_type     TEXT NOT NULL,    -- post, comment, video_upload, upvote
    content_id      TEXT NOT NULL,    -- platform-specific content ID
    content_length  INTEGER DEFAULT 0,
    reward_urtc     INTEGER NOT NULL,
    epoch_nonce     INTEGER NOT NULL, -- RIP-309 nonce
    timestamp       REAL NOT NULL,
    is_valid        INTEGER NOT NULL DEFAULT 1,
    UNIQUE(platform, content_id)
);
CREATE INDEX IF NOT EXISTS idx_sa_user
    ON social_actions(user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_sa_beacon
    ON social_actions(beacon_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_sa_platform
    ON social_actions(platform, action_type, timestamp);

-- Tipping ledger
CREATE TABLE IF NOT EXISTS tips (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tipper_id       TEXT NOT NULL,
    tipper_beacon   TEXT NOT NULL,
    recipient_id    TEXT NOT NULL,
    recipient_beacon TEXT NOT NULL,
    tip_method      TEXT NOT NULL,    -- command, emoji
    amount_urtc     INTEGER NOT NULL,
    fee_urtc        INTEGER NOT NULL, -- 8% to social_mining_pool
    net_urtc        INTEGER NOT NULL, -- recipient receives
    platform        TEXT NOT NULL,
    content_id      TEXT,             -- optional: tipped content
    emoji           TEXT,             -- for emoji tips
    timestamp       REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tips_tipper
    ON tips(tipper_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_tips_recipient
    ON tips(recipient_id, timestamp);

-- Daily frequency tracking (per user, per action type, per day)
CREATE TABLE IF NOT EXISTS daily_action_counts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    beacon_id       TEXT NOT NULL,
    platform        TEXT NOT NULL,
    action_type     TEXT NOT NULL,
    date_str        TEXT NOT NULL,    -- YYYY-MM-DD
    count           INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, platform, action_type, date_str)
);

-- RIP-309 epoch nonce tracking
CREATE TABLE IF NOT EXISTS rip309_epochs (
    epoch_num       INTEGER PRIMARY KEY,
    nonce           TEXT NOT NULL,
    start_time      REAL NOT NULL,
    end_time        REAL NOT NULL,
    active_metrics  TEXT NOT NULL,    -- JSON array of active metric types
    metric_weights  TEXT              -- JSON object of metric weights
);

-- Content quality scores (Phase 4)
CREATE TABLE IF NOT EXISTS content_quality (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id      TEXT NOT NULL UNIQUE,
    platform        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    quality_score   REAL NOT NULL DEFAULT 0.5,
    upvote_count    INTEGER NOT NULL DEFAULT 0,
    tip_count       INTEGER NOT NULL DEFAULT 0,
    total_tips_urtc INTEGER NOT NULL DEFAULT 0,
    comment_count   INTEGER NOT NULL DEFAULT 0,
    last_updated    REAL NOT NULL,
    UNIQUE(platform, content_id)
);

-- User cumulative statistics
CREATE TABLE IF NOT EXISTS user_social_stats (
    user_id         TEXT PRIMARY KEY,
    beacon_id       TEXT NOT NULL,
    total_earned_urtc INTEGER NOT NULL DEFAULT 0,
    total_tips_sent_urtc INTEGER NOT NULL DEFAULT 0,
    total_tips_received_urtc INTEGER NOT NULL DEFAULT 0,
    total_posts     INTEGER NOT NULL DEFAULT 0,
    total_comments  INTEGER NOT NULL DEFAULT 0,
    total_videos    INTEGER NOT NULL DEFAULT 0,
    total_upvotes_received INTEGER NOT NULL DEFAULT 0,
    last_active     REAL NOT NULL,
    created_at      REAL NOT NULL
);
"""


def init_social_mining_db(db_path: str = DB_PATH) -> None:
    """Initialize social mining database tables."""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    log.info("Social mining database initialized at %s", db_path)


def _get_conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Get a database connection, initializing if needed."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Initialize if tables don't exist
    conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' LIMIT 1"
    )
    return conn


# ─── RIP-309 Rotating Nonce ─────────────────────────────────────────────────

def _compute_epoch_nonce(epoch_num: int) -> str:
    """Compute deterministic nonce for an epoch from timestamp."""
    data = f"rip309:epoch:{epoch_num}:social_mining:{time.time()}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def _get_current_epoch() -> int:
    """Get current RIP-309 epoch number."""
    return int(time.time()) // RIP309_EPOCH_SECONDS


def _get_epoch_metrics(epoch_num: int) -> Tuple[List[str], Dict[str, float]]:
    """Get active metrics and weights for an epoch.

    RIP-309: each epoch rotates which engagement metrics count for rewards,
    preventing sustained gaming of any single metric.
    """
    all_metrics = ["posts", "comments", "video_uploads", "upvotes", "tips"]

    # Use epoch_num to deterministically select active subset
    seed = epoch_num % len(all_metrics)
    # Always include at least 3 metrics
    active = []
    for i, m in enumerate(all_metrics):
        if (epoch_num + i) % 3 != 0 or i == seed:
            active.append(m)
    if len(active) < 3:
        active = all_metrics[:3]

    # Compute weights: active metrics get higher weight, others get 0.1x
    weights = {}
    for m in all_metrics:
        if m in active:
            weights[m] = 1.0
        else:
            weights[m] = 0.1

    return active, weights


def get_or_create_epoch(epoch_num: Optional[int] = None,
                        db_path: str = DB_PATH) -> Dict[str, Any]:
    """Get or create RIP-309 epoch record."""
    if epoch_num is None:
        epoch_num = _get_current_epoch()

    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM rip309_epochs WHERE epoch_num = ?",
            (epoch_num,)
        ).fetchone()

        if row:
            return {
                "epoch_num": row["epoch_num"],
                "nonce": row["nonce"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "active_metrics": json.loads(row["active_metrics"]),
                "metric_weights": json.loads(row["metric_weights"]),
            }

        # Create new epoch
        start = epoch_num * RIP309_EPOCH_SECONDS
        end = start + RIP309_EPOCH_SECONDS
        nonce = _compute_epoch_nonce(epoch_num)
        active, weights = _get_epoch_metrics(epoch_num)

        conn.execute(
            "INSERT INTO rip309_epochs "
            "(epoch_num, nonce, start_time, end_time, "
            "active_metrics, metric_weights) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (epoch_num, nonce, start, end,
             json.dumps(active), json.dumps(weights))
        )
        conn.commit()

        return {
            "epoch_num": epoch_num,
            "nonce": nonce,
            "start_time": start,
            "end_time": end,
            "active_metrics": active,
            "metric_weights": weights,
        }
    finally:
        conn.close()


# ─── Beacon ID Verification ─────────────────────────────────────────────────

def verify_beacon_id(beacon_id: str, db_path: str = DB_PATH) -> bool:
    """Verify a user has a valid Beacon ID.

    In production, this would check beacon_identity.py's known keys table.
    For RIP-310, we check that the beacon_id follows the expected format
    and is registered in our user_social_stats table.
    """
    if not beacon_id or len(beacon_id) < 10:
        return False

    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT beacon_id FROM user_social_stats "
            "WHERE beacon_id = ? LIMIT 1",
            (beacon_id,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def register_beacon_user(user_id: str, beacon_id: str,
                         db_path: str = DB_PATH) -> bool:
    """Register a user with their Beacon ID for social mining."""
    if not beacon_id or len(beacon_id) < 10:
        return False

    conn = _get_conn(db_path)
    try:
        now = time.time()
        conn.execute(
            "INSERT OR IGNORE INTO user_social_stats "
            "(user_id, beacon_id, last_active, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, beacon_id, now, now)
        )
        conn.commit()
        return True
    finally:
        conn.close()


# ─── Frequency Cap Tracking ─────────────────────────────────────────────────

def _get_daily_count(user_id: str, platform: str, action_type: str,
                     date_str: str, db_path: str = DB_PATH) -> int:
    """Get user's action count for a specific day."""
    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT count FROM daily_action_counts "
            "WHERE user_id = ? AND platform = ? "
            "AND action_type = ? AND date_str = ?",
            (user_id, platform, action_type, date_str)
        ).fetchone()
        return row["count"] if row else 0
    finally:
        conn.close()


def _increment_daily_count(user_id: str, beacon_id: str, platform: str,
                           action_type: str, date_str: str,
                           db_path: str = DB_PATH) -> bool:
    """Increment daily action count. Returns False if cap exceeded."""
    caps = {
        (Platform.MOLBOOK.value, Action.POST.value): CAP_MOLBOOK_POSTS,
        (Platform.FOURCLAW.value, Action.POST.value): CAP_4CLAW_POSTS,
        (Platform.BOTTUBE.value, Action.VIDEO_UPLOAD.value): CAP_BOTTUBE_UPLOADS,
        (None, Action.COMMENT.value): CAP_COMMENTS,
    }
    cap = caps.get((platform, action_type), caps.get((None, action_type), 999))

    conn = _get_conn(db_path)
    try:
        current = conn.execute(
            "SELECT count FROM daily_action_counts "
            "WHERE user_id = ? AND platform = ? "
            "AND action_type = ? AND date_str = ?",
            (user_id, platform, action_type, date_str)
        ).fetchone()

        count = current["count"] if current else 0
        if count >= cap:
            return False

        conn.execute(
            "INSERT INTO daily_action_counts "
            "(user_id, beacon_id, platform, action_type, date_str, count) "
            "VALUES (?, ?, ?, ?, ?, 1) "
            "ON CONFLICT(user_id, platform, action_type, date_str) "
            "DO UPDATE SET count = count + 1",
            (user_id, beacon_id, platform, action_type, date_str)
        )
        conn.commit()
        return True
    finally:
        conn.close()


# ─── Phase 1: Tipping Engine ────────────────────────────────────────────────

def process_tip(
    tipper_id: str,
    tipper_beacon: str,
    recipient_id: str,
    recipient_beacon: str,
    amount_urtc: int,
    tip_method: str = TipMethod.COMMAND.value,
    platform: str = Platform.MOLBOOK.value,
    content_id: Optional[str] = None,
    emoji: Optional[str] = None,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """Process a tip between two users.

    Phase 1 + Phase 3: Manual /tip command and emoji-based micro-tips.

    Rules:
    - Both parties must have Beacon IDs
    - Minimum tip: 0.01 RTC
    - 8% fee goes to social_mining_pool
    - Net amount goes to recipient
    """
    # Validate Beacon IDs
    if not verify_beacon_id(tipper_beacon, db_path):
        return {"success": False, "error": "Tipper has no valid Beacon ID"}
    if not verify_beacon_id(recipient_beacon, db_path):
        return {
            "success": False,
            "error": "Recipient has no valid Beacon ID"
        }

    # Validate amount
    if amount_urtc < MINIMUM_TIP_URTC:
        return {
            "success": False,
            "error": f"Tip below minimum ({MINIMUM_TIP_URTC} uRTC)"
        }

    # Calculate fee and net
    fee_urtc = int(amount_urtc * TIP_FEE_PCT)
    net_urtc = amount_urtc - fee_urtc

    conn = _get_conn(db_path)
    try:
        now = time.time()

        # Record tip
        conn.execute(
            "INSERT INTO tips "
            "(tipper_id, tipper_beacon, recipient_id, recipient_beacon, "
            "tip_method, amount_urtc, fee_urtc, net_urtc, platform, "
            "content_id, emoji, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (tipper_id, tipper_beacon, recipient_id, recipient_beacon,
             tip_method, amount_urtc, fee_urtc, net_urtc, platform,
             content_id, emoji, now)
        )

        # Credit fee to social mining pool
        conn.execute(
            "UPDATE social_mining_pool SET "
            "balance_urtc = balance_urtc + ?, "
            "total_inflow_urtc = total_inflow_urtc + ?, "
            "updated_at = ? "
            "WHERE id = 1",
            (fee_urtc, fee_urtc, now)
        )

        # Update tipper stats
        conn.execute(
            "UPDATE user_social_stats SET "
            "total_tips_sent_urtc = total_tips_sent_urtc + ?, "
            "last_active = ? "
            "WHERE user_id = ?",
            (amount_urtc, now, tipper_id)
        )

        # Update recipient stats
        conn.execute(
            "UPDATE user_social_stats SET "
            "total_tips_received_urtc = total_tips_received_urtc + ?, "
            "last_active = ? "
            "WHERE user_id = ?",
            (net_urtc, now, recipient_id)
        )

        conn.commit()

        log.info(
            "Tip: %s -> %s | %d uRTC (fee: %d, net: %d)",
            tipper_id, recipient_id, amount_urtc, fee_urtc, net_urtc
        )

        return {
            "success": True,
            "amount_urtc": amount_urtc,
            "fee_urtc": fee_urtc,
            "net_urtc": net_urtc,
            "social_mining_pool_fee_pct": TIP_FEE_PCT,
            "tipper_id": tipper_id,
            "recipient_id": recipient_id,
            "timestamp": now,
        }
    except sqlite3.Error as e:
        conn.rollback()
        log.error("Tip processing failed: %s", e)
        return {"success": False, "error": f"Database error: {e}"}
    finally:
        conn.close()


# ─── Phase 2: Automated Social Rewards ──────────────────────────────────────

def record_social_action(
    user_id: str,
    beacon_id: str,
    platform: str,
    action_type: str,
    content_id: str,
    content_length: int = 0,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """Record a social action and calculate RIP-310 reward.

    Phase 2: Automated post/comment/video rewards with RIP-309 anti-gaming.

    Each epoch, the active metrics rotate so users can't game one metric.
    """
    # Verify Beacon ID
    if not verify_beacon_id(beacon_id, db_path):
        return {"success": False, "error": "No valid Beacon ID"}

    # Check frequency cap
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not _increment_daily_count(
        user_id, beacon_id, platform, action_type, date_str, db_path
    ):
        return {"success": False, "error": "Daily frequency cap reached"}

    # Validate content for comments
    if action_type == Action.COMMENT.value and content_length < MIN_COMMENT_LENGTH:
        return {
            "success": False,
            "error": f"Comment too short ({content_length} < {MIN_COMMENT_LENGTH} chars)"
        }

    # Get current RIP-309 epoch and metric weights
    epoch = get_or_create_epoch(db_path=db_path)
    metric_key = {
        Action.POST.value: "posts",
        Action.COMMENT.value: "comments",
        Action.VIDEO_UPLOAD.value: "video_uploads",
        Action.UPVOTE.value: "upvotes",
    }.get(action_type, "posts")

    weight = epoch["metric_weights"].get(metric_key, 0.1)

    # Base reward in uRTC
    base_rewards = {
        Action.POST.value: (
            REWARD_MOLBOOK_POST if platform == Platform.MOLBOOK.value
            else REWARD_4CLAW_POST
        ),
        Action.COMMENT.value: REWARD_COMMENT,
        Action.VIDEO_UPLOAD.value: REWARD_BOTTUBE_UPLOAD,
        Action.UPVOTE.value: REWARD_UPVOTE,
    }
    base = base_rewards.get(action_type, 0)
    reward_urtc = int(base * weight)

    if reward_urtc <= 0:
        return {
            "success": False,
            "error": "This action type is not rewarded in the current epoch"
        }

    conn = _get_conn(db_path)
    try:
        now = time.time()

        # Record action
        conn.execute(
            "INSERT OR IGNORE INTO social_actions "
            "(user_id, beacon_id, platform, action_type, content_id, "
            "content_length, reward_urtc, epoch_nonce, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, beacon_id, platform, action_type, content_id,
             content_length, reward_urtc, epoch["epoch_num"], now)
        )

        # Debit reward from social mining pool
        conn.execute(
            "UPDATE social_mining_pool SET "
            "balance_urtc = balance_urtc - ?, "
            "total_outflow_urtc = total_outflow_urtc + ?, "
            "updated_at = ? "
            "WHERE id = 1",
            (reward_urtc, reward_urtc, now)
        )

        # Update user stats
        stat_field = {
            Action.POST.value: "total_posts",
            Action.COMMENT.value: "total_comments",
            Action.VIDEO_UPLOAD.value: "total_videos",
            Action.UPVOTE.value: "total_upvotes_received",
        }.get(action_type)

        if stat_field:
            conn.execute(
                f"UPDATE user_social_stats SET "
                f"{stat_field} = {stat_field} + 1, "
                f"total_earned_urtc = total_earned_urtc + ?, "
                f"last_active = ? "
                f"WHERE user_id = ?",
                (reward_urtc, now, user_id)
            )

        conn.commit()

        log.info(
            "Social action: %s %s on %s | reward: %d uRTC (weight: %.2f)",
            user_id, action_type, platform, reward_urtc, weight
        )

        return {
            "success": True,
            "reward_urtc": reward_urtc,
            "epoch_num": epoch["epoch_num"],
            "metric_weight": weight,
            "active_metrics": epoch["active_metrics"],
        }
    except sqlite3.Error as e:
        conn.rollback()
        log.error("Social action recording failed: %s", e)
        return {"success": False, "error": f"Database error: {e}"}
    finally:
        conn.close()


# ─── Phase 3: Cross-Platform Engagement Bonus ───────────────────────────────

def compute_cross_platform_bonus(user_id: str, db_path: str = DB_PATH) -> int:
    """Calculate bonus for users active on multiple platforms.

    Phase 3: Cross-platform engagement bonus.
    Users who post on 2+ platforms get a multiplier bonus.
    """
    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(DISTINCT platform) as platform_count "
            "FROM social_actions WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        platform_count = row["platform_count"] if row else 0

        # Bonus tiers
        if platform_count >= 3:
            return int(0.05 * UNIT)  # 0.05 RTC bonus
        elif platform_count >= 2:
            return int(0.02 * UNIT)  # 0.02 RTC bonus
        return 0
    finally:
        conn.close()


def award_video_upload(user_id: str, beacon_id: str, content_id: str,
                       video_duration_sec: int = 0,
                       db_path: str = DB_PATH) -> Dict[str, Any]:
    """Process a BoTTube video upload with duration validation.

    Phase 3: Video upload rewards with minimum duration check.
    """
    if video_duration_sec < MIN_VIDEO_DURATION_SEC:
        return {
            "success": False,
            "error": f"Video too short ({video_duration_sec}s < "
                     f"{MIN_VIDEO_DURATION_SEC}s)"
        }

    result = record_social_action(
        user_id=user_id,
        beacon_id=beacon_id,
        platform=Platform.BOTTUBE.value,
        action_type=Action.VIDEO_UPLOAD.value,
        content_id=content_id,
        db_path=db_path,
    )

    # Add cross-platform bonus
    if result.get("success"):
        bonus = compute_cross_platform_bonus(user_id, db_path)
        if bonus > 0:
            result["cross_platform_bonus_urtc"] = bonus
            result["reward_urtc"] += bonus

    return result


# ─── Phase 4: Quality Scoring & Leaderboards ────────────────────────────────

def update_content_quality(content_id: str, platform: str, user_id: str,
                           upvote_delta: int = 0,
                           tip_delta_urtc: int = 0,
                           comment_delta: int = 0,
                           db_path: str = DB_PATH) -> Dict[str, Any]:
    """Update content quality score based on engagement signals.

    Phase 4: Quality scoring using upvotes, tips, and comments.
    Score = sigmoid(upvotes * 0.3 + tips_rtc * 0.4 + comments * 0.3)
    """
    conn = _get_conn(db_path)
    try:
        now = time.time()

        # Get or create quality record
        conn.execute(
            "INSERT OR IGNORE INTO content_quality "
            "(content_id, platform, user_id, quality_score, "
            "upvote_count, tip_count, total_tips_urtc, "
            "comment_count, last_updated) "
            "VALUES (?, ?, ?, 0.5, 0, 0, 0, 0, ?)",
            (content_id, platform, user_id, now)
        )

        # Apply deltas
        conn.execute(
            "UPDATE content_quality SET "
            "upvote_count = upvote_count + ?, "
            "tip_count = tip_count + CASE WHEN ? > 0 THEN 1 ELSE 0 END, "
            "total_tips_urtc = total_tips_urtc + ?, "
            "comment_count = comment_count + ?, "
            "last_updated = ? "
            "WHERE content_id = ? AND platform = ?",
            (upvote_delta, tip_delta_urtc, tip_delta_urtc, comment_delta,
             now, content_id, platform)
        )

        # Recalculate quality score
        row = conn.execute(
            "SELECT upvote_count, total_tips_urtc, comment_count "
            "FROM content_quality "
            "WHERE content_id = ? AND platform = ?",
            (content_id, platform)
        ).fetchone()

        if row:
            import math
            upvotes = row["upvote_count"]
            tips_rtc = row["total_tips_urtc"] / UNIT
            comments = row["comment_count"]

            # Sigmoid-based quality score
            raw = upvotes * 0.3 + tips_rtc * 0.4 + comments * 0.3
            score = 1.0 / (1.0 + math.exp(-raw / 10))

            conn.execute(
                "UPDATE content_quality SET quality_score = ? "
                "WHERE content_id = ? AND platform = ?",
                (round(score, 4), content_id, platform)
            )
            conn.commit()

            return {
                "success": True,
                "quality_score": round(score, 4),
                "upvotes": upvotes,
                "tips_rtc": round(tips_rtc, 2),
                "comments": comments,
            }

        return {"success": False, "error": "Content not found"}
    except sqlite3.Error as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_leaderboard(limit: int = 20, db_path: str = DB_PATH) -> List[Dict]:
    """Get social mining leaderboard sorted by total earned.

    Phase 4: Creator leaderboard.
    """
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT user_id, beacon_id, total_earned_urtc, "
            "total_tips_sent_urtc, total_tips_received_urtc, "
            "total_posts, total_comments, total_videos, "
            "total_upvotes_received, last_active "
            "FROM user_social_stats "
            "ORDER BY total_earned_urtc DESC LIMIT ?",
            (limit,)
        ).fetchall()

        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_treasury_report(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Get social mining pool treasury sustainability report.

    Phase 4: Treasury reporting.
    """
    conn = _get_conn(db_path)
    try:
        pool = conn.execute(
            "SELECT * FROM social_mining_pool WHERE id = 1"
        ).fetchone()

        # Recent inflows (last 24h from tips)
        now = time.time()
        inflow_24h = conn.execute(
            "SELECT COALESCE(SUM(fee_urtc), 0) as total "
            "FROM tips WHERE timestamp > ?",
            (now - 86400,)
        ).fetchone()["total"]

        # Recent outflows (last 24h from rewards)
        outflow_24h = conn.execute(
            "SELECT COALESCE(SUM(reward_urtc), 0) as total "
            "FROM social_actions WHERE timestamp > ?",
            (now - 86400,)
        ).fetchone()["total"]

        # Unique active users (last 24h)
        active_users = conn.execute(
            "SELECT COUNT(DISTINCT user_id) as count "
            "FROM user_social_stats WHERE last_active > ?",
            (now - 86400,)
        ).fetchone()["count"]

        balance = pool["balance_urtc"] if pool else 0
        sustainability_days = (
            outflow_24h > 0
            and balance / outflow_24h
            or float("inf")
        )

        return {
            "balance_urtc": balance,
            "balance_rtc": round(balance / UNIT, 2),
            "total_inflow_urtc": pool["total_inflow_urtc"] if pool else 0,
            "total_outflow_urtc": pool["total_outflow_urtc"] if pool else 0,
            "inflow_24h_urtc": inflow_24h,
            "outflow_24h_urtc": outflow_24h,
            "net_24h_urtc": inflow_24h - outflow_24h,
            "active_users_24h": active_users,
            "sustainability_days": round(sustainability_days, 1),
            "tip_fee_pct": TIP_FEE_PCT,
        }
    finally:
        conn.close()


# ─── Epoch Settlement Integration ───────────────────────────────────────────

def redirect_epoch_reward_to_social_pool(
    epoch_reward_urtc: int,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """Redirect a portion of epoch mining rewards to the social mining pool.

    This is called during epoch settlement to fund the social economy.
    10% of epoch mining rewards are redirected.
    """
    redirect_amount = int(epoch_reward_urtc * EPOCH_REWARD_REDIRECT_PCT)

    conn = _get_conn(db_path)
    try:
        now = time.time()
        conn.execute(
            "UPDATE social_mining_pool SET "
            "balance_urtc = balance_urtc + ?, "
            "total_inflow_urtc = total_inflow_urtc + ?, "
            "updated_at = ? "
            "WHERE id = 1",
            (redirect_amount, redirect_amount, now)
        )
        conn.commit()

        log.info(
            "Epoch reward redirect: %d uRTC (%.1f%% of %d)",
            redirect_amount, EPOCH_REWARD_REDIRECT_PCT * 100,
            epoch_reward_urtc
        )

        return {
            "success": True,
            "redirected_urtc": redirect_amount,
            "pct": EPOCH_REWARD_REDIRECT_PCT,
        }
    except sqlite3.Error as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


# ─── Flask API Routes (Phase 1 + 4) ─────────────────────────────────────────

def register_social_mining_routes(app, db_path: str = DB_PATH):
    """Register Flask API routes for the social mining protocol."""
    try:
        from flask import request, jsonify
    except ImportError:
        log.warning("Flask not available, skipping route registration")
        return

    # ── Phase 1: Tip ────────────────────────────────────────────────────

    @app.route("/api/social/tip", methods=["POST"])
    def api_tip():
        """POST /api/social/tip
        {
            "tipper_id": "...", "tipper_beacon": "...",
            "recipient_id": "...", "recipient_beacon": "...",
            "amount_urtc": 5000000,
            "tip_method": "command" | "emoji",
            "platform": "moltbook" | "4claw" | "bottube",
            "emoji": "🦞"  // optional for emoji tips
        }
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        result = process_tip(
            tipper_id=data["tipper_id"],
            tipper_beacon=data["tipper_beacon"],
            recipient_id=data["recipient_id"],
            recipient_beacon=data["recipient_beacon"],
            amount_urtc=data["amount_urtc"],
            tip_method=data.get("tip_method", TipMethod.COMMAND.value),
            platform=data.get("platform", Platform.MOLBOOK.value),
            emoji=data.get("emoji"),
            db_path=db_path,
        )

        if result["success"]:
            return jsonify(result), 200
        return jsonify(result), 400

    # ── Phase 2: Social Action ──────────────────────────────────────────

    @app.route("/api/social/action", methods=["POST"])
    def api_social_action():
        """POST /api/social/action
        {
            "user_id": "...", "beacon_id": "...",
            "platform": "moltbook" | "4claw" | "bottube",
            "action_type": "post" | "comment" | "video_upload" | "upvote",
            "content_id": "...",
            "content_length": 120  // optional for comments
        }
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        result = record_social_action(
            user_id=data["user_id"],
            beacon_id=data["beacon_id"],
            platform=data["platform"],
            action_type=data["action_type"],
            content_id=data["content_id"],
            content_length=data.get("content_length", 0),
            db_path=db_path,
        )

        if result["success"]:
            return jsonify(result), 200
        return jsonify(result), 400

    # ── Phase 3: Video Upload ───────────────────────────────────────────

    @app.route("/api/social/video", methods=["POST"])
    def api_video_upload():
        """POST /api/social/video
        {
            "user_id": "...", "beacon_id": "...",
            "content_id": "...",
            "video_duration_sec": 45
        }
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        result = award_video_upload(
            user_id=data["user_id"],
            beacon_id=data["beacon_id"],
            content_id=data["content_id"],
            video_duration_sec=data.get("video_duration_sec", 0),
            db_path=db_path,
        )

        if result["success"]:
            return jsonify(result), 200
        return jsonify(result), 400

    # ── Phase 4: Leaderboard ────────────────────────────────────────────

    @app.route("/api/social/leaderboard", methods=["GET"])
    def api_leaderboard():
        """GET /api/social/leaderboard?limit=20"""
        limit = request.args.get("limit", 20, type=int)
        return jsonify(get_leaderboard(limit, db_path))

    # ── Phase 4: Treasury Report ────────────────────────────────────────

    @app.route("/api/social/treasury", methods=["GET"])
    def api_treasury():
        """GET /api/social/treasury"""
        return jsonify(get_treasury_report(db_path))

    # ── User Registration ───────────────────────────────────────────────

    @app.route("/api/social/register", methods=["POST"])
    def api_register():
        """POST /api/social/register
        {"user_id": "...", "beacon_id": "..."}
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        success = register_beacon_user(
            data["user_id"], data["beacon_id"], db_path
        )
        if success:
            return jsonify({"success": True}), 200
        return jsonify({"success": False, "error": "Invalid beacon_id"}), 400

    # ── RIP-309 Epoch Info ──────────────────────────────────────────────

    @app.route("/api/social/epoch", methods=["GET"])
    def api_epoch():
        """GET /api/social/epoch"""
        return jsonify(get_or_create_epoch(db_path=db_path))

    # ── Content Quality Update ──────────────────────────────────────────

    @app.route("/api/social/quality", methods=["POST"])
    def api_quality():
        """POST /api/social/quality
        {
            "content_id": "...", "platform": "...", "user_id": "...",
            "upvote_delta": 1, "tip_delta_urtc": 0, "comment_delta": 0
        }
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        result = update_content_quality(
            content_id=data["content_id"],
            platform=data["platform"],
            user_id=data["user_id"],
            upvote_delta=data.get("upvote_delta", 0),
            tip_delta_urtc=data.get("tip_delta_urtc", 0),
            comment_delta=data.get("comment_delta", 0),
            db_path=db_path,
        )

        if result.get("success"):
            return jsonify(result), 200
        return jsonify(result), 400

    log.info("Social mining API routes registered")


# ─── CLI / Standalone Entry ──────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Initialize DB
    init_social_mining_db()
    print("Social mining database initialized.")

    # Register a test user
    register_beacon_user("alice", "beacon_alice_001")
    register_beacon_user("bob", "beacon_bob_002")
    print("Registered test users: alice, bob")

    # Test tip
    result = process_tip(
        tipper_id="alice", tipper_beacon="beacon_alice_001",
        recipient_id="bob", recipient_beacon="beacon_bob_002",
        amount_urtc=5_000_000,  # 5 RTC
    )
    print(f"Tip result: {result}")

    # Test social action
    result = record_social_action(
        user_id="alice", beacon_id="beacon_alice_001",
        platform="moltbook", action_type="post",
        content_id="post_001",
    )
    print(f"Social action result: {result}")

    # Treasury report
    report = get_treasury_report()
    print(f"Treasury report: {json.dumps(report, indent=2)}")
