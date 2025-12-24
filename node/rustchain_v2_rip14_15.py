#!/usr/bin/env python3
"""
RustChain v2 - RIP-0010 Enhanced
Includes Canonical Header Store + Fast Sync APIs
"""
import os, time, json, secrets, hashlib, sqlite3, base64, struct, yaml
from flask import Flask, request, jsonify
from datetime import datetime
from typing import Dict, Optional, Tuple, List
try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    # Mock metrics for environments without prometheus_client
    class MockMetric:
        def inc(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    Counter = Gauge = Histogram = lambda *args, **kwargs: MockMetric()
    generate_latest = lambda: b""
    PROMETHEUS_AVAILABLE = False

from blake3 import blake3

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
KEEP_SLOTS = 2880  # Keep ~20 days of headers

# Global state
LAST_HASH_B3 = "00" * 32
LAST_EPOCH = None
STATE_ROOT_B3 = "00" * 32

# Prometheus metrics
withdrawal_requests = Counter('rustchain_withdrawal_requests', 'Total withdrawal requests')
withdrawal_completed = Counter('rustchain_withdrawal_completed', 'Completed withdrawals')
withdrawal_failed = Counter('rustchain_withdrawal_failed', 'Failed withdrawals')
balance_gauge = Gauge('rustchain_miner_balance', 'Miner balance', ['miner_pk'])
epoch_gauge = Gauge('rustchain_current_epoch', 'Current epoch')
withdrawal_queue_size = Gauge('rustchain_withdrawal_queue', 'Pending withdrawals')
header_count = Gauge('rustchain_header_count', 'Total headers stored')
header_tip = Gauge('rustchain_header_tip_slot', 'Latest header slot')

# Config loading for auth
try:
    with open("./config/chain.yaml", "r") as f:
        CHAIN_CONFIG = yaml.safe_load(f)
except FileNotFoundError:
    CHAIN_CONFIG = {}

AUTH_CFG = CHAIN_CONFIG.get("auth", {}) or {}

# Database setup
DB_PATH = "./rustchain_v2.db"

def init_db():
    """Initialize all database tables including headers"""
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

        # RIP-0010: Headers table for canonical chain
        c.execute("""
            CREATE TABLE IF NOT EXISTS headers (
                slot INTEGER PRIMARY KEY,
                hash_b3 TEXT NOT NULL,
                prev_hash_b3 TEXT NOT NULL,
                state_root_b3 TEXT NOT NULL,
                header_json TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_headers_hash ON headers(hash_b3)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_headers_prev ON headers(prev_hash_b3)")

        # RIP-0014: Merkle withdrawal roots cache
        c.execute("CREATE TABLE IF NOT EXISTS withdraw_merkle_roots (day TEXT PRIMARY KEY, root_hex TEXT, leaf_count INTEGER)")

# Header storage functions
def headers_put(slot: int, hash_b3: str, prev_hash_b3: str, state_root_b3: str, header_json: str):
    """Store a header in the canonical chain"""
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            INSERT OR REPLACE INTO headers(slot, hash_b3, prev_hash_b3, state_root_b3, header_json)
            VALUES (?, ?, ?, ?, ?)
        """, (int(slot), str(hash_b3), str(prev_hash_b3), str(state_root_b3), str(header_json)))

        # Update metrics
        count = c.execute("SELECT COUNT(*) FROM headers").fetchone()[0]
        header_count.set(count)
        header_tip.set(slot)

def headers_tip() -> Optional[Dict]:
    """Get the latest header"""
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute("""
            SELECT slot, hash_b3, state_root_b3, header_json
            FROM headers
            ORDER BY slot DESC
            LIMIT 1
        """).fetchone()

        if not row:
            return None

        return {
            "slot": int(row[0]),
            "hash_b3": row[1],
            "state_root_b3": row[2],
            "header": json.loads(row[3])
        }

def headers_range(from_slot: int, count: int) -> List[Dict]:
    """Get a range of headers starting from a slot"""
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute("""
            SELECT slot, hash_b3, prev_hash_b3, state_root_b3, header_json
            FROM headers
            WHERE slot >= ?
            ORDER BY slot ASC
            LIMIT ?
        """, (int(from_slot), int(count))).fetchall()

        return [{
            "slot": int(r[0]),
            "hash_b3": r[1],
            "prev_hash_b3": r[2],
            "state_root_b3": r[3],
            "header": json.loads(r[4])
        } for r in rows]

def headers_since(slot_exclusive: int, limit: int) -> List[Dict]:
    """Get headers after a specific slot"""
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute("""
            SELECT slot, hash_b3, prev_hash_b3, state_root_b3, header_json
            FROM headers
            WHERE slot > ?
            ORDER BY slot ASC
            LIMIT ?
        """, (int(slot_exclusive), int(limit))).fetchall()

        return [{
            "slot": int(r[0]),
            "hash_b3": r[1],
            "prev_hash_b3": r[2],
            "state_root_b3": r[3],
            "header": json.loads(r[4])
        } for r in rows]

def headers_by_hash(h: str) -> Optional[Dict]:
    """Get a header by its hash"""
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute("""
            SELECT slot, hash_b3, prev_hash_b3, state_root_b3, header_json
            FROM headers
            WHERE hash_b3 = ?
            LIMIT 1
        """, (h.lower(),)).fetchone()

        if not row:
            return None

        return {
            "slot": int(row[0]),
            "hash_b3": row[1],
            "prev_hash_b3": row[2],
            "state_root_b3": row[3],
            "header": json.loads(row[4])
        }

def headers_prune(keep_slots: int) -> int:
    """Prune old headers, keeping only the latest N slots"""
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute("SELECT MAX(slot) FROM headers").fetchone()
        if not row or row[0] is None:
            return 0

        tip = int(row[0])
        floor = max(0, tip - int(keep_slots))

        c.execute("DELETE FROM headers WHERE slot < ?", (floor,))
        deleted = c.rowcount

        # Update metrics
        count = c.execute("SELECT COUNT(*) FROM headers").fetchone()[0]
        header_count.set(count)

        return deleted

# RIP-0014: Merkle withdrawal receipt functions
def withdraws_for_day(day: str):
    """Get withdrawals for a specific day (YYYY-MM-DD)"""
    start = f"{day} 00:00:00"
    end = f"{day} 23:59:59"
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute("""SELECT withdrawal_id, miner_pk, destination, amount, created_at
                           FROM withdrawals
                           WHERE status IN ('sent','completed') AND datetime(created_at,'unixepoch') BETWEEN ? AND ?
                           ORDER BY withdrawal_id ASC""", (start, end)).fetchall()
        return rows

def merkle_root_get(day: str):
    """Get cached Merkle root for a day"""
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute("SELECT root_hex, leaf_count FROM withdraw_merkle_roots WHERE day=?", (day,)).fetchone()
        if not row:
            return None
        return {"root_hex": row[0], "leaf_count": int(row[1])}

def merkle_root_put(day: str, root_hex: str, leaf_count: int):
    """Cache Merkle root for a day"""
    with sqlite3.connect(DB_PATH) as c:
        c.execute("INSERT OR REPLACE INTO withdraw_merkle_roots(day, root_hex, leaf_count) VALUES (?,?,?)",
                  (day, root_hex, int(leaf_count)))

# RIP-0015: API-key auth functions
def _consteq(a, b):
    """Constant-time string comparison"""
    if not isinstance(a, (bytes, bytearray)):
        a = str(a).encode()
    if not isinstance(b, (bytes, bytearray)):
        b = str(b).encode()
    if len(a) != len(b):
        return False
    r = 0
    for x, y in zip(a, b):
        r |= (x ^ y)
    return r == 0

def _authorized(roles):
    """Check if request has valid API key for required roles"""
    keys = AUTH_CFG.get("api_keys", []) or []
    presented = request.headers.get("X-API-Key", "")
    if not presented:
        return False
    for k in keys:
        if k.get("role") in roles:
            if _consteq(blake3(presented.encode()).hexdigest(), (k.get("key_hash") or "").lower()):
                return True
    return False

def require_role(*roles):
    """Decorator to require API key with specific role"""
    def deco(fn):
        def inner(*a, **kw):
            if not _authorized(roles):
                return jsonify({"ok": False, "reason": "unauthorized"}), 403
            return fn(*a, **kw)
        inner.__name__ = fn.__name__
        return inner
    return deco

# Merkle tree functions
def _leaf_hash(txid: str, miner: str, dest: str, amt: float, ts: int) -> bytes:
    """Create leaf hash for Merkle tree"""
    s = json.dumps({"txid": txid, "miner": miner, "dest": dest, "amount": float(amt), "ts": int(ts)},
                   separators=(',', ':')).encode()
    return blake3(s).digest()

def _merkle_tree(hashes):
    """Build Merkle tree from leaf hashes, returns root and levels"""
    if not hashes:
        z = blake3(b"").digest()
        return z, [[z]]
    level = list(hashes)
    levels = [level]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            a = level[i]
            b = level[i+1] if i+1 < len(level) else level[i]
            nxt.append(blake3(a + b).digest())
        level = nxt
        levels.append(level)
    return levels[-1][0], levels

def _mk_proof(levels, index):
    """Generate Merkle proof for leaf at index"""
    proof = []
    for lvl in levels[:-1]:
        sib = index ^ 1
        if sib >= len(lvl):
            sib = index  # duplicate last
        proof.append(lvl[sib].hex())
        index >>= 1
    return proof

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

def calculate_state_root() -> str:
    """Calculate current state root from balances"""
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute("""
            SELECT miner_pk, balance_rtc
            FROM balances
            ORDER BY miner_pk
        """).fetchall()

        if not rows:
            return "0" * 64

        # Simple merkle of balances
        leaves = []
        for pk, balance in rows:
            leaf = hashlib.sha256(f"{pk}:{balance:.8f}".encode()).hexdigest()
            leaves.append(leaf)

        while len(leaves) > 1:
            next_level = []
            for i in range(0, len(leaves), 2):
                if i + 1 < len(leaves):
                    combined = leaves[i] + leaves[i + 1]
                else:
                    combined = leaves[i] + leaves[i]
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
            leaves = next_level

        return leaves[0]

def epoch_snapshot():
    """Get current epoch state snapshot"""
    current_slot = int(time.time()) // BLOCK_TIME
    current_epoch = current_slot // EPOCH_SLOTS

    with sqlite3.connect(DB_PATH) as c:
        # Get epoch state
        row = c.execute("SELECT accepted_blocks, finalized FROM epoch_state WHERE epoch=?", (current_epoch,)).fetchone()
        accepted_blocks = row[0] if row else 0
        finalized = bool(row[1]) if row else False

        # Get enrolled miners count
        enrolled_count = c.execute("SELECT COUNT(*) FROM epoch_enroll WHERE epoch=?", (current_epoch,)).fetchone()[0]

    return {
        "slot": current_slot,
        "epoch": current_epoch,
        "accepted_blocks": accepted_blocks,
        "finalized": finalized,
        "enrolled_miners": enrolled_count
    }

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

# ============= BLOCK SUBMISSION =============

@app.route('/api/submit_block', methods=['POST'])
def api_submit_block():
    """Submit a new block and store header"""
    global LAST_HASH_B3, STATE_ROOT_B3

    try:
        data = request.get_json(force=True)
        header = data.get("header", {})
        header_ext = data.get("header_ext", {})

        # Calculate state root
        STATE_ROOT_B3 = calculate_state_root()

        # Include state root in header
        header_with_state = dict(header)
        header_with_state["state_root_b3"] = STATE_ROOT_B3
        header_with_state["prev_hash_b3"] = LAST_HASH_B3

        # Calculate block hash
        try:
            from blake3 import blake3
            payload = json.dumps({"header": header_with_state, "header_ext": header_ext}, sort_keys=True).encode()
            LAST_HASH_B3 = blake3(payload).hexdigest()
        except ImportError:
            # Fallback to SHA256
            payload = json.dumps({"header": header_with_state, "header_ext": header_ext}, sort_keys=True).encode()
            LAST_HASH_B3 = hashlib.sha256(payload).hexdigest()

        # Store header in canonical chain
        slot = header_with_state.get("slot", current_slot())
        headers_put(
            slot,
            LAST_HASH_B3,
            header_with_state.get("prev_hash_b3", ""),
            STATE_ROOT_B3,
            json.dumps(header_with_state, separators=(',', ':'))
        )

        return jsonify({
            "ok": True,
            "new_hash_b3": LAST_HASH_B3,
            "state_root_b3": STATE_ROOT_B3,
            "reward_rtc": PER_BLOCK_RTC,
            "slot": slot
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============= HEADER APIs (RIP-0010) =============

@app.route('/headers/tip', methods=['GET'])
def api_headers_tip():
    """Get the latest header"""
    tip = headers_tip()

    if not tip:
        return jsonify({"ok": True, "empty": True})

    return jsonify({
        "ok": True,
        "tip": tip,
        "finalized_epoch": slot_to_epoch(tip["slot"]),
        "chain_id": CHAIN_ID
    })

@app.route('/headers/range', methods=['GET'])
def api_headers_range():
    """Get a range of headers"""
    try:
        start = int(request.args.get("from_slot", "0"))
        count = int(request.args.get("count", "256"))
    except Exception:
        return jsonify({"ok": False, "reason": "bad_params"}), 400

    return jsonify({
        "ok": True,
        "items": headers_range(start, min(count, 2048))
    })

@app.route('/headers/since/<int:slot>', methods=['GET'])
def api_headers_since(slot: int):
    """Get headers after a specific slot"""
    limit = int(request.args.get("limit", "512"))

    return jsonify({
        "ok": True,
        "items": headers_since(slot, min(limit, 4096))
    })

@app.route('/headers/by_hash/<h>', methods=['GET'])
def api_headers_by_hash(h: str):
    """Get header by hash"""
    result = headers_by_hash(h.lower())

    if not result:
        return jsonify({"ok": False, "reason": "not_found"}), 404

    return jsonify({
        "ok": True,
        "item": result
    })

@app.route('/headers/prune', methods=['POST'])
@require_role("admin")
def api_headers_prune():
    """Prune old headers keeping N latest slots"""
    try:
        data = request.get_json(silent=True) or {}
        keep = int(data.get("keep_slots", KEEP_SLOTS))

        deleted = headers_prune(keep)

        return jsonify({
            "ok": True,
            "deleted": deleted,
            "kept_slots": keep
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Admin: finalize epoch
@app.route('/epoch/finalize_admin', methods=['POST'])
@require_role("admin")
def api_epoch_finalize_admin():
    """Manual epoch finalization"""
    try:
        snap = epoch_snapshot()
        result = finalize_epoch(snap.get("epoch", 0), PER_BLOCK_RTC)
        return jsonify({"ok": True, "epoch": snap.get("epoch", 0), "result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Merkle: withdrawal receipts and proofs
@app.route('/withdraw/merkle/<day>', methods=['GET'])
def api_withdraw_merkle_day(day):
    """Get Merkle root for withdrawals on a specific day (YYYY-MM-DD)"""
    try:
        r = merkle_root_get(day)
        if r:
            return jsonify({"ok": True, "day": day, "root_hex": r["root_hex"], "leaf_count": r["leaf_count"]})

        # Compute on demand
        rows = withdraws_for_day(day)
        leafs = [_leaf_hash(tx, m, d, a, ts) for (tx, m, d, a, ts) in rows]
        root, _ = _merkle_tree(leafs)
        merkle_root_put(day, root.hex(), len(leafs))
        return jsonify({"ok": True, "day": day, "root_hex": root.hex(), "leaf_count": len(leafs)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/withdraw/receipt/<withdrawal_id>', methods=['GET'])
def api_withdraw_receipt(withdrawal_id):
    """Get Merkle proof for a specific withdrawal"""
    try:
        with sqlite3.connect(DB_PATH) as c:
            row = c.execute("""SELECT withdrawal_id, miner_pk, destination, amount, created_at,
                                     datetime(created_at,'unixepoch','localtime')
                               FROM withdrawals
                               WHERE withdrawal_id=? AND status IN ('sent','completed')""",
                            (withdrawal_id,)).fetchone()

        if not row:
            return jsonify({"ok": False, "reason": "not_found_or_not_sent"}), 404

        tx, miner, dest, amt, ts, local = row
        day = local.split(' ')[0]
        rows = withdraws_for_day(day)
        leafs = [_leaf_hash(t, m, d, a, u) for (t, m, d, a, u) in rows]

        # Find position in that day's list
        try:
            idx = [t for (t, _, _, _, _) in rows].index(tx)
        except ValueError:
            return jsonify({"ok": False, "reason": "not_found_in_day"}), 404

        root, levels = _merkle_tree(leafs)
        proof = _mk_proof(levels, idx)

        return jsonify({
            "ok": True,
            "withdrawal_id": tx,
            "day": day,
            "leaf_hash": leafs[idx].hex(),
            "index": idx,
            "root_hex": root.hex(),
            "proof": proof,
            "algo": "blake3-merkle"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        total_headers = c.execute("SELECT COUNT(*) FROM headers").fetchone()[0]

        # Get tip slot
        tip_row = c.execute("SELECT MAX(slot) FROM headers").fetchone()
        tip_slot = tip_row[0] if tip_row and tip_row[0] else 0

    return jsonify({
        "version": "2.1.0-rip10",
        "chain_id": CHAIN_ID,
        "epoch": epoch,
        "block_time": BLOCK_TIME,
        "total_miners": total_miners,
        "total_balance": total_balance,
        "pending_withdrawals": pending_withdrawals,
        "total_headers": total_headers,
        "tip_slot": tip_slot,
        "features": ["RIP-0005", "RIP-0008", "RIP-0009", "RIP-0010"]
    })

@app.route('/api/last_hash', methods=['GET'])
def get_last_hash():
    """Get the last block hash"""
    return jsonify({
        "last_hash_b3": LAST_HASH_B3,
        "state_root_b3": STATE_ROOT_B3
    })

@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest()

# ============= HEALTH CHECK =============

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.execute("SELECT 1")

        return jsonify({
            "status": "healthy",
            "chain_id": CHAIN_ID,
            "features": ["RIP-0005", "RIP-0008", "RIP-0009", "RIP-0010"]
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

if __name__ == "__main__":
    init_db()
    print("RustChain v2 Enhanced with RIP-0010")
    print(f"Chain ID: {CHAIN_ID}")
    print(f"SR25519 Available: {SR25519_AVAILABLE}")
    print("Features: RIP-0005 (Epochs), RIP-0008 (Withdrawals), RIP-0009 (Finality), RIP-0010 (Headers)")
    print(f"Header pruning: Keep {KEEP_SLOTS} slots (~{KEEP_SLOTS * BLOCK_TIME / 86400:.1f} days)")
    print()
    app.run(host='0.0.0.0', port=8088, debug=False)