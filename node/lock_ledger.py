#!/usr/bin/env python3
"""
RIP-0305: Lock Ledger Module
============================

Implements lock ledger management for tracking locked assets.
Track C: Bridge API + Lock Ledger

The lock ledger tracks assets that are:
- Locked for bridge transfers (pending external confirmation)
- Locked for epoch settlement (pending distribution)
- Locked for other protocol operations

Functions:
- create_lock() - Create a new lock entry
- release_lock() - Release a lock (credit back to owner)
- get_locks_by_miner() - Query locks for a miner
- get_pending_unlocks() - Get locks ready for release
- forfeit_lock() - Forfeit a lock (penalty/slashing)
"""

import hmac
import sqlite3
import time
import os
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

# Import from main node module
try:
    from rustchain_v2_integrated_v2_2_1_rip200 import (
        DB_PATH, 
        current_slot, 
        slot_to_epoch,
        UNIT
    )
except ImportError:
    # Fallback for standalone testing
    DB_PATH = os.environ.get("RC_DB_PATH", "rustchain.db")
    UNIT = 1000000  # Micro-units per RTC
    def current_slot() -> int:
        return int(time.time()) // 600
    def slot_to_epoch(slot: int) -> int:
        return slot // 144


# =============================================================================
# Configuration
# =============================================================================

LOCK_UNIT = UNIT  # Micro-units per RTC


# =============================================================================
# Enums and Data Classes
# =============================================================================

class LockType(Enum):
    BRIDGE_DEPOSIT = "bridge_deposit"
    BRIDGE_WITHDRAW = "bridge_withdraw"
    EPOCH_SETTLEMENT = "epoch_settlement"
    ADMIN_HOLD = "admin_hold"


class LockStatus(Enum):
    LOCKED = "locked"
    RELEASED = "released"
    FORFEITED = "forfeited"


@dataclass
class LockEntry:
    id: int
    bridge_transfer_id: Optional[int]
    miner_id: str
    amount_i64: int
    lock_type: str
    locked_at: int
    unlock_at: int
    unlocked_at: Optional[int]
    status: str
    created_at: int
    released_by: Optional[str]
    release_tx_hash: Optional[str]
    
    @property
    def amount_rtc(self) -> float:
        return self.amount_i64 / LOCK_UNIT
    
    @property
    def is_unlocked(self) -> bool:
        return self.unlocked_at is not None
    
    @property
    def time_until_unlock(self) -> int:
        if self.is_unlocked:
            return 0
        return max(0, self.unlock_at - int(time.time()))


# =============================================================================
# Core Lock Functions
# =============================================================================

def create_lock(
    db_conn: sqlite3.Connection,
    miner_id: str,
    amount_i64: int,
    lock_type: str,
    unlock_at: int,
    bridge_transfer_id: Optional[int] = None,
    created_at: Optional[int] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Create a new lock entry.
    
    Args:
        db_conn: Database connection
        miner_id: Miner ID who owns the locked assets
        amount_i64: Amount in micro-units
        lock_type: Type of lock (bridge_deposit, etc.)
        unlock_at: Unix timestamp when lock can be released
        bridge_transfer_id: Optional reference to bridge_transfers.id
        created_at: Optional creation timestamp (defaults to now)
    
    Returns:
        (success, result_dict)
    """
    cursor = db_conn.cursor()
    now = created_at or int(time.time())
    
    # Validate lock type
    valid_types = {lt.value for lt in LockType}
    if lock_type not in valid_types:
        return False, {
            "error": f"Invalid lock_type: {lock_type}",
            "valid_types": list(valid_types)
        }
    
    # Validate amount
    if amount_i64 <= 0:
        return False, {"error": "amount_i64 must be positive"}
    
    # Validate unlock time
    if unlock_at <= now:
        return False, {"error": "unlock_at must be in the future"}
    
    try:
        # Deduct locked amount from miner's balance atomically.
        # This ensures locked funds are unavailable for withdrawal/transfer.
        # INSERT OR IGNORE creates the row if the miner has no prior balance record.
        cursor.execute(
            "INSERT OR IGNORE INTO balances (miner_id, amount_i64) VALUES (?, 0)",
            (miner_id,)
        )
        cursor.execute(
            "UPDATE balances SET amount_i64 = amount_i64 - ? WHERE miner_id = ?",
            (amount_i64, miner_id)
        )

        # Verify the deduction did not go negative (sanity check)
        row = cursor.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            (miner_id,)
        ).fetchone()
        if row and row[0] < 0:
            # Roll back the deduction — this should never happen if callers
            # checked available balance before calling create_lock
            db_conn.rollback()
            return False, {
                "error": "Balance went negative after lock — insufficient available balance",
                "miner_id": miner_id,
                "amount_i64": amount_i64
            }

        cursor.execute("""
            INSERT INTO lock_ledger (
                bridge_transfer_id,
                miner_id,
                amount_i64,
                lock_type,
                locked_at,
                unlock_at,
                status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'locked', ?)
        """, (
            bridge_transfer_id,
            miner_id,
            amount_i64,
            lock_type,
            now,
            unlock_at,
            now
        ))
        
        lock_id = cursor.lastrowid
        db_conn.commit()
        
        return True, {
            "ok": True,
            "lock_id": lock_id,
            "miner_id": miner_id,
            "amount_rtc": amount_i64 / LOCK_UNIT,
            "lock_type": lock_type,
            "locked_at": now,
            "unlock_at": unlock_at,
            "status": "locked"
        }
        
    except sqlite3.Error as e:
        db_conn.rollback()
        return False, {
            "error": "Database error",
            "details": str(e)
        }


def release_lock(
    db_conn: sqlite3.Connection,
    lock_id: int,
    released_by: str = "system",
    release_tx_hash: Optional[str] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Release a lock, crediting assets back to owner.
    
    Args:
        db_conn: Database connection
        lock_id: Lock ledger entry ID
        released_by: Entity releasing the lock (admin/system)
        release_tx_hash: Optional transaction hash for the release
    
    Returns:
        (success, result_dict)
    """
    cursor = db_conn.cursor()
    now = int(time.time())
    
    # Find the lock
    row = cursor.execute("""
        SELECT id, miner_id, amount_i64, lock_type, status, unlock_at
        FROM lock_ledger
        WHERE id = ?
    """, (lock_id,)).fetchone()
    
    if not row:
        return False, {"error": "Lock not found"}
    
    lid, miner_id, amount_i64, lock_type, status, unlock_at = row
    
    if status != "locked":
        return False, {
            "error": f"Lock already {status}",
            "hint": "Only locked entries can be released"
        }
    
    # Check if unlock time has passed (unless properly authorized admin override).
    # SECURITY FIX: string comparison "admin" was trivially bypassable by any caller.
    # Now requires the released_by to match a configured admin public key.
    authorized_admin_key = os.environ.get("RC_ADMIN_KEY", "")
    is_admin_authorized = bool(authorized_admin_key and released_by == authorized_admin_key)

    if now < unlock_at and not is_admin_authorized:
        return False, {
            "error": "Lock has not yet unlocked",
            "unlock_at": unlock_at,
            "seconds_remaining": unlock_at - now
        }
    
    try:
        # Credit the locked amount back to the miner's available balance.
        # This is the core fix: without this, locked funds are permanently lost.
        cursor.execute(
            "UPDATE balances SET amount_i64 = amount_i64 + ? WHERE miner_id = ?",
            (amount_i64, miner_id)
        )

        # Update lock status
        cursor.execute("""
            UPDATE lock_ledger
            SET status = 'released',
                unlocked_at = ?,
                released_by = ?,
                release_tx_hash = ?
            WHERE id = ?
        """, (now, released_by, release_tx_hash, lock_id))
        
        db_conn.commit()
        
        return True, {
            "ok": True,
            "lock_id": lock_id,
            "miner_id": miner_id,
            "amount_rtc": amount_i64 / LOCK_UNIT,
            "released_by": released_by,
            "release_tx_hash": release_tx_hash,
            "released_at": now
        }
        
    except sqlite3.Error as e:
        db_conn.rollback()
        return False, {
            "error": "Database error",
            "details": str(e)
        }


def forfeit_lock(
    db_conn: sqlite3.Connection,
    lock_id: int,
    reason: str,
    forfeited_by: str = "admin"
) -> Tuple[bool, Dict[str, Any]]:
    """
    Forfeit a lock (penalty/slashing).
    Assets are not returned to owner.
    
    Args:
        db_conn: Database connection
        lock_id: Lock ledger entry ID
        reason: Reason for forfeiture
        forfeited_by: Entity forfeiting the lock
    
    Returns:
        (success, result_dict)
    """
    cursor = db_conn.cursor()
    now = int(time.time())
    
    # Find the lock
    row = cursor.execute("""
        SELECT id, miner_id, amount_i64, status
        FROM lock_ledger
        WHERE id = ?
    """, (lock_id,)).fetchone()
    
    if not row:
        return False, {"error": "Lock not found"}
    
    lid, miner_id, amount_i64, status = row
    
    if status != "locked":
        return False, {
            "error": f"Lock already {status}",
            "hint": "Only locked entries can be forfeited"
        }
    
    try:
        # Update lock status
        cursor.execute("""
            UPDATE lock_ledger
            SET status = 'forfeited',
                unlocked_at = ?,
                released_by = ?
            WHERE id = ?
        """, (now, forfeited_by, lock_id))
        
        # Note: Forfeited assets remain in the protocol treasury
        # They are not credited back to the miner
        
        db_conn.commit()
        
        return True, {
            "ok": True,
            "lock_id": lock_id,
            "miner_id": miner_id,
            "amount_rtc": amount_i64 / LOCK_UNIT,
            "reason": reason,
            "forfeited_by": forfeited_by,
            "forfeited_at": now,
            "note": "Forfeited assets are retained by protocol"
        }
        
    except sqlite3.Error as e:
        db_conn.rollback()
        return False, {
            "error": "Database error",
            "details": str(e)
        }


def get_lock_by_id(
    db_conn: sqlite3.Connection,
    lock_id: int
) -> Optional[LockEntry]:
    """Get a single lock entry by ID."""
    cursor = db_conn.cursor()
    
    row = cursor.execute("""
        SELECT 
            id, bridge_transfer_id, miner_id, amount_i64, lock_type,
            locked_at, unlock_at, unlocked_at, status, created_at,
            released_by, release_tx_hash
        FROM lock_ledger
        WHERE id = ?
    """, (lock_id,)).fetchone()
    
    if not row:
        return None
    
    return LockEntry(
        id=row[0],
        bridge_transfer_id=row[1],
        miner_id=row[2],
        amount_i64=row[3],
        lock_type=row[4],
        locked_at=row[5],
        unlock_at=row[6],
        unlocked_at=row[7],
        status=row[8],
        created_at=row[9],
        released_by=row[10],
        release_tx_hash=row[11]
    )


def get_locks_by_miner(
    db_conn: sqlite3.Connection,
    miner_id: str,
    status_filter: Optional[str] = None,
    limit: int = 100
) -> List[LockEntry]:
    """Get all locks for a miner."""
    cursor = db_conn.cursor()
    
    query = """
        SELECT 
            id, bridge_transfer_id, miner_id, amount_i64, lock_type,
            locked_at, unlock_at, unlocked_at, status, created_at,
            released_by, release_tx_hash
        FROM lock_ledger
        WHERE miner_id = ?
    """
    params = [miner_id]
    
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    
    query += " ORDER BY id DESC LIMIT ?"
    params.append(min(limit, 500))
    
    rows = cursor.execute(query, params).fetchall()
    
    return [
        LockEntry(
            id=r[0],
            bridge_transfer_id=r[1],
            miner_id=r[2],
            amount_i64=r[3],
            lock_type=r[4],
            locked_at=r[5],
            unlock_at=r[6],
            unlocked_at=r[7],
            status=r[8],
            created_at=r[9],
            released_by=r[10],
            release_tx_hash=r[11]
        )
        for r in rows
    ]


def get_pending_unlocks(
    db_conn: sqlite3.Connection,
    before_timestamp: Optional[int] = None,
    limit: int = 100
) -> List[LockEntry]:
    """
    Get locks that are ready to be unlocked.
    
    Args:
        db_conn: Database connection
        before_timestamp: Only return locks unlocking before this time
        limit: Maximum number of entries to return
    
    Returns:
        List of LockEntry objects
    """
    cursor = db_conn.cursor()
    now = int(time.time())
    
    query = """
        SELECT 
            id, bridge_transfer_id, miner_id, amount_i64, lock_type,
            locked_at, unlock_at, unlocked_at, status, created_at,
            released_by, release_tx_hash
        FROM lock_ledger
        WHERE status = 'locked'
          AND unlock_at <= ?
    """
    params = [now]
    
    if before_timestamp:
        query += " AND unlock_at <= ?"
        params.append(before_timestamp)
    
    query += " ORDER BY unlock_at ASC LIMIT ?"
    params.append(min(limit, 500))
    
    rows = cursor.execute(query, params).fetchall()
    
    return [
        LockEntry(
            id=r[0],
            bridge_transfer_id=r[1],
            miner_id=r[2],
            amount_i64=r[3],
            lock_type=r[4],
            locked_at=r[5],
            unlock_at=r[6],
            unlocked_at=r[7],
            status=r[8],
            created_at=r[9],
            released_by=r[10],
            release_tx_hash=r[11]
        )
        for r in rows
    ]


def get_miner_locked_balance(
    db_conn: sqlite3.Connection,
    miner_id: str
) -> Dict[str, Any]:
    """
    Get total locked balance for a miner.
    
    Returns:
        Dict with total_locked_rtc, breakdown by lock_type, etc.
    """
    cursor = db_conn.cursor()
    
    # Total locked
    total_row = cursor.execute("""
        SELECT COALESCE(SUM(amount_i64), 0), COUNT(*)
        FROM lock_ledger
        WHERE miner_id = ? AND status = 'locked'
    """, (miner_id,)).fetchone()
    
    total_locked = total_row[0] if total_row else 0
    total_count = total_row[1] if total_row else 0
    
    # Breakdown by type
    breakdown_rows = cursor.execute("""
        SELECT lock_type, SUM(amount_i64), COUNT(*)
        FROM lock_ledger
        WHERE miner_id = ? AND status = 'locked'
        GROUP BY lock_type
    """, (miner_id,)).fetchall()
    
    breakdown = {
        r[0]: {"amount_rtc": r[1] / LOCK_UNIT, "count": r[2]}
        for r in breakdown_rows
    }
    
    # Next unlock
    next_row = cursor.execute("""
        SELECT unlock_at, amount_i64
        FROM lock_ledger
        WHERE miner_id = ? AND status = 'locked'
        ORDER BY unlock_at ASC
        LIMIT 1
    """, (miner_id,)).fetchone()
    
    next_unlock = None
    if next_row:
        next_unlock = {
            "unlock_at": next_row[0],
            "amount_rtc": next_row[1] / LOCK_UNIT,
            "seconds_until": max(0, next_row[0] - int(time.time()))
        }
    
    return {
        "miner_id": miner_id,
        "total_locked_rtc": total_locked / LOCK_UNIT,
        "total_locked_count": total_count,
        "breakdown": breakdown,
        "next_unlock": next_unlock
    }


def auto_release_expired_locks(
    db_conn: sqlite3.Connection,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    Automatically release locks that have passed their unlock time.
    
    This should be called periodically by a background worker.
    
    Args:
        db_conn: Database connection
        batch_size: Maximum number of locks to release per call
    
    Returns:
        Dict with released_count, total_amount_rtc, errors
    """
    cursor = db_conn.cursor()
    now = int(time.time())
    
    # Get expired locks
    expired = get_pending_unlocks(db_conn, limit=batch_size)
    
    released_count = 0
    total_amount = 0
    errors = []
    
    for lock in expired:
        success, result = release_lock(
            db_conn,
            lock.id,
            released_by="auto_worker",
            release_tx_hash=None
        )
        
        if success:
            released_count += 1
            total_amount += lock.amount_i64
        else:
            errors.append({
                "lock_id": lock.id,
                "error": result.get("error", "Unknown error")
            })
    
    return {
        "released_count": released_count,
        "total_amount_rtc": total_amount / LOCK_UNIT,
        "errors": errors,
        "processed_at": now
    }


# =============================================================================
# Flask Routes (to be integrated into main node)
# =============================================================================

def register_lock_ledger_routes(app):
    """Register lock ledger API routes with Flask app."""
    from flask import request, jsonify
    
    @app.route('/api/lock/miner/<miner_id>', methods=['GET'])
    def get_miner_locks(miner_id: str):
        """Get locks for a specific miner."""
        status = request.args.get("status")
        limit = int(request.args.get("limit", 100))
        
        conn = sqlite3.connect(DB_PATH)
        try:
            if status == "summary":
                result = get_miner_locked_balance(conn, miner_id)
                return jsonify(result), 200
            
            locks = get_locks_by_miner(conn, miner_id, status_filter=status, limit=limit)
            
            return jsonify({
                "ok": True,
                "miner_id": miner_id,
                "count": len(locks),
                "locks": [
                    {
                        "id": l.id,
                        "amount_rtc": l.amount_rtc,
                        "lock_type": l.lock_type,
                        "status": l.status,
                        "locked_at": l.locked_at,
                        "unlock_at": l.unlock_at,
                        "time_until_unlock": l.time_until_unlock
                    }
                    for l in locks
                ]
            }), 200
        finally:
            conn.close()
    
    @app.route('/api/lock/<int:lock_id>', methods=['GET'])
    def get_lock(lock_id: int):
        """Get a specific lock by ID."""
        conn = sqlite3.connect(DB_PATH)
        try:
            lock = get_lock_by_id(conn, lock_id)
            if not lock:
                return jsonify({"error": "Lock not found"}), 404
            
            return jsonify({
                "ok": True,
                "lock": {
                    "id": lock.id,
                    "miner_id": lock.miner_id,
                    "amount_rtc": lock.amount_rtc,
                    "lock_type": lock.lock_type,
                    "status": lock.status,
                    "locked_at": lock.locked_at,
                    "unlock_at": lock.unlock_at,
                    "unlocked_at": lock.unlocked_at,
                    "released_by": lock.released_by,
                    "release_tx_hash": lock.release_tx_hash
                }
            }), 200
        finally:
            conn.close()
    
    @app.route('/api/lock/pending-unlock', methods=['GET'])
    def get_pending_unlocks():
        """Get locks ready to be released."""
        before = request.args.get("before")
        limit = int(request.args.get("limit", 100))
        
        before_ts = int(before) if before else None
        
        conn = sqlite3.connect(DB_PATH)
        try:
            locks = get_pending_unlocks(conn, before_timestamp=before_ts, limit=limit)
            
            return jsonify({
                "ok": True,
                "count": len(locks),
                "locks": [
                    {
                        "id": l.id,
                        "miner_id": l.miner_id,
                        "amount_rtc": l.amount_rtc,
                        "lock_type": l.lock_type,
                        "unlock_at": l.unlock_at,
                        "expired_seconds": max(0, int(time.time()) - l.unlock_at)
                    }
                    for l in locks
                ]
            }), 200
        finally:
            conn.close()
    
    @app.route('/api/lock/release', methods=['POST'])
    def release_lock_endpoint():
        """Admin: Release a lock."""
        admin_key = request.headers.get("X-Admin-Key", "")
        expected_key = os.environ.get("RC_ADMIN_KEY", "")
        if not expected_key:
            return jsonify({"error": "RC_ADMIN_KEY not configured — admin endpoints disabled"}), 503
        if not hmac.compare_digest(admin_key, expected_key):
            return jsonify({"error": "Unauthorized - admin key required"}), 401
        
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        lock_id = data.get("lock_id")
        release_tx_hash = data.get("release_tx_hash")
        
        if not lock_id:
            return jsonify({"error": "lock_id required"}), 400
        
        conn = sqlite3.connect(DB_PATH)
        try:
            success, result = release_lock(
                conn, lock_id, 
                released_by=os.environ.get("RC_ADMIN_KEY", "admin"),
                release_tx_hash=release_tx_hash
            )
            if success:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
        finally:
            conn.close()
    
    @app.route('/api/lock/forfeit', methods=['POST'])
    def forfeit_lock_endpoint():
        """Admin: Forfeit a lock (penalty)."""
        admin_key = request.headers.get("X-Admin-Key", "")
        expected_key = os.environ.get("RC_ADMIN_KEY", "")
        if not expected_key:
            return jsonify({"error": "RC_ADMIN_KEY not configured — admin endpoints disabled"}), 503
        if not hmac.compare_digest(admin_key, expected_key):
            return jsonify({"error": "Unauthorized - admin key required"}), 401
        
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        lock_id = data.get("lock_id")
        reason = data.get("reason", "admin_forfeit")
        
        if not lock_id:
            return jsonify({"error": "lock_id required"}), 400
        
        conn = sqlite3.connect(DB_PATH)
        try:
            success, result = forfeit_lock(
                conn, lock_id,
                reason=reason,
                forfeited_by="admin"
            )
            if success:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
        finally:
            conn.close()
    
    @app.route('/api/lock/auto-release', methods=['POST'])
    def auto_release_endpoint():
        """Worker: Auto-release expired locks."""
        # Require worker key authentication
        worker_key = request.headers.get("X-Worker-Key", "")
        expected_worker = os.environ.get("RC_WORKER_KEY", "")
        if not expected_worker:
            return jsonify({"error": "RC_WORKER_KEY not configured — worker endpoints disabled"}), 503
        if not hmac.compare_digest(worker_key, expected_worker):
            return jsonify({"error": "Unauthorized"}), 401
        batch_size = int(request.args.get("batch_size", 100))
        
        conn = sqlite3.connect(DB_PATH)
        try:
            result = auto_release_expired_locks(conn, batch_size=batch_size)
            return jsonify(result), 200
        finally:
            conn.close()


# =============================================================================
# Database Initialization
# =============================================================================

def init_lock_ledger_schema(cursor_or_db_path=None):
    """Initialize lock_ledger table schema.
    
    Args:
        cursor_or_db_path: Either a SQLite cursor object (for integration with main node)
                          or a database path string (for standalone usage)
    """
    # Support both cursor (from main node init_db) and db_path (standalone)
    if hasattr(cursor_or_db_path, 'execute'):
        # It's a cursor
        cursor = cursor_or_db_path
        conn = None
    else:
        # It's a db_path or None (use default)
        db_path = cursor_or_db_path if cursor_or_db_path else DB_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lock_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Reference to bridge transfer
            bridge_transfer_id INTEGER,

            -- Lock metadata
            miner_id TEXT NOT NULL,
            amount_i64 INTEGER NOT NULL CHECK (amount_i64 > 0),
            lock_type TEXT NOT NULL CHECK (lock_type IN (
                'bridge_deposit',
                'bridge_withdraw',
                'epoch_settlement',
                'admin_hold'
            )),

            -- Timing
            locked_at INTEGER NOT NULL,
            unlock_at INTEGER NOT NULL,
            unlocked_at INTEGER,

            -- State
            status TEXT NOT NULL DEFAULT 'locked'
                CHECK (status IN ('locked', 'released', 'forfeited')),

            -- Audit
            created_at INTEGER NOT NULL,
            released_by TEXT,
            release_tx_hash TEXT,

            FOREIGN KEY (bridge_transfer_id) REFERENCES bridge_transfers(id)
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lock_miner ON lock_ledger(miner_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lock_status ON lock_ledger(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lock_unlock_at ON lock_ledger(unlock_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lock_bridge ON lock_ledger(bridge_transfer_id)")

    if conn:
        conn.commit()
        conn.close()
