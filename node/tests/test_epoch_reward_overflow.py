# SPDX-License-Identifier: MIT
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


NODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NODE_DIR))

from rip_200_round_robin_1cpu1vote import (  # noqa: E402
    EPOCH_WEIGHT_SCALE,
    MAX_EPOCH_WEIGHT,
    calculate_epoch_rewards_time_aged,
)


def _create_enrolled_db(rows, weight_type="INTEGER"):
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE miner_attest_recent (
                miner TEXT,
                device_arch TEXT,
                fingerprint_passed INTEGER DEFAULT 1,
                fingerprint_checks_json TEXT DEFAULT '{}',
                warthog_bonus REAL DEFAULT 1.0
            );
            """
        )
        conn.execute(
            f"""
            CREATE TABLE epoch_enroll (
                epoch INTEGER,
                miner_pk TEXT,
                weight {weight_type},
                PRIMARY KEY (epoch, miner_pk)
            )
            """
        )
        conn.executemany(
            "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
            rows,
        )
        conn.executemany(
            """
            INSERT INTO miner_attest_recent
            (miner, device_arch, fingerprint_passed, fingerprint_checks_json, warthog_bonus)
            VALUES (?, 'g4', 1, '{}', 1.0)
            """,
            [(miner_pk,) for _epoch, miner_pk, _weight in rows],
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_large_enrolled_weight_is_capped_before_distribution():
    max_units = MAX_EPOCH_WEIGHT * EPOCH_WEIGHT_SCALE
    rows = [
        (7, "rogue", 9_000_000_000_000_000_000),
        (7, "honest", max_units),
    ]
    db_path = _create_enrolled_db(rows)
    try:
        rewards = calculate_epoch_rewards_time_aged(db_path, 7, 101, 7 * 144 + 1)
    finally:
        os.unlink(db_path)

    assert sum(rewards.values()) == 101
    assert sorted(rewards.values()) == [50, 51]
    assert rewards["rogue"] <= 51


def test_many_enrolled_miners_distribute_exactly_without_float_path():
    max_units = MAX_EPOCH_WEIGHT * EPOCH_WEIGHT_SCALE
    rows = [(8, f"miner_{idx:03}", max_units) for idx in range(150)]
    db_path = _create_enrolled_db(rows)
    try:
        rewards = calculate_epoch_rewards_time_aged(
            db_path, 8, 1_500_001, 8 * 144 + 1
        )
    finally:
        os.unlink(db_path)

    assert len(rewards) == 150
    assert sum(rewards.values()) == 1_500_001
    assert min(rewards.values()) == 10_000
    assert max(rewards.values()) == 10_001


def test_legacy_real_enrolled_weights_still_distribute_proportionally():
    rows = [
        (9, "g4_weight", 2.5),
        (9, "modern_weight", 1.0),
    ]
    db_path = _create_enrolled_db(rows, weight_type="REAL")
    try:
        rewards = calculate_epoch_rewards_time_aged(db_path, 9, 3_500, 9 * 144 + 1)
    finally:
        os.unlink(db_path)

    assert rewards == {"g4_weight": 2_500, "modern_weight": 1_000}
