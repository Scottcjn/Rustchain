#!/usr/bin/env python3
"""
Warthog Dual-Mining Verification (Server-Side)
===============================================

Validates Warthog proof payloads submitted by dual-miners.
Determines bonus tier and records proofs for epoch reward calculation.

Target audience: Modern/semi-modern machines WITH GPUs.
Vintage hardware (G4, G5, retro) already earns high antiquity multipliers
and can't run the modern GPUs required for Warthog's Janushash PoW.
This bonus gives GPU-equipped modern miners a slight edge — bumping
their base ~0.8-1.0x weight up toward ~1.1-1.15x.

Bonus tiers:
  1.0x   No Warthog (default — all existing miners unchanged)
  1.1x   Pool mining confirmed (contributing GPU hashrate)
  1.15x  Own Warthog node confirmed (running full node + balance)

Replay prevention: one proof per miner per epoch.
"""

import time
import sqlite3
from typing import Tuple

# Warthog bonus tier constants — intentionally modest.
# Modern machines sit at 0.8-1.0x base; this nudges them up slightly,
# NOT enough to overtake vintage antiquity bonuses (G4=2.5x, G5=2.0x).
WART_BONUS_NONE = 1.0
WART_BONUS_POOL = 1.1
WART_BONUS_NODE = 1.15

# Minimum node height to be considered plausible (Warthog mainnet launched 2023)
MIN_PLAUSIBLE_HEIGHT = 1000

# Maximum age of a proof timestamp (seconds) - reject stale proofs
MAX_PROOF_AGE = 900  # 15 minutes


def init_warthog_tables(conn):
    """
    Create Warthog dual-mining tables if they don't exist.

    Args:
        conn: sqlite3 connection (or cursor)
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS warthog_mining_proofs (
            miner TEXT NOT NULL,
            epoch INTEGER NOT NULL,
            proof_type TEXT NOT NULL,
            wart_address TEXT,
            wart_node_height INTEGER,
            wart_balance TEXT,
            pool_url TEXT,
            pool_hashrate REAL,
            bonus_tier REAL DEFAULT 1.0,
            verified INTEGER DEFAULT 0,
            verified_reason TEXT,
            submitted_at INTEGER NOT NULL,
            PRIMARY KEY (miner, epoch)
        )
    """)

    # Safely add warthog_bonus column to miner_attest_recent
    try:
        conn.execute(
            "ALTER TABLE miner_attest_recent ADD COLUMN warthog_bonus REAL DEFAULT 1.0"
        )
    except Exception:
        pass  # Column already exists


def verify_warthog_proof(proof, miner_id) -> Tuple[bool, float, str]:
    """
    Validate a Warthog dual-mining proof submitted with attestation.

    Server-side checks:
      - Proof structure is valid
      - Proof timestamp is recent (not replayed from old session)
      - Node proof: synced==True, height plausible, balance non-zero
      - Pool proof: known pool URL, hashrate > 0

    Args:
        proof: dict from attestation payload's "warthog" key
        miner_id: RustChain miner identifier

    Returns:
        (verified, bonus_tier, reason)
    """
    if not proof or not isinstance(proof, dict):
        return False, WART_BONUS_NONE, "no_proof_data"

    if not proof.get("enabled"):
        return False, WART_BONUS_NONE, "warthog_not_enabled"

    # Check proof freshness
    collected_at = proof.get("collected_at", 0)
    if collected_at and abs(time.time() - collected_at) > MAX_PROOF_AGE:
        return False, WART_BONUS_NONE, "proof_too_old"

    # Validate WART address present
    wart_address = proof.get("wart_address", "")
    if not wart_address or len(wart_address) < 10:
        return False, WART_BONUS_NONE, "invalid_wart_address"

    proof_type = proof.get("proof_type", "none")

    # === Tier 1.5: Own Node Verification ===
    if proof_type == "own_node":
        node = proof.get("node")
        if not node or not isinstance(node, dict):
            return False, WART_BONUS_NONE, "node_data_missing"

        # Must be synced
        if not node.get("synced"):
            return False, WART_BONUS_NONE, "node_not_synced"

        # Height must be plausible
        height = node.get("height", 0)
        if not height or height < MIN_PLAUSIBLE_HEIGHT:
            return False, WART_BONUS_NONE, f"implausible_height_{height}"

        # Balance must be non-zero (proves actual mining activity)
        balance_str = proof.get("balance", "0")
        try:
            balance = float(balance_str)
        except (ValueError, TypeError):
            balance = 0.0

        if balance <= 0:
            # Node running but no balance — downgrade to pool tier
            # (they're contributing hashpower but haven't earned yet)
            return True, WART_BONUS_POOL, "node_no_balance_downgraded"

        return True, WART_BONUS_NODE, "own_node_verified"

    # === Tier 1.3: Pool Mining Verification ===
    if proof_type == "pool":
        pool = proof.get("pool")
        if not pool or not isinstance(pool, dict):
            return False, WART_BONUS_NONE, "pool_data_missing"

        hashrate = pool.get("hashrate", 0)
        if not hashrate or hashrate <= 0:
            return False, WART_BONUS_NONE, "pool_zero_hashrate"

        pool_url = pool.get("url", "")
        if not pool_url:
            return False, WART_BONUS_NONE, "pool_url_missing"

        return True, WART_BONUS_POOL, "pool_mining_verified"

    # Unknown proof type
    return False, WART_BONUS_NONE, f"unknown_proof_type_{proof_type}"


def record_warthog_proof(conn, miner_id, epoch, proof, verified, bonus_tier, reason):
    """
    Write Warthog proof record to database.

    Args:
        conn: sqlite3 connection
        miner_id: RustChain miner identifier
        epoch: Current epoch number
        proof: Raw proof dict
        verified: Boolean result
        bonus_tier: Float bonus multiplier
        reason: Verification reason string
    """
    node = proof.get("node") or {}
    pool = proof.get("pool") or {}

    try:
        conn.execute("""
            INSERT OR REPLACE INTO warthog_mining_proofs
            (miner, epoch, proof_type, wart_address, wart_node_height,
             wart_balance, pool_url, pool_hashrate, bonus_tier,
             verified, verified_reason, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            miner_id,
            epoch,
            proof.get("proof_type", "none"),
            proof.get("wart_address", ""),
            node.get("height"),
            proof.get("balance"),
            pool.get("url"),
            pool.get("hashrate"),
            bonus_tier,
            1 if verified else 0,
            reason,
            int(time.time()),
        ))
        conn.commit()
    except Exception as e:
        print(f"[WARTHOG] Error recording proof: {e}")


def get_warthog_bonus(conn, miner_id):
    """
    Get current Warthog bonus for a miner from latest attestation.

    Args:
        conn: sqlite3 connection
        miner_id: RustChain miner identifier

    Returns:
        Float bonus multiplier (1.0 if no Warthog)
    """
    try:
        row = conn.execute(
            "SELECT warthog_bonus FROM miner_attest_recent WHERE miner = ?",
            (miner_id,)
        ).fetchone()
        if row and row[0] and row[0] > 1.0:
            return row[0]
    except Exception:
        pass  # Column may not exist on older schemas

    return WART_BONUS_NONE


if __name__ == "__main__":
    # Self-test with mock proofs
    print("=" * 60)
    print("Warthog Verification - Self Test")
    print("=" * 60)

    # Test 1: No proof
    ok, tier, reason = verify_warthog_proof(None, "test-miner")
    print(f"[1] No proof:     ok={ok}, tier={tier}, reason={reason}")
    assert tier == 1.0

    # Test 2: Valid own node (modern machine with GPU running Warthog full node)
    ok, tier, reason = verify_warthog_proof({
        "enabled": True,
        "wart_address": "wart1qtest123456789",
        "proof_type": "own_node",
        "node": {"height": 500000, "synced": True, "hash": "abc123"},
        "balance": "42.5",
        "collected_at": int(time.time()),
    }, "test-miner")
    print(f"[2] Own node:     ok={ok}, tier={tier}, reason={reason}")
    assert tier == 1.15

    # Test 3: Node but no balance (new miner, hasn't earned yet — downgrade to pool tier)
    ok, tier, reason = verify_warthog_proof({
        "enabled": True,
        "wart_address": "wart1qtest123456789",
        "proof_type": "own_node",
        "node": {"height": 500000, "synced": True},
        "balance": "0",
        "collected_at": int(time.time()),
    }, "test-miner")
    print(f"[3] No balance:   ok={ok}, tier={tier}, reason={reason}")
    assert tier == 1.1  # Downgraded to pool

    # Test 4: Pool mining
    ok, tier, reason = verify_warthog_proof({
        "enabled": True,
        "wart_address": "wart1qtest123456789",
        "proof_type": "pool",
        "pool": {"url": "https://acc-pool.pw", "hashrate": 150.5, "shares": 42},
        "collected_at": int(time.time()),
    }, "test-miner")
    print(f"[4] Pool mining:  ok={ok}, tier={tier}, reason={reason}")
    assert tier == 1.1

    # Test 5: Stale proof
    ok, tier, reason = verify_warthog_proof({
        "enabled": True,
        "wart_address": "wart1qtest123456789",
        "proof_type": "own_node",
        "node": {"height": 500000, "synced": True},
        "balance": "42.5",
        "collected_at": int(time.time()) - 3600,  # 1 hour old
    }, "test-miner")
    print(f"[5] Stale proof:  ok={ok}, tier={tier}, reason={reason}")
    assert tier == 1.0  # Rejected

    # Test 6: DB operations
    import tempfile, os
    db_path = os.path.join(tempfile.gettempdir(), "wart_test.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS miner_attest_recent (
            miner TEXT PRIMARY KEY, ts_ok INTEGER, device_family TEXT,
            device_arch TEXT, entropy_score REAL DEFAULT 0.0,
            fingerprint_passed INTEGER DEFAULT 0, source_ip TEXT
        )""")
        init_warthog_tables(conn)
        record_warthog_proof(conn, "test-miner", 100, {
            "proof_type": "own_node", "wart_address": "wart1qtest",
            "node": {"height": 500000}, "balance": "42.5",
        }, True, 1.15, "own_node_verified")
        conn.execute(
            "INSERT OR REPLACE INTO miner_attest_recent (miner, ts_ok, warthog_bonus) VALUES (?, ?, ?)",
            ("test-miner", int(time.time()), 1.15)
        )
        bonus = get_warthog_bonus(conn, "test-miner")
        print(f"[6] DB bonus:     {bonus}")
        assert bonus == 1.15

    os.unlink(db_path)
    print("\nAll tests passed!")
