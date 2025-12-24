"""
RustChain v2 Rewards Implementation
To integrate: call register_rewards(app, DB_PATH)
"""

import time
import sqlite3
from flask import request, jsonify

# ---- Rewards constants/util ----
UNIT = 100_000_000  # uRTC (1 RTC = 100 million micro-RTC)
PER_EPOCH_URTC = int(1.5 * UNIT)  # 1.5 RTC per epoch

def _epoch_eligible_miners(db, epoch: int):
    """Get list of miners eligible for epoch rewards"""
    # Prefer explicit enroll table if present
    try:
        rows = db.execute(
            "SELECT DISTINCT miner_id FROM epoch_enroll WHERE epoch=?",
            (epoch,)
        ).fetchall()
        elig = [r[0] for r in rows]
        if elig:
            return elig
    except Exception:
        pass

    # Fallback: anyone who submitted a valid header in this epoch
    # Use actual slot-to-epoch mapping
    first_slot = epoch * 144  # 144 blocks per epoch (example)
    last_slot = first_slot + 143

    rows = db.execute(
        "SELECT DISTINCT miner_id FROM headers WHERE slot BETWEEN ? AND ?",
        (first_slot, last_slot)
    ).fetchall()
    return [r[0] for r in rows]

def settle_epoch(db, epoch: int):
    """Settle rewards for a completed epoch - idempotent"""
    # Check if already settled
    st = db.execute("SELECT settled FROM epoch_state WHERE epoch=?", (epoch,)).fetchone()
    if st and int(st[0]) == 1:
        return {"ok": True, "epoch": epoch, "already_settled": True}

    miners = _epoch_eligible_miners(db, epoch)
    n = len(miners)

    if n == 0:
        db.execute("INSERT OR REPLACE INTO epoch_state(epoch, settled, settled_ts) VALUES (?,?,?)",
                   (epoch, 1, int(time.time())))
        db.commit()
        return {"ok": True, "epoch": epoch, "eligible": 0, "distributed_urtc": 0}

    # Split 1.5 RTC equally among eligible miners
    share = PER_EPOCH_URTC // n
    remainder = PER_EPOCH_URTC - (share * n)

    ts = int(time.time())
    for i, m in enumerate(miners):
        # Distribute remainder deterministically (first N miners get +1 uRTC)
        this_share = share + (1 if i < remainder else 0)

        db.execute("INSERT OR IGNORE INTO epoch_rewards(epoch, miner_id, share_i64) VALUES (?,?,?)",
                   (epoch, m, this_share))
        db.execute("INSERT INTO ledger(ts, epoch, miner_id, delta_i64, reason) VALUES (?,?,?,?,?)",
                   (ts, epoch, m, this_share, "epoch_reward"))

        # Upsert balance
        cur = db.execute("UPDATE balances SET amount_i64 = amount_i64 + ? WHERE miner_id=?",
                         (this_share, m))
        if cur.rowcount == 0:
            db.execute("INSERT INTO balances(miner_id, amount_i64) VALUES(?,?)",
                       (m, this_share))

    db.execute("INSERT OR REPLACE INTO epoch_state(epoch, settled, settled_ts) VALUES (?,?,?)",
               (epoch, 1, ts))
    db.commit()

    return {
        "ok": True,
        "epoch": epoch,
        "eligible": n,
        "share_i64": share,
        "distributed_urtc": PER_EPOCH_URTC,
        "distributed_rtc": PER_EPOCH_URTC / UNIT
    }

def total_balances(db):
    """Get total balance across all miners"""
    try:
        row = db.execute("SELECT COALESCE(SUM(amount_i64),0) FROM balances").fetchone()
        return int(row[0])
    except Exception:
        return 0

def register_rewards(app, DB_PATH):
    """Register all rewards-related Flask routes"""
    
    @app.route('/rewards/settle', methods=['POST'])
    def api_rewards_settle():
        """Settle rewards for a specific epoch (admin/cron callable)"""
        body = request.get_json(force=True, silent=True) or {}
        epoch = int(body.get("epoch", -1))
        if epoch < 0:
            return jsonify({"ok": False, "error": "epoch required"}), 400

        with sqlite3.connect(DB_PATH) as db:
            res = settle_epoch(db, epoch)
        return jsonify(res)

    @app.route('/rewards/epoch/<int:epoch>', methods=['GET'])
    def api_rewards_epoch(epoch: int):
        """Get reward distribution for a specific epoch"""
        with sqlite3.connect(DB_PATH) as db:
            rows = db.execute(
                "SELECT miner_id, share_i64 FROM epoch_rewards WHERE epoch=? ORDER BY miner_id",
                (epoch,)
            ).fetchall()

        return jsonify({
            "epoch": epoch,
            "rewards": [
                {
                    "miner_id": r[0],
                    "share_i64": int(r[1]),
                    "share_rtc": int(r[1]) / UNIT
                } for r in rows
            ]
        })

    @app.route('/wallet/balance', methods=['GET'])
    def api_wallet_balance():
        """Get balance for a specific miner"""
        miner_id = request.args.get("miner_id", "").strip()
        if not miner_id:
            return jsonify({"ok": False, "error": "miner_id required"}), 400

        with sqlite3.connect(DB_PATH) as db:
            row = db.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (miner_id,)).fetchone()

        amt = int(row[0]) if row else 0
        return jsonify({
            "miner_id": miner_id,
            "amount_i64": amt,
            "amount_rtc": amt / UNIT
        })

    @app.route('/wallet/ledger', methods=['GET'])
    def api_wallet_ledger():
        """Get transaction ledger (optionally filtered by miner)"""
        miner_id = request.args.get("miner_id", "").strip()

        with sqlite3.connect(DB_PATH) as db:
            if miner_id:
                rows = db.execute(
                    "SELECT ts, epoch, delta_i64, reason FROM ledger WHERE miner_id=? ORDER BY id DESC LIMIT 200",
                    (miner_id,)
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT ts, epoch, miner_id, delta_i64, reason FROM ledger ORDER BY id DESC LIMIT 200"
                ).fetchall()

        items = []
        for r in rows:
            if miner_id:
                ts, epoch, delta, reason = r
                items.append({
                    "ts": int(ts),
                    "epoch": int(epoch),
                    "miner_id": miner_id,
                    "delta_i64": int(delta),
                    "delta_rtc": int(delta) / UNIT,
                    "reason": reason
                })
            else:
                ts, epoch, m, delta, reason = r
                items.append({
                    "ts": int(ts),
                    "epoch": int(epoch),
                    "miner_id": m,
                    "delta_i64": int(delta),
                    "delta_rtc": int(delta) / UNIT,
                    "reason": reason
                })

        return jsonify({"items": items})

    @app.route('/wallet/balances/all', methods=['GET'])
    def api_wallet_balances_all():
        """Get all miner balances"""
        with sqlite3.connect(DB_PATH) as db:
            rows = db.execute(
                "SELECT miner_id, amount_i64 FROM balances ORDER BY amount_i64 DESC"
            ).fetchall()

        return jsonify({
            "balances": [
                {
                    "miner_id": r[0],
                    "amount_i64": int(r[1]),
                    "amount_rtc": int(r[1]) / UNIT
                } for r in rows
            ],
            "total_i64": sum(int(r[1]) for r in rows),
            "total_rtc": sum(int(r[1]) for r in rows) / UNIT
        })
