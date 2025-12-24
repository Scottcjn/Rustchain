#!/usr/bin/env python3
"""
RustChain Rewards with RIP-200: Round-Robin + Time-Aging
Replaces VRF lottery with 1 CPU = 1 vote deterministic consensus
"""

import sqlite3
import time
from flask import request, jsonify

# Import RIP-200 functions
import sys
sys.path.insert(0, '/root/rustchain')
from rip_200_round_robin_1cpu1vote import (
    get_time_aged_multiplier,
    get_chain_age_years,
    calculate_epoch_rewards_time_aged,
    get_round_robin_producer,
    get_attested_miners,
    check_eligibility_round_robin
)

# Constants
UNIT = 100_000_000  # uRTC per 1 RTC
DB_PATH = "/root/rustchain/rustchain_v2.db"
PER_EPOCH_URTC = int(1.5 * UNIT)  # 150,000,000 uRTC
BLOCK_TIME = 600
GENESIS_TIMESTAMP = 1728000000  # Placeholder - will be set from server

def current_slot():
    """Get current blockchain slot"""
    return (int(time.time()) - GENESIS_TIMESTAMP) // BLOCK_TIME

def slot_to_epoch(slot):
    """Convert slot to epoch (144 blocks per epoch)"""
    return slot // 144

def settle_epoch_rip200(db_path, epoch: int):
    """
    Settle rewards for an epoch using RIP-200 time-aged multipliers

    Args:
        db_path: Database connection or path
        epoch: Epoch number to settle

    Returns:
        {
            "ok": True,
            "epoch": epoch number,
            "distributed_rtc": float,
            "miners": [{miner_id, share_urtc, multiplier}, ...],
            "already_settled": bool
        }
    """
    # Handle both connection and path
    if isinstance(db_path, str):
        db = sqlite3.connect(db_path)
        own_conn = True
    else:
        db = db_path
        own_conn = False

    try:
        # Check if already settled
        st = db.execute("SELECT settled FROM epoch_state WHERE epoch=?", (epoch,)).fetchone()
        if st and int(st[0]) == 1:
            return {"ok": True, "epoch": epoch, "already_settled": True}

        # Calculate current slot for age calculation
        current = current_slot()

        # Get time-aged reward distribution
        rewards = calculate_epoch_rewards_time_aged(
            db_path if isinstance(db_path, str) else DB_PATH,  # Pass path for RIP-200 functions
            epoch,
            PER_EPOCH_URTC,
            current
        )

        if not rewards:
            return {"ok": False, "error": "no_eligible_miners", "epoch": epoch}

        # Credit rewards to miners
        ts_now = int(time.time())
        miners_data = []

        for miner_id, share_urtc in rewards.items():
            # Insert or update balance
            db.execute(
                "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?) "
                "ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = amount_i64 + ?",
                (miner_id, share_urtc, share_urtc)
            )

            # Record in ledger
            db.execute(
                "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?, ?, ?, ?, ?)",
                (ts_now, epoch, miner_id, share_urtc, f"epoch_{epoch}_reward")
            )

            # Record in epoch_rewards
            db.execute(
                "INSERT INTO epoch_rewards (epoch, miner_id, share_i64) VALUES (?, ?, ?)",
                (epoch, miner_id, share_urtc)
            )

            # Get multiplier for reporting
            chain_age = get_chain_age_years(current)
            # Get device arch from attestation
            arch_row = db.execute(
                "SELECT device_arch FROM miner_attest_recent WHERE miner = ? LIMIT 1",
                (miner_id,)
            ).fetchone()
            device_arch = arch_row[0] if arch_row else "unknown"
            multiplier = get_time_aged_multiplier(device_arch, chain_age)

            miners_data.append({
                "miner_id": miner_id,
                "share_urtc": share_urtc,
                "share_rtc": share_urtc / UNIT,
                "multiplier": round(multiplier, 3),
                "device_arch": device_arch
            })

        # Mark epoch as settled
        db.execute(
            "INSERT OR REPLACE INTO epoch_state (epoch, settled, settled_ts) VALUES (?, 1, ?)",
            (epoch, ts_now)
        )

        db.commit()

        return {
            "ok": True,
            "epoch": epoch,
            "distributed_rtc": PER_EPOCH_URTC / UNIT,
            "distributed_urtc": PER_EPOCH_URTC,
            "miners": miners_data,
            "chain_age_years": round(get_chain_age_years(current), 2)
        }

    finally:
        if own_conn:
            db.close()

def total_balances(db):
    """Get total balance across all miners"""
    try:
        row = db.execute("SELECT COALESCE(SUM(amount_i64),0) FROM balances").fetchone()
        return int(row[0])
    except Exception:
        return 0

def register_rewards_rip200(app, DB_PATH):
    """Register RIP-200 rewards endpoints"""

    @app.route('/rewards/settle', methods=['POST'])
    def settle_rewards():
        data = request.json or {}
        epoch = data.get('epoch')

        if epoch is None:
            # Auto-settle previous epoch
            current = current_slot()
            current_epoch = slot_to_epoch(current)
            epoch = current_epoch - 1

        result = settle_epoch_rip200(DB_PATH, epoch)
        return jsonify(result)

    @app.route('/wallet/balance', methods=['GET'])
    def get_balance():
        miner_id = request.args.get('miner_id')
        if not miner_id:
            return jsonify({"error": "miner_id required"}), 400

        with sqlite3.connect(DB_PATH) as db:
            row = db.execute(
                "SELECT amount_i64 FROM balances WHERE miner_id = ?",
                (miner_id,)
            ).fetchone()

            amount_i64 = int(row[0]) if row else 0
            return jsonify({
                "miner_id": miner_id,
                "amount_i64": amount_i64,
                "amount_rtc": amount_i64 / UNIT
            })

    @app.route('/wallet/balances/all', methods=['GET'])
    def get_all_balances():
        with sqlite3.connect(DB_PATH) as db:
            rows = db.execute(
                "SELECT miner_id, amount_i64 FROM balances WHERE amount_i64 > 0 ORDER BY amount_i64 DESC"
            ).fetchall()

            balances = [
                {
                    "miner_id": row[0],
                    "amount_i64": int(row[1]),
                    "amount_rtc": int(row[1]) / UNIT
                }
                for row in rows
            ]

            total = sum(b["amount_i64"] for b in balances)

            return jsonify({
                "balances": balances,
                "total_urtc": total,
                "total_rtc": total / UNIT
            })

    @app.route('/lottery/eligibility', methods=['GET'])
    def check_eligibility():
        """RIP-200: Round-robin eligibility check"""
        miner_id = request.args.get('miner_id')
        if not miner_id:
            return jsonify({"error": "miner_id required"}), 400

        current = current_slot()
        current_ts = int(time.time())

        result = check_eligibility_round_robin(DB_PATH, miner_id, current, current_ts)
        return jsonify(result)

    @app.route('/consensus/round_robin_status', methods=['GET'])
    def round_robin_status():
        """Get current round-robin rotation status"""
        current = current_slot()
        current_ts = int(time.time())

        attested_miners = get_attested_miners(DB_PATH, current_ts)
        current_producer = get_round_robin_producer(current, attested_miners)
        chain_age = get_chain_age_years(current)

        # Get multipliers for all attested miners
        miners_info = []
        for miner_id, device_arch in attested_miners:
            multiplier = get_time_aged_multiplier(device_arch, chain_age)
            miners_info.append({
                "miner_id": miner_id,
                "device_arch": device_arch,
                "multiplier": round(multiplier, 3)
            })

        return jsonify({
            "current_slot": current,
            "current_producer": current_producer,
            "rotation_size": len(attested_miners),
            "attested_miners": miners_info,
            "chain_age_years": round(chain_age, 2)
        })

    print("[RIP-200] Round-robin consensus endpoints registered")
