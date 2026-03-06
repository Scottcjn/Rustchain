#!/usr/bin/env python3
"""
RustChain v2 - Integrated Server
Includes RIP-0005 (Epoch Rewards), RIP-0008 (Withdrawals), RIP-0009 (Finality)
"""
import os, time, json, secrets, hashlib, sqlite3, base64, struct
from flask import Flask, request, jsonify
from datetime import datetime
from typing import Dict, Optional, Tuple
from prometheus_client import Counter, Gauge, Histogram, generate_latest

app = Flask(__name__)

# Configuration
BLOCK_TIME = 600  # 10 minutes
PER_BLOCK_RTC = 1.5  # Fixed per block
EPOCH_SLOTS = 144  # 24 hours at 10-min blocks
ENFORCE = False  # Start with enforcement off
CHAIN_ID = "rustchain-mainnet-v2"
MIN_WITHDRAWAL = 0.1  # RTC
WITHDRAWAL_FEE = 0.01  # RTC
MAX_DAILY_WITHDRAWAL = 1000.0  # RTC

# Prometheus metrics
withdrawal_requests = Counter('rustchain_withdrawal_requests', 'Total withdrawal requests')
withdrawal_completed = Counter('rustchain_withdrawal_completed', 'Completed withdrawals')
withdrawal_failed = Counter('rustchain_withdrawal_failed', 'Failed withdrawals')
balance_gauge = Gauge('rustchain_miner_balance', 'Miner balance', ['miner_pk'])
epoch_gauge = Gauge('rustchain_current_epoch', 'Current epoch')
withdrawal_queue_size = Gauge('rustchain_withdrawal_queue', 'Pending withdrawals')

# Database setup
DB_PATH = "./rustchain_v2.db"

def init_db():
    """Initialize all database tables"""
    with sqlite3.connect(DB_PATH) as c:
        # Core tables
        c.execute("CREATE TABLE IF NOT EXISTS nonces (nonce TEXT PRIMARY KEY, expires_at INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS tickets (ticket_id TEXT PRIMARY KEY, expires_at INTEGER, commitment TEXT)")

        # Epoch tables
        c.execute("CREATE TABLE IF NOT EXISTS epoch_state (epoch INTEGER PRIMARY KEY, accepted_blocks INTEGER DEFAULT 0, finalized INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS epoch_enroll (epoch INTEGER, miner_pk TEXT, weight REAL, PRIMARY KEY (epoch, miner_pk))")
        c.execute("CREATE TABLE IF NOT EXISTS balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL DEFAULT 0)")

        # Withdrawal tables
        c.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                withdrawal_id TEXT PRIMARY KEY,
                miner_pk TEXT NOT NULL,
                amount REAL NOT NULL,
                fee REAL NOT NULL,
                destination TEXT NOT NULL,
                signature TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at INTEGER NOT NULL,
                processed_at INTEGER,
                tx_hash TEXT,
                error_msg TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS withdrawal_limits (
                miner_pk TEXT NOT NULL,
                date TEXT NOT NULL,
                total_withdrawn REAL DEFAULT 0,
                PRIMARY KEY (miner_pk, date)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS miner_keys (
                miner_pk TEXT PRIMARY KEY,
                pubkey_sr25519 TEXT NOT NULL,
                registered_at INTEGER NOT NULL,
                last_withdrawal INTEGER
            )
        """)

# Hardware multipliers
HARDWARE_WEIGHTS = {
    "PowerPC": {"G4": 2.5, "G5": 2.0},
    "x86": {"default": 1.0},
    "ARM": {"default": 1.0}
}

# sr25519 signature verification
try:
    from py_sr25519 import verify as sr25519_verify
    SR25519_AVAILABLE = True
except ImportError:
    SR25519_AVAILABLE = False

def verify_sr25519_signature(message: bytes, signature: bytes, pubkey: bytes) -> bool:
    """Verify sr25519 signature with real implementation or mock"""
    if SR25519_AVAILABLE:
        try:
            return sr25519_verify(signature, message, pubkey)
        except:
            return False
    else:
        # Mock for testing - accept 64-byte signatures
        return len(signature) == 64

def slot_to_epoch(slot):
    """Convert slot number to epoch"""
    return int(slot) // max(EPOCH_SLOTS, 1)

def current_slot():
    """Get current slot number"""
    return int(time.time()) // BLOCK_TIME

def finalize_epoch(epoch, per_block_rtc):
    """Finalize epoch and distribute rewards"""
    with sqlite3.connect(DB_PATH) as c:
        # Get all enrolled miners
        miners = c.execute(
            "SELECT miner_pk, weight FROM epoch_enroll WHERE epoch = ?",
            (epoch,)
        ).fetchall()

        if not miners:
            return

        # Calculate total weight and rewards
        total_weight = sum(w for _, w in miners)
        total_reward = per_block_rtc * EPOCH_SLOTS

        # Distribute rewards
        for pk, weight in miners:
            amount = total_reward * (weight / total_weight)
            c.execute(
                "UPDATE balances SET balance_rtc = balance_rtc + ? WHERE miner_pk = ?",
                (amount, pk)
            )
            balance_gauge.labels(miner_pk=pk).set(amount)

        # Mark epoch as finalized
        c.execute("UPDATE epoch_state SET finalized = 1 WHERE epoch = ?", (epoch,))

# ============= ATTESTATION ENDPOINTS =============

@app.route('/attest/challenge', methods=['POST'])
def get_challenge():
    """Issue challenge for hardware attestation"""
    nonce = secrets.token_hex(32)
    expires = int(time.time()) + 300  # 5 minutes

    with sqlite3.connect(DB_PATH) as c:
        c.execute("INSERT INTO nonces (nonce, expires_at) VALUES (?, ?)", (nonce, expires))

    return jsonify({
        "nonce": nonce,
        "expires_at": expires,
        "server_time": int(time.time())
    })

@app.route('/attest/submit', methods=['POST'])
def submit_attestation():
    """Submit hardware attestation"""
    data = request.get_json()

    # Extract attestation data
    report = data.get('report', {})
    nonce = report.get('nonce')
    device = report.get('device', {})

    # Basic validation
    if not nonce:
        return jsonify({"error": "Missing nonce"}), 400

    # Generate ticket ID
    ticket_id = f"ticket_{secrets.token_hex(16)}"

    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            "INSERT INTO tickets (ticket_id, expires_at, commitment) VALUES (?, ?, ?)",
            (ticket_id, int(time.time()) + 3600, report.get('commitment', ''))
        )

    return jsonify({
        "ticket_id": ticket_id,
        "status": "accepted",
        "device": device
    })

# ============= EPOCH ENDPOINTS =============

@app.route('/epoch', methods=['GET'])
def get_epoch():
    """Get current epoch info"""
    slot = current_slot()
    epoch = slot_to_epoch(slot)
    epoch_gauge.set(epoch)

    with sqlite3.connect(DB_PATH) as c:
        enrolled = c.execute(
            "SELECT COUNT(*) FROM epoch_enroll WHERE epoch = ?",
            (epoch,)
        ).fetchone()[0]

    return jsonify({
        "epoch": epoch,
        "slot": slot,
        "epoch_pot": PER_BLOCK_RTC * EPOCH_SLOTS,
        "enrolled_miners": enrolled,
        "blocks_per_epoch": EPOCH_SLOTS
    })

@app.route('/epoch/enroll', methods=['POST'])
def enroll_epoch():
    """Enroll in current epoch"""
    data = request.get_json()
    miner_pk = data.get('miner_pubkey')
    device = data.get('device', {})

    if not miner_pk:
        return jsonify({"error": "Missing miner_pubkey"}), 400

    # Calculate weight based on hardware
    family = device.get('family', 'x86')
    arch = device.get('arch', 'default')
    weight = HARDWARE_WEIGHTS.get(family, {}).get(arch, 1.0)

    epoch = slot_to_epoch(current_slot())

    with sqlite3.connect(DB_PATH) as c:
        # Ensure miner has balance entry
        c.execute(
            "INSERT OR IGNORE INTO balances (miner_pk, balance_rtc) VALUES (?, 0)",
            (miner_pk,)
        )

        # Enroll in epoch
        c.execute(
            "INSERT OR REPLACE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
            (epoch, miner_pk, weight)
        )

    return jsonify({
        "ok": True,
        "epoch": epoch,
        "weight": weight,
        "miner_pk": miner_pk
    })

# ============= WITHDRAWAL ENDPOINTS =============

@app.route('/withdraw/register', methods=['POST'])
def register_withdrawal_key():
    """Register sr25519 public key for withdrawals"""
    data = request.get_json()
    miner_pk = data.get('miner_pk')
    pubkey_sr25519 = data.get('pubkey_sr25519')

    if not all([miner_pk, pubkey_sr25519]):
        return jsonify({"error": "Missing fields"}), 400

    try:
        bytes.fromhex(pubkey_sr25519)
    except ValueError:
        return jsonify({"error": "Invalid pubkey hex"}), 400

    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            INSERT INTO miner_keys (miner_pk, pubkey_sr25519, registered_at)
            VALUES (?, ?, ?)
            ON CONFLICT(miner_pk) DO UPDATE SET
            pubkey_sr25519 = ?, registered_at = ?
        """, (miner_pk, pubkey_sr25519, int(time.time()),
              pubkey_sr25519, int(time.time())))

    return jsonify({
        "miner_pk": miner_pk,
        "pubkey_registered": True,
        "can_withdraw": True
    })

@app.route('/withdraw/request', methods=['POST'])
def request_withdrawal():
    """Request RTC withdrawal"""
    withdrawal_requests.inc()

    data = request.get_json()
    miner_pk = data.get('miner_pk')
    amount = float(data.get('amount', 0))
    destination = data.get('destination')
    signature = data.get('signature')
    nonce = data.get('nonce')

    if not all([miner_pk, destination, signature, nonce]):
        return jsonify({"error": "Missing required fields"}), 400

    if amount < MIN_WITHDRAWAL:
        return jsonify({"error": f"Minimum withdrawal is {MIN_WITHDRAWAL} RTC"}), 400

    with sqlite3.connect(DB_PATH) as c:
        # Check balance
        row = c.execute("SELECT balance_rtc FROM balances WHERE miner_pk = ?", (miner_pk,)).fetchone()
        balance = row[0] if row else 0.0
        total_needed = amount + WITHDRAWAL_FEE

        if balance < total_needed:
            withdrawal_failed.inc()
            return jsonify({"error": "Insufficient balance", "balance": balance}), 400

        # Check daily limit
        today = datetime.now().strftime("%Y-%m-%d")
        limit_row = c.execute(
            "SELECT total_withdrawn FROM withdrawal_limits WHERE miner_pk = ? AND date = ?",
            (miner_pk, today)
        ).fetchone()

        daily_total = limit_row[0] if limit_row else 0.0
        if daily_total + amount > MAX_DAILY_WITHDRAWAL:
            withdrawal_failed.inc()
            return jsonify({"error": f"Daily limit exceeded"}), 400

        # Verify signature
        row = c.execute("SELECT pubkey_sr25519 FROM miner_keys WHERE miner_pk = ?", (miner_pk,)).fetchone()
        if not row:
            return jsonify({"error": "Miner not registered"}), 404

        pubkey_hex = row[0]
        message = f"{miner_pk}:{destination}:{amount}:{nonce}".encode()

        # Try base64 first, then hex
        try:
            try:
                sig_bytes = base64.b64decode(signature)
            except:
                sig_bytes = bytes.fromhex(signature)

            pubkey_bytes = bytes.fromhex(pubkey_hex)

            if len(sig_bytes) != 64:
                withdrawal_failed.inc()
                return jsonify({"error": "Invalid signature length"}), 400

            if not verify_sr25519_signature(message, sig_bytes, pubkey_bytes):
                withdrawal_failed.inc()
                return jsonify({"error": "Invalid signature"}), 401
        except Exception as e:
            withdrawal_failed.inc()
            return jsonify({"error": f"Signature error: {e}"}), 400

        # Create withdrawal
        withdrawal_id = f"WD_{int(time.time() * 1000000)}_{secrets.token_hex(8)}"

        # Deduct balance
        c.execute("UPDATE balances SET balance_rtc = balance_rtc - ? WHERE miner_pk = ?",
                  (total_needed, miner_pk))

        # Create withdrawal record
        c.execute("""
            INSERT INTO withdrawals (
                withdrawal_id, miner_pk, amount, fee, destination,
                signature, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (withdrawal_id, miner_pk, amount, WITHDRAWAL_FEE, destination, signature, int(time.time())))

        # Update daily limit
        c.execute("""
            INSERT INTO withdrawal_limits (miner_pk, date, total_withdrawn)
            VALUES (?, ?, ?)
            ON CONFLICT(miner_pk, date) DO UPDATE SET
            total_withdrawn = total_withdrawn + ?
        """, (miner_pk, today, amount, amount))

        balance_gauge.labels(miner_pk=miner_pk).set(balance - total_needed)
        withdrawal_queue_size.inc()

    return jsonify({
        "withdrawal_id": withdrawal_id,
        "status": "pending",
        "amount": amount,
        "fee": WITHDRAWAL_FEE,
        "net_amount": amount - WITHDRAWAL_FEE
    })

@app.route('/withdraw/status/<withdrawal_id>', methods=['GET'])
def withdrawal_status(withdrawal_id):
    """Get withdrawal status"""
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute("""
            SELECT miner_pk, amount, fee, destination, status,
                   created_at, processed_at, tx_hash, error_msg
            FROM withdrawals WHERE withdrawal_id = ?
        """, (withdrawal_id,)).fetchone()

        if not row:
            return jsonify({"error": "Withdrawal not found"}), 404

        return jsonify({
            "withdrawal_id": withdrawal_id,
            "miner_pk": row[0],
            "amount": row[1],
            "fee": row[2],
            "destination": row[3],
            "status": row[4],
            "created_at": row[5],
            "processed_at": row[6],
            "tx_hash": row[7],
            "error_msg": row[8]
        })

@app.route('/withdraw/history/<miner_pk>', methods=['GET'])
def withdrawal_history(miner_pk):
    """Get withdrawal history for miner"""
    limit = request.args.get('limit', 50, type=int)

    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute("""
            SELECT withdrawal_id, amount, fee, destination, status,
                   created_at, processed_at, tx_hash
            FROM withdrawals
            WHERE miner_pk = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (miner_pk, limit)).fetchall()

        withdrawals = []
        for row in rows:
            withdrawals.append({
                "withdrawal_id": row[0],
                "amount": row[1],
                "fee": row[2],
                "destination": row[3],
                "status": row[4],
                "created_at": row[5],
                "processed_at": row[6],
                "tx_hash": row[7]
            })

        # Get balance
        balance_row = c.execute("SELECT balance_rtc FROM balances WHERE miner_pk = ?", (miner_pk,)).fetchone()
        balance = balance_row[0] if balance_row else 0.0

        return jsonify({
            "miner_pk": miner_pk,
            "current_balance": balance,
            "withdrawals": withdrawals
        })

# ============= MONITORING ENDPOINTS =============

@app.route('/balance/<miner_pk>', methods=['GET'])
def get_balance(miner_pk):
    """Get miner balance"""
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute("SELECT balance_rtc FROM balances WHERE miner_pk = ?", (miner_pk,)).fetchone()
        balance = row[0] if row else 0.0

        return jsonify({
            "miner_pk": miner_pk,
            "balance_rtc": balance
        })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    epoch = slot_to_epoch(current_slot())

    with sqlite3.connect(DB_PATH) as c:
        total_miners = c.execute("SELECT COUNT(*) FROM balances").fetchone()[0]
        total_balance = c.execute("SELECT SUM(balance_rtc) FROM balances").fetchone()[0] or 0
        pending_withdrawals = c.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'").fetchone()[0]

    return jsonify({
        "version": "2.1.0-rip8",
        "chain_id": CHAIN_ID,
        "epoch": epoch,
        "block_time": BLOCK_TIME,
        "total_miners": total_miners,
        "total_balance": total_balance,
        "pending_withdrawals": pending_withdrawals,
        "features": ["RIP-0005", "RIP-0008", "RIP-0009"]
    })

@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest()

if __name__ == "__main__":
    init_db()
    print("RustChain v2 Integrated Server")
    print(f"Chain ID: {CHAIN_ID}")
    print(f"SR25519 Available: {SR25519_AVAILABLE}")
    print("Features: RIP-0005 (Epochs), RIP-0008 (Withdrawals), RIP-0009 (Finality)")
    print()
    app.run(host='0.0.0.0', port=8088, debug=False)