# SPDX-License-Identifier: MIT
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NODE_DIR = PROJECT_ROOT / "node"
if str(NODE_DIR) not in sys.path:
    sys.path.insert(0, str(NODE_DIR))

import rip_200_round_robin_1cpu1vote as rip200


def test_epoch_rewards_apply_warthog_bonus_from_enrollment_path(tmp_path):
    db_path = tmp_path / "rewards.db"
    with sqlite3.connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE epoch_enroll (
                epoch INTEGER NOT NULL,
                miner_pk TEXT NOT NULL,
                weight REAL NOT NULL
            );
            CREATE TABLE miner_attest_recent (
                miner TEXT NOT NULL,
                device_arch TEXT,
                fingerprint_passed INTEGER DEFAULT 1,
                fingerprint_checks_json TEXT,
                warthog_bonus REAL DEFAULT 1.0
            );
            """
        )
        db.executemany(
            "INSERT INTO epoch_enroll(epoch, miner_pk, weight) VALUES (0, ?, 1.0)",
            [("miner_bonus",), ("miner_plain",)],
        )
        db.executemany(
            """
            INSERT INTO miner_attest_recent(
                miner, device_arch, fingerprint_passed, fingerprint_checks_json, warthog_bonus
            )
            VALUES (?, 'x86_64', 1, '{}', ?)
            """,
            [("miner_bonus", 1.15), ("miner_plain", 1.0)],
        )

    total_reward = 2_150_000
    rewards = rip200.calculate_epoch_rewards_time_aged(
        str(db_path),
        epoch=0,
        total_reward_urtc=total_reward,
        current_slot=0,
    )

    bonus_share = int((1.15 / 2.15) * total_reward)
    assert rewards == {
        "miner_bonus": bonus_share,
        "miner_plain": total_reward - bonus_share,
    }


def test_epoch_rewards_fallback_allows_checks_without_warthog_bonus(tmp_path):
    db_path = tmp_path / "legacy_rewards.db"
    with sqlite3.connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE miner_attest_recent (
                miner TEXT NOT NULL,
                device_arch TEXT,
                ts_ok INTEGER NOT NULL,
                fingerprint_passed INTEGER DEFAULT 1,
                fingerprint_checks_json TEXT
            );
            """
        )
        db.executemany(
            """
            INSERT INTO miner_attest_recent(
                miner, device_arch, ts_ok, fingerprint_passed, fingerprint_checks_json
            )
            VALUES (?, 'x86_64', ?, 1, '{}')
            """,
            [("legacy_a", rip200.GENESIS_TIMESTAMP), ("legacy_b", rip200.GENESIS_TIMESTAMP)],
        )

    rewards = rip200.calculate_epoch_rewards_time_aged(
        str(db_path),
        epoch=0,
        total_reward_urtc=100,
        current_slot=0,
    )

    assert rewards == {"legacy_a": 50, "legacy_b": 50}
