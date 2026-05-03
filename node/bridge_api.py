#!/usr/bin/env python3
"""
RIP-0305: Bridge API Module
===========================

Implements REST API endpoints for cross-chain bridge transfers.
Track C: Bridge API + Lock Ledger

Endpoints:
- POST /api/bridge/initiate - Initiate a bridge transfer
- GET  /api/bridge/status/<tx_hash> - Query bridge transfer status
- GET  /api/bridge/list - List bridge transfers with filters
- POST /api/bridge/void - Admin: Void a bridge transfer
- POST /api/bridge/update-external - Update external tx confirmation data
"""

import sqlite3
import time
import hmac
import hashlib
import os
from typing import Optional, Tuple, Dict, Any
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

# Import from main node module
try:
    from rustchain_v2_integrated_v2_2_1_rip200 import (
        DB_PATH, 
        current_slot, 
        slot_to_epoch,
        validate_miner_id_format
    )
except ImportError:
    # Fallback for standalone testing
    DB_PATH = os.environ.get("RC_DB_PATH", "rustchain.db")
    def current_slot() -> int:
        return int(time.time()) // 600
    def slot_to_epoch(slot: int) -> int:
        return slot // 144
    def validate_miner_id_format(miner_id: str) -> Tuple[bool, str]:
        if not miner_id or len(miner_id) < 3:
            return False, "Miner ID must be at least 3 characters"
        if not miner_id.startswith("RTC"):
            return False, "Miner ID must start with 'RTC'"
        return True, ""


# =============================================================================
# Configuration
# =============================================================================

BRIDGE_DEFAULT_CONFIRMATIONS = int(os.environ.get("RC_BRIDGE_DEFAULT_CONFIRMATIONS", "12"))
BRIDGE_LOCK_EXPIRY_SECONDS = int(os.environ.get("RC_BRIDGE_LOCK_EXPIRY_SECONDS", "604800"))  # 7 days
BRIDGE_MIN_AMOUNT_RTC = float(os.environ.get("RC_BRIDGE_MIN_AMOUNT_RTC", "1.0"))
BRIDGE_UNIT = 1000000  # Micro-units per RTC


# =============================================================================
# Enums and Data Classes
# =============================================================================

class BridgeDirection(Enum):
    DEPOSIT = "deposit"      # RustChain -> External
    WITHDRAW = "withdraw"    # External -> RustChain


class BridgeStatus(Enum):
    PENDING = "pending"
    LOCKED = "locked"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    FAILED = "failed"
    VOIDED = "voided"


class LockType(Enum):
    BRIDGE_DEPOSIT = "bridge_deposit"
    BRIDGE_WITHDRAW = "bridge_withdraw"
    EPOCH_SETTLEMENT = "epoch_settlement"


class LockStatus(Enum):
    LOCKED = "locked"
    RELEASED = "released"
    FORFEITED = "forfeited"


@dataclass
class BridgeTransferRequest:
    direction: str
    source_chain: str
    dest_chain: str
    source_address: str
    dest_address: str
    amount_rtc: float
    memo: Optional[str] = None
    bridge_type: str = "bottube"


@dataclass
class ValidationResult:
    ok: bool
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# =============================================================================
# Validation Functions
# =============================================================================

VALID_CHAINS = {"rustchain", "solana", "ergo", "base", "ethereum"}
VALID_BRIDGE_TYPES = {"bottube", "internal", "custom"}


def validate_bridge_request(data: Optional[Dict]) -> ValidationResult:
    """Validate bridge transfer request payload."""
    if not data:
        return ValidationResult(ok=False, error="Request body is required")
    
    # Required fields
    required = ["direction", "source_chain", "dest_chain", "source_address", "dest_address", "amount_rtc"]
    for field in required:
        if field not in data:
            return ValidationResult(ok=False, error=f"Missing required field: {field}")
    
    # Validate direction
    direction = data.get("direction")
    if direction not in ["deposit", "withdraw"]:
        return ValidationResult(ok=False, error=f"Invalid direction: {direction}. Must be 'deposit' or 'withdraw'")
    
    # Validate chains
    source_chain = data.get("source_chain", "").lower()
    dest_chain = data.get("dest_chain", "").lower()
    
    if source_chain not in VALID_CHAINS:
        return ValidationResult(ok=False, error=f"Invalid source_chain: {source_chain}")
    if dest_chain not in VALID_CHAINS:
        return ValidationResult(ok=False, error=f"Invalid dest_chain: {dest_chain}")
    if source_chain == dest_chain:
        return ValidationResult(ok=False, error="Source and destination chains must be different")
    
    # Validate addresses
    source_address = data.get("source_address", "")
    dest_address = data.get("dest_address", "")
    
    if not source_address or len(source_address) < 10:
        return ValidationResult(ok=False, error="Invalid source_address (too short)")
    if not dest_address or len(dest_address) < 10:
        return ValidationResult(ok=False, error="Invalid dest_address (too short)")
    
    # Validate amount
    try:
        amount_rtc = float(data.get("amount_rtc", 0))
    except (TypeError, ValueError):
        return ValidationResult(ok=False, error="amount_rtc must be a number")
    
    if amount_rtc <= 0:
        return ValidationResult(ok=False, error="amount_rtc must be positive")
    if amount_rtc < BRIDGE_MIN_AMOUNT_RTC:
        return ValidationResult(ok=False, error=f"amount_rtc must be >= {BRIDGE_MIN_AMOUNT_RTC} RTC")
    
    # Validate bridge type (optional)
    bridge_type = data.get("bridge_type", "bottube")
    if bridge_type not in VALID_BRIDGE_TYPES:
        return ValidationResult(ok=False, error=f"Invalid bridge_type: {bridge_type}")
    
    # Validate memo (optional)
    memo = data.get("memo")
    if memo and len(memo) > 256:
        return ValidationResult(ok=False, error="Memo must be <= 256 characters")
    
    return ValidationResult(
        ok=True,
        details={
            "direction": direction,
            "source_chain": source_chain,
            "dest_chain": dest_chain,
            "source_address": source_address,
            "dest_address": dest_address,
            "amount_rtc": amount_rtc,
            "memo": memo,
            "bridge_type": bridge_type
        }
    )


def validate_chain_address_format(chain: str, address: str) -> Tuple[bool, str]:
    """Validate address format for specific chain."""
    if not address:
        return False, "Address is required"
    
    if chain == "rustchain":
        if not address.startswith("RTC"):
            return False, "RustChain addresses must start with 'RTC'"
        if len(address) < 10:
            return False, "RustChain address too short"
    
    elif chain == "solana":
        # Solana addresses are base58, 32-44 chars
        if len(address) < 32 or len(address) > 44:
            return False, "Invalid Solana address length"
    
    elif chain == "ergo":
        # Ergo addresses start with '9' or '3'
        if not address.startswith(("9", "3")):
            return False, "Invalid Ergo address format"
        if len(address) < 30:
            return False, "Ergo address too short"
    
    elif chain == "base":
        # Base (Ethereum L2) addresses are 0x-prefixed
        if not address.startswith("0x"):
            return False, "Base addresses must start with '0x'"
        if len(address) != 42:
            return False, "Invalid Base address length"
    
    return True, ""


# =============================================================================
# Bridge Transfer Functions
# =============================================================================

def generate_bridge_tx_hash(
    direction: str,
    source_chain: str,
    dest_chain: str,
    source_address: str,
    dest_address: str,
    amount_i64: int
) -> str:
    """Generate unique transaction hash for bridge transfer."""
    data = f"{direction}:{source_chain}:{dest_chain}:{source_address}:{dest_address}:{amount_i64}:{time.time()}:{os.urandom(8).hex()}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def check_miner_balance(db_conn: sqlite3.Connection, miner_id: str, amount_i64: int) -> Tuple[bool, int, int]:
    """
    Check if miner has sufficient available balance.
    Returns: (has_balance, available_balance, pending_debits)
    """
    cursor = db_conn.cursor()
    
    # Get total balance
    row = cursor.execute(
        "SELECT amount_i64 FROM balances WHERE miner_id = ?", 
        (miner_id,)
    ).fetchone()
    total_balance = row[0] if row else 0
    
    # Get pending bridge debits (locked but not yet confirmed/voided)
    pending_row = cursor.execute("""
        SELECT COALESCE(SUM(amount_i64), 0) 
        FROM bridge_transfers 
        WHERE source_address = ? 
          AND direction = 'deposit'
          AND status IN ('pending', 'locked', 'confirming')
    """, (miner_id,)).fetchone()
    pending_debits = pending_row[0] if pending_row else 0
    
    available = total_balance - pending_debits
    
    return available >= amount_i64, available, pending_debits


def create_bridge_transfer(
    db_conn: sqlite3.Connection,
    request: BridgeTransferRequest,
    admin_initiated: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """
    Create a new bridge transfer entry.
    
    Returns: (success, result_dict)
    """
    cursor = db_conn.cursor()
    now = int(time.time())
    current_epoch = slot_to_epoch(current_slot())
    
    amount_i64 = int(Decimal(str(request.amount_rtc)) * BRIDGE_UNIT)
    tx_hash = generate_bridge_tx_hash(
        request.direction,
        request.source_chain,
        request.dest_chain,
        request.source_address,
        request.dest_address,
        amount_i64
    )
    
    # Calculate unlock time based on direction
    if request.direction == "deposit":
        # Deposit: lock until external confirmations
        unlock_at = now + BRIDGE_LOCK_EXPIRY_SECONDS
    else:
        # Withdraw: shorter lock (RustChain confirmation)
        unlock_at = now + (6 * 600)  # 6 slots = 1 hour
    
    try:
        # For deposits, check balance and create lock
        if request.direction == "deposit" and not admin_initiated:
            has_balance, available, pending = check_miner_balance(
                db_conn, 
                request.source_address, 
                amount_i64
            )
            if not has_balance:
                return False, {
                    "error": "Insufficient available balance",
                    "available_rtc": available / BRIDGE_UNIT,
                    "pending_debits_rtc": pending / BRIDGE_UNIT,
                    "requested_rtc": request.amount_rtc
                }
        
        # Insert bridge transfer
        cursor.execute("""
            INSERT INTO bridge_transfers (
                direction, source_chain, dest_chain,
                source_address, dest_address,
                amount_i64, amount_rtc,
                bridge_type, bridge_fee_i64,
                status, lock_epoch,
                created_at, updated_at, expires_at,
                tx_hash, memo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.direction,
            request.source_chain,
            request.dest_chain,
            request.source_address,
            request.dest_address,
            amount_i64,
            request.amount_rtc,
            request.bridge_type,
            0,  # bridge_fee_i64
            "pending",
            current_epoch,
            now,
            now,
            unlock_at,
            tx_hash,
            request.memo
        ))
        
        bridge_id = cursor.lastrowid
        
        # Create lock ledger entry for deposits
        if request.direction == "deposit":
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bridge_id,
                request.source_address,
                amount_i64,
                "bridge_deposit",
                now,
                unlock_at,
                "locked",
                now
            ))
        
        db_conn.commit()
        
        return True, {
            "ok": True,
            "bridge_transfer_id": bridge_id,
            "tx_hash": tx_hash,
            "status": "pending",
            "lock_epoch": current_epoch,
            "unlock_at": unlock_at,
            "estimated_completion": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(unlock_at)),
            "direction": request.direction,
            "source_chain": request.source_chain,
            "dest_chain": request.dest_chain,
            "amount_rtc": request.amount_rtc
        }
        
    except sqlite3.Error as e:
        db_conn.rollback()
        return False, {
            "error": "Database error",
            "details": str(e)
        }


def get_bridge_transfer_by_hash(
    db_conn: sqlite3.Connection,
    tx_hash: str
) -> Optional[Dict[str, Any]]:
    """Get bridge transfer details by transaction hash."""
    cursor = db_conn.cursor()
    
    row = cursor.execute("""
        SELECT 
            id, direction, source_chain, dest_chain,
            source_address, dest_address,
            amount_i64, amount_rtc,
            bridge_type, bridge_fee_i64,
            external_tx_hash, external_confirmations, required_confirmations,
            status, lock_epoch,
            created_at, updated_at, expires_at, completed_at,
            tx_hash, voided_by, voided_reason, failure_reason,
            memo
        FROM bridge_transfers
        WHERE tx_hash = ?
    """, (tx_hash,)).fetchone()
    
    if not row:
        return None
    
    return {
        "id": row[0],
        "direction": row[1],
        "source_chain": row[2],
        "dest_chain": row[3],
        "source_address": row[4],
        "dest_address": row[5],
        "amount_rtc": row[7],
        "bridge_type": row[8],
        "external_tx_hash": row[10],
        "external_confirmations": row[11],
        "required_confirmations": row[12],
        "status": row[13],
        "lock_epoch": row[14],
        "created_at": row[15],
        "updated_at": row[16],
        "expires_at": row[17],
        "completed_at": row[18],
        "tx_hash": row[19],
        "voided_by": row[20],
        "voided_reason": row[21],
        "failure_reason": row[22],
        "memo": row[23]
    }


def list_bridge_transfers(
    db_conn: sqlite3.Connection,
    status_filter: Optional[str] = None,
    source_address: Optional[str] = None,
    dest_address: Optional[str] = None,
    direction: Optional[str] = None,
    limit: int = 100
) -> list:
    """List bridge transfers with optional filters."""
    cursor = db_conn.cursor()
    
    # Build query with filters
    query = """
        SELECT 
            id, direction, source_chain, dest_chain,
            source_address, dest_address,
            amount_rtc, bridge_type,
            external_tx_hash, external_confirmations, required_confirmations,
            status, lock_epoch, created_at, tx_hash
        FROM bridge_transfers
        WHERE 1=1
    """
    params = []
    
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    
    if source_address:
        query += " AND source_address = ?"
        params.append(source_address)
    
    if dest_address:
        query += " AND dest_address = ?"
        params.append(dest_address)
    
    if direction:
        query += " AND direction = ?"
        params.append(direction)
    
    query += " ORDER BY id DESC LIMIT ?"
    params.append(min(limit, 500))
    
    rows = cursor.execute(query, params).fetchall()
    
    return [
        {
            "id": r[0],
            "direction": r[1],
            "source_chain": r[2],
            "dest_chain": r[3],
            "source_address": r[4],
            "dest_address": r[5],
            "amount_rtc": r[6],
            "bridge_type": r[7],
            "external_tx_hash": r[8],
            "external_confirmations": r[9],
            "required_confirmations": r[10],
            "status": r[11],
            "lock_epoch": r[12],
            "created_at": r[13],
            "tx_hash": r[14]
        }
        for r in rows
    ]


def void_bridge_transfer(
    db_conn: sqlite3.Connection,
    tx_hash: str,
    reason: str,
    voided_by: str
) -> Tuple[bool, Dict[str, Any]]:
    """Void a bridge transfer and release associated lock."""
    cursor = db_conn.cursor()
    
    # Find the transfer
    transfer = get_bridge_transfer_by_hash(db_conn, tx_hash)
    if not transfer:
        return False, {"error": "Bridge transfer not found"}
    
    if transfer["status"] not in ("pending", "locked", "confirming"):
        return False, {
            "error": f"Cannot void transfer with status '{transfer['status']}'",
            "hint": "Only pending/locked/confirming transfers can be voided"
        }
    
    now = int(time.time())
    
    try:
        # Update bridge transfer
        cursor.execute("""
            UPDATE bridge_transfers
            SET status = 'voided',
                voided_by = ?,
                voided_reason = ?,
                updated_at = ?
            WHERE tx_hash = ?
        """, (voided_by, reason, now, tx_hash))
        
        # Release associated lock
        cursor.execute("""
            UPDATE lock_ledger
            SET status = 'released',
                unlocked_at = ?,
                released_by = ?
            WHERE bridge_transfer_id = ?
              AND status = 'locked'
        """, (now, voided_by, transfer["id"]))
        
        db_conn.commit()
        
        return True, {
            "ok": True,
            "voided_id": transfer["id"],
            "tx_hash": tx_hash,
            "source_address": transfer["source_address"],
            "dest_address": transfer["dest_address"],
            "amount_rtc": transfer["amount_rtc"],
            "voided_by": voided_by,
            "reason": reason,
            "lock_released": True
        }
        
    except sqlite3.Error as e:
        db_conn.rollback()
        return False, {
            "error": "Database error",
            "details": str(e)
        }


def update_external_confirmation(
    db_conn: sqlite3.Connection,
    tx_hash: str,
    external_tx_hash: str,
    confirmations: int,
    required_confirmations: Optional[int] = None
) -> Tuple[bool, Dict[str, Any]]:
    """Update external transaction confirmation data."""
    cursor = db_conn.cursor()
    
    transfer = get_bridge_transfer_by_hash(db_conn, tx_hash)
    if not transfer:
        return False, {"error": "Bridge transfer not found"}
    
    if transfer["status"] in ("completed", "failed", "voided"):
        return False, {
            "error": f"Cannot update completed/failed/voided transfer",
            "current_status": transfer["status"]
        }
    
    now = int(time.time())
    req_conf = required_confirmations or transfer["required_confirmations"] or BRIDGE_DEFAULT_CONFIRMATIONS
    
    # Determine new status
    if confirmations >= req_conf:
        new_status = "completed"
        completed_at = now
    elif confirmations > 0:
        new_status = "confirming"
        completed_at = None
    else:
        new_status = "locked"
        completed_at = None
    
    try:
        cursor.execute("""
            UPDATE bridge_transfers
            SET external_tx_hash = ?,
                external_confirmations = ?,
                required_confirmations = ?,
                status = ?,
                completed_at = ?,
                updated_at = ?
            WHERE tx_hash = ?
        """, (external_tx_hash, confirmations, req_conf, new_status, completed_at, now, tx_hash))
        
        # If completed, release the lock
        if new_status == "completed":
            cursor.execute("""
                UPDATE lock_ledger
                SET status = 'released',
                    unlocked_at = ?,
                    release_tx_hash = ?
                WHERE bridge_transfer_id = ?
                  AND status = 'locked'
            """, (now, external_tx_hash, transfer["id"]))
        
        db_conn.commit()
        
        return True, {
            "ok": True,
            "tx_hash": tx_hash,
            "status": new_status,
            "external_confirmations": confirmations,
            "required_confirmations": req_conf
        }
        
    except sqlite3.Error as e:
        db_conn.rollback()
        return False, {
            "error": "Database error",
            "details": str(e)
        }


# =============================================================================
# Flask Routes (to be integrated into main node)
# =============================================================================

def register_bridge_routes(app):
    """Register bridge API routes with Flask app."""
    from flask import request, jsonify
    
    @app.route('/api/bridge/initiate', methods=['POST'])
    def initiate_bridge():
        """Initiate a new bridge transfer."""
        data = request.get_json(silent=True)
        
        # Validate request
        validation = validate_bridge_request(data)
        if not validation.ok:
            return jsonify({"error": validation.error}), 400
        
        # Validate address formats
        for chain, addr in [
            (data["source_chain"], data["source_address"]),
            (data["dest_chain"], data["dest_address"])
        ]:
            valid, msg = validate_chain_address_format(chain, addr)
            if not valid:
                return jsonify({"error": f"Invalid {chain} address: {msg}"}), 400
        
        # Check admin initiation (bypasses balance check)
        admin_key = request.headers.get("X-Admin-Key", "")
        admin_initiated = hmac.compare_digest(admin_key, os.environ.get("RC_ADMIN_KEY", ""))
        
        # Create bridge transfer
        req = BridgeTransferRequest(
            direction=data["direction"],
            source_chain=data["source_chain"],
            dest_chain=data["dest_chain"],
            source_address=data["source_address"],
            dest_address=data["dest_address"],
            amount_rtc=data["amount_rtc"],
            memo=data.get("memo"),
            bridge_type=data.get("bridge_type", "bottube")
        )
        
        conn = sqlite3.connect(DB_PATH)
        try:
            success, result = create_bridge_transfer(conn, req, admin_initiated)
            if success:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
        finally:
            conn.close()
    
    @app.route('/api/bridge/status/<tx_hash>', methods=['GET'])
    @app.route('/api/bridge/status', methods=['GET'])
    def get_bridge_status(tx_hash: Optional[str] = None):
        """Get bridge transfer status by tx_hash or id."""
        if not tx_hash:
            tx_hash = request.args.get("id") or request.args.get("tx_hash")
        
        if not tx_hash:
            return jsonify({"error": "tx_hash or id parameter required"}), 400
        
        conn = sqlite3.connect(DB_PATH)
        try:
            transfer = get_bridge_transfer_by_hash(conn, tx_hash)
            if not transfer:
                return jsonify({"error": "Bridge transfer not found"}), 404
            
            return jsonify({
                "ok": True,
                "transfer": transfer
            }), 200
        finally:
            conn.close()
    
    @app.route('/api/bridge/list', methods=['GET'])
    def list_bridges():
        """List bridge transfers with filters."""
        status = request.args.get("status")
        source = request.args.get("source_address")
        dest = request.args.get("dest_address")
        direction = request.args.get("direction")
        limit = int(request.args.get("limit", 100))
        
        conn = sqlite3.connect(DB_PATH)
        try:
            transfers = list_bridge_transfers(
                conn,
                status_filter=status,
                source_address=source,
                dest_address=dest,
                direction=direction,
                limit=limit
            )
            
            return jsonify({
                "ok": True,
                "count": len(transfers),
                "transfers": transfers
            }), 200
        finally:
            conn.close()
    
    @app.route('/api/bridge/void', methods=['POST'])
    def void_bridge():
        """Admin: Void a bridge transfer."""
        admin_key = request.headers.get("X-Admin-Key", "")
        if admin_key != os.environ.get("RC_ADMIN_KEY", ""):
            return jsonify({"error": "Unauthorized - admin key required"}), 401
        
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        tx_hash = data.get("tx_hash")
        reason = data.get("reason", "admin_void")
        voided_by = data.get("voided_by", "admin")
        
        if not tx_hash:
            return jsonify({"error": "tx_hash required"}), 400
        
        conn = sqlite3.connect(DB_PATH)
        try:
            success, result = void_bridge_transfer(conn, tx_hash, reason, voided_by)
            if success:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
        finally:
            conn.close()
    
    @app.route('/api/bridge/update-external', methods=['POST'])
    def update_external():
        """Update external confirmation data (for bridge service callbacks)."""
        # Optional: require API key for callbacks
        api_key = request.headers.get("X-API-Key", "")
        expected_key = os.environ.get("RC_BRIDGE_API_KEY", "")
        if expected_key and api_key != expected_key:
            return jsonify({"error": "Unauthorized"}), 401
        
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        tx_hash = data.get("tx_hash")
        external_tx_hash = data.get("external_tx_hash")
        confirmations = data.get("confirmations", 0)
        required_confirmations = data.get("required_confirmations")
        
        if not tx_hash or not external_tx_hash:
            return jsonify({"error": "tx_hash and external_tx_hash required"}), 400

        conn = sqlite3.connect(DB_PATH)
        try:
            success, result = update_external_confirmation(
                conn, tx_hash, external_tx_hash, confirmations, required_confirmations
            )
            if success:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
        finally:
            conn.close()


# =============================================================================
# Database Initialization
# =============================================================================

def init_bridge_schema(cursor):
    """Initialize bridge_transfers table schema.
    
    Args:
        cursor: SQLite cursor object
    """
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bridge_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Core transfer data
            direction TEXT NOT NULL CHECK (direction IN ('deposit', 'withdraw')),
            source_chain TEXT NOT NULL,
            dest_chain TEXT NOT NULL,
            source_address TEXT NOT NULL,
            dest_address TEXT NOT NULL,

            -- Amount (stored in micro-units for precision)
            amount_i64 INTEGER NOT NULL CHECK (amount_i64 > 0),
            amount_rtc REAL NOT NULL,

            -- Bridge metadata
            bridge_type TEXT NOT NULL DEFAULT 'bottube',
            bridge_fee_i64 INTEGER DEFAULT 0,
            external_tx_hash TEXT,
            external_confirmations INTEGER DEFAULT 0,
            required_confirmations INTEGER DEFAULT 12,

            -- State tracking
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'locked', 'confirming', 'completed', 'failed', 'voided')),
            lock_epoch INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            expires_at INTEGER,
            completed_at INTEGER,

            -- Audit fields
            tx_hash TEXT UNIQUE NOT NULL,
            voided_by TEXT,
            voided_reason TEXT,
            failure_reason TEXT,

            -- Optional memo
            memo TEXT
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_status ON bridge_transfers(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_source ON bridge_transfers(source_address)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_dest ON bridge_transfers(dest_address)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_lock_epoch ON bridge_transfers(lock_epoch)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_tx_hash ON bridge_transfers(tx_hash)")
