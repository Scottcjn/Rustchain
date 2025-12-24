#!/usr/bin/env python3
"""
RustChain v2 - RIP-0005 Epoch Pro-Rata Rewards
Production Anti-Spoof System with Fair Distribution
"""
import os, time, json, secrets, hashlib, sqlite3
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Configuration
BLOCK_TIME = 600  # 10 minutes
PER_BLOCK_RTC = 1.5  # Fixed per block
EPOCH_SLOTS = 144  # 24 hours at 10-min blocks
ENFORCE = False  # Start with enforcement off
LAST_HASH_B3 = "00" * 32
LAST_EPOCH = None

# Database setup
DB_PATH = "./rustchain_v2.db"

def init_db():
    """Initialize database with epoch tables"""
    with sqlite3.connect(DB_PATH) as c:
        # Existing tables
        c.execute("CREATE TABLE IF NOT EXISTS nonces (nonce TEXT PRIMARY KEY, expires_at INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS tickets (ticket_id TEXT PRIMARY KEY, expires_at INTEGER, commitment TEXT)")

        # New epoch tables
        c.execute("CREATE TABLE IF NOT EXISTS epoch_state (epoch INTEGER PRIMARY KEY, accepted_blocks INTEGER DEFAULT 0, finalized INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS epoch_enroll (epoch INTEGER, miner_pk TEXT, weight REAL, PRIMARY KEY (epoch, miner_pk))")
        c.execute("CREATE TABLE IF NOT EXISTS balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL DEFAULT 0)")

# Hardware multipliers
HARDWARE_WEIGHTS = {
    "PowerPC": {"G4": 2.5, "G5": 2.0},
    "x86": {"default": 1.0},
    "ARM": {"default": 1.0}
}

# In-memory storage
registered_nodes = {}
mining_pool = {}
blacklisted = set()
tickets_db = {}

def slot_to_epoch(slot):
    """Convert slot number to epoch"""
    return int(slot) // max(EPOCH_SLOTS, 1)

def inc_epoch_block(epoch):
    """Increment accepted blocks for epoch"""
    with sqlite3.connect(DB_PATH) as c:
        c.execute("INSERT OR IGNORE INTO epoch_state(epoch, accepted_blocks, finalized) VALUES (?,0,0)", (epoch,))
        c.execute("UPDATE epoch_state SET accepted_blocks = accepted_blocks + 1 WHERE epoch=?", (epoch,))

def enroll_epoch(epoch, miner_pk, weight):
    """Enroll miner in epoch with weight"""
    with sqlite3.connect(DB_PATH) as c:
        c.execute("INSERT OR REPLACE INTO epoch_enroll(epoch, miner_pk, weight) VALUES (?,?,?)", (epoch, miner_pk, float(weight)))

def finalize_epoch(epoch, per_block_rtc):
    """Finalize epoch and distribute rewards"""
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute("SELECT finalized, accepted_blocks FROM epoch_state WHERE epoch=?", (epoch,)).fetchone()
        if not row:
            return {"ok": False, "reason": "no_state"}

        finalized, blocks = int(row[0]), int(row[1])
        if finalized:
            return {"ok": False, "reason": "already_finalized"}

        total_reward = per_block_rtc * blocks
        miners = list(c.execute("SELECT miner_pk, weight FROM epoch_enroll WHERE epoch=?", (epoch,)))
        sum_w = sum(w for _, w in miners) or 0.0
        payouts = []

        if sum_w > 0 and total_reward > 0:
            for pk, w in miners:
                amt = total_reward * (w / sum_w)
                c.execute("INSERT OR IGNORE INTO balances(miner_pk, balance_rtc) VALUES (?,0)", (pk,))
                c.execute("UPDATE balances SET balance_rtc = balance_rtc + ? WHERE miner_pk=?", (amt, pk))
                payouts.append((pk, amt))

        c.execute("UPDATE epoch_state SET finalized=1 WHERE epoch=?", (epoch,))
        return {"ok": True, "blocks": blocks, "total_reward": total_reward, "sum_w": sum_w, "payouts": payouts}

def get_balance(miner_pk):
    """Get miner balance"""
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute("SELECT balance_rtc FROM balances WHERE miner_pk=?", (miner_pk,)).fetchone()
        return float(row[0]) if row else 0.0

def get_hardware_weight(device):
    """Get hardware multiplier from device info"""
    family = device.get("family", "default")
    arch = device.get("arch", "default")

    if family in HARDWARE_WEIGHTS:
        return HARDWARE_WEIGHTS[family].get(arch, HARDWARE_WEIGHTS[family].get("default", 1.0))
    return 1.0

def consume_ticket(ticket_id):
    """Consume a ticket (mark as used)"""
    if ticket_id in tickets_db:
        ticket = tickets_db[ticket_id]
        if ticket["expires_at"] > time.time():
            del tickets_db[ticket_id]
            return True
    return False

@app.get("/api/stats")
def api_stats():
    """Network statistics endpoint"""
    current_slot = int(time.time() // BLOCK_TIME)
    current_epoch = slot_to_epoch(current_slot)

    return jsonify({
        "block_time": BLOCK_TIME,
        "per_block_rtc": PER_BLOCK_RTC,
        "epoch_slots": EPOCH_SLOTS,
        "current_epoch": current_epoch,
        "current_slot": current_slot,
        "active_miners": len(mining_pool),
        "registered_nodes": len(registered_nodes),
        "enforce_mode": ENFORCE,
        "network": "mainnet",
        "version": "2.1.0-rip5"
    })

@app.get("/api/last_hash")
def api_last_hash():
    """Get last block hash for VRF beacon"""
    return jsonify({"hash_b3": LAST_HASH_B3})

@app.get("/epoch")
def get_epoch():
    """Get current epoch information"""
    now_slot = int(time.time() // BLOCK_TIME)
    epoch = slot_to_epoch(now_slot)

    # Get epoch state
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute("SELECT accepted_blocks, finalized FROM epoch_state WHERE epoch=?", (epoch,)).fetchone()
        blocks = int(row[0]) if row else 0
        finalized = bool(row[1]) if row else False

        # Count enrolled miners
        miners = c.execute("SELECT COUNT(*), SUM(weight) FROM epoch_enroll WHERE epoch=?", (epoch,)).fetchone()
        miner_count = int(miners[0]) if miners[0] else 0
        total_weight = float(miners[1]) if miners[1] else 0.0

    return jsonify({
        "epoch": epoch,
        "slots_per_epoch": EPOCH_SLOTS,
        "per_block_rtc": PER_BLOCK_RTC,
        "current_slot": now_slot,
        "slot_in_epoch": now_slot % EPOCH_SLOTS,
        "blocks_this_epoch": blocks,
        "enrolled_miners": miner_count,
        "total_weight": total_weight,
        "finalized": finalized,
        "epoch_pot": PER_BLOCK_RTC * blocks
    })

@app.post("/epoch/enroll")
def epoch_enroll():
    """Enroll miner in current epoch"""
    data = request.get_json(force=True) or {}

    miner_pk = data.get("miner_pubkey", "")
    weights = data.get("weights", {}) or {}
    device = data.get("device", {}) or {}
    ticket_id = data.get("ticket_id", "")

    if not miner_pk or not ticket_id:
        return jsonify({"ok": False, "reason": "missing_params"}), 400

    # Consume ticket (anti-replay)
    if not consume_ticket(ticket_id):
        return jsonify({"ok": False, "reason": "ticket_invalid"}), 400

    # Compute epoch
    slot = int(data.get("slot", int(time.time() // BLOCK_TIME)))
    epoch = slot_to_epoch(slot)

    # Calculate weight = temporal × rtc × hardware
    temporal = float(weights.get("temporal", 1.0))
    rtc = float(weights.get("rtc", 1.0))
    hw = get_hardware_weight(device)
    total_weight = temporal * rtc * hw

    # Enroll
    enroll_epoch(epoch, miner_pk, total_weight)

    return jsonify({
        "ok": True,
        "epoch": epoch,
        "weight": total_weight,
        "hardware_multiplier": hw,
        "device_tier": "Classic" if hw >= 2.0 else "Modern"
    })

@app.get("/balance/<miner_pk>")
def balance(miner_pk):
    """Get miner balance"""
    bal = get_balance(miner_pk)
    return jsonify({
        "miner": miner_pk,
        "balance_rtc": bal
    })

@app.post("/api/register")
def api_register():
    """Register node with hardware fingerprint"""
    data = request.get_json(force=True)

    system_id = data.get("system_id")
    fingerprint = data.get("fingerprint", {})

    if not system_id or not fingerprint:
        return jsonify({"error": "missing_data"}), 400

    # Check blacklist
    fp_hash = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
    if fp_hash in blacklisted:
        return jsonify({"error": "blacklisted"}), 403

    # Store registration
    registered_nodes[system_id] = {
        "fingerprint": fingerprint,
        "registered_at": time.time(),
        "hardware_tier": get_hardware_tier(fingerprint)
    }

    return jsonify({
        "success": True,
        "system_id": system_id,
        "hardware_tier": registered_nodes[system_id]["hardware_tier"]
    })

@app.post("/attest/challenge")
def attest_challenge():
    """Get attestation challenge"""
    nonce = secrets.token_hex(16)
    return jsonify({
        "nonce": nonce,
        "window_s": 120,
        "policy_id": "rip5"
    })

@app.post("/attest/submit")
def attest_submit():
    """Submit Silicon Ticket attestation"""
    data = request.get_json(force=True)
    report = data.get("report", {})

    # Basic validation
    if not report.get("commitment"):
        return jsonify({"error": "missing_commitment"}), 400

    # Create ticket
    ticket_id = secrets.token_hex(8)
    ticket = {
        "ticket_id": ticket_id,
        "commitment": report["commitment"],
        "expires_at": int(time.time()) + 3600,
        "device": report.get("device", {}),
        "weight": get_hardware_weight(report.get("device", {}))
    }

    tickets_db[ticket_id] = ticket
    return jsonify(ticket)

@app.post("/api/submit_block")
def api_submit_block():
    """Submit block with VRF proof and Silicon Ticket"""
    global LAST_HASH_B3, LAST_EPOCH

    data = request.get_json(force=True)
    header = data.get("header", {})
    ext = data.get("header_ext", {})

    # Check previous hash
    if header.get("prev_hash_b3") != LAST_HASH_B3:
        return jsonify({"error": "bad_prev_hash"}), 409

    # Validate Silicon Ticket if enforced
    ticket = ext.get("ticket", {})
    ticket_id = ticket.get("ticket_id")

    if ENFORCE and ticket_id and ticket_id not in tickets_db:
        return jsonify({"error": "invalid_ticket"}), 400

    # Epoch rollover & accounting
    slot = int(header.get("slot", 0))
    epoch = slot_to_epoch(slot)

    if LAST_EPOCH is None:
        LAST_EPOCH = epoch

    if epoch != LAST_EPOCH:
        # Finalize previous epoch
        result = finalize_epoch(LAST_EPOCH, PER_BLOCK_RTC)
        print(f"Finalized epoch {LAST_EPOCH}: {result}")
        LAST_EPOCH = epoch

    # Add block to current epoch
    inc_epoch_block(epoch)

    # Update block hash
    payload = json.dumps({"header": header, "ext": ext}, sort_keys=True).encode()
    LAST_HASH_B3 = hashlib.sha256(payload).hexdigest()

    return jsonify({
        "ok": True,
        "new_hash_b3": LAST_HASH_B3,
        "reward_rtc": PER_BLOCK_RTC,
        "epoch": epoch
    })

@app.get("/health")
def health():
    """Health check endpoint"""
    return jsonify({
        "ok": True,
        "service": "rustchain_v2_rip5",
        "enforce": ENFORCE,
        "epoch_system": "active"
    })

def get_hardware_tier(fingerprint):
    """Determine hardware age tier"""
    platform = fingerprint.get("platform", {})

    if "PowerPC" in platform.get("processor", ""):
        return "Classic"
    elif "x86" in platform.get("processor", ""):
        return "Modern"
    else:
        return "Unknown"

if __name__ == "__main__":
    init_db()
    print("RustChain v2 RIP-0005 - Epoch Pro-Rata Rewards")
    print(f"Block Time: {BLOCK_TIME}s, Reward: {PER_BLOCK_RTC} RTC per block")
    print(f"Epoch Length: {EPOCH_SLOTS} blocks ({EPOCH_SLOTS * BLOCK_TIME // 3600}h)")
    print(f"Enforcement: {ENFORCE}")

    # Show current epoch
    current_slot = int(time.time() // BLOCK_TIME)
    current_epoch = slot_to_epoch(current_slot)
    print(f"Current Epoch: {current_epoch}, Slot: {current_slot}")

    app.run(host="0.0.0.0", port=8088)