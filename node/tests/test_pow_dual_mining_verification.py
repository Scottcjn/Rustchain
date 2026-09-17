"""
node/tests/test_pow_dual_mining_verification.py

Comprehensive test suite for Server-Side PoW Dual-Mining Verification Engine (Bounty #453):
- Supported chain validation (Ergo, Monero, Warthog, Kaspa, etc.)
- Tier 1.5x Node RPC validation (height floors, mining candidate)
- Tier 1.3x Pool validation (hashrate check, pool URL)
- Tier 1.15x Process detection (allowed processes, PID sanity)
- Anti-cheat checks (nonce binding, replay rejection, stale proofs)
"""

import sqlite3
import time
import pytest
from node.pow_dual_mining_verification import (
    init_pow_tables,
    validate_pow_proof,
    record_pow_proof,
    get_pow_bonus,
    POW_BONUS_NONE,
    POW_BONUS_PROCESS,
    POW_BONUS_POOL,
    POW_BONUS_NODE,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    init_pow_tables(c)
    # Create mock miner_attest_recent table
    c.execute("""
        CREATE TABLE IF NOT EXISTS miner_attest_recent (
            miner TEXT PRIMARY KEY,
            pow_bonus REAL DEFAULT 1.0
        )
    """)
    yield c
    c.close()


def test_validate_pow_proof_no_payload():
    ok, bonus, reason = validate_pow_proof(None, "miner_1", 100)
    assert ok is False
    assert bonus == POW_BONUS_NONE
    assert reason == "no_proof_payload"


def test_validate_pow_proof_unsupported_chain():
    proof = {"chain": "bitcoin", "nonce": "nonce_123456", "collected_at": time.time()}
    ok, bonus, reason = validate_pow_proof(proof, "miner_1", 100)
    assert ok is False
    assert bonus == POW_BONUS_NONE
    assert "unsupported_chain" in reason


def test_validate_pow_proof_stale_timestamp():
    proof = {
        "chain": "ergo",
        "nonce": "nonce_123456",
        "collected_at": time.time() - 2000,
    }
    ok, bonus, reason = validate_pow_proof(proof, "miner_1", 100)
    assert ok is False
    assert reason == "proof_expired_or_stale"


def test_validate_pow_proof_short_nonce():
    proof = {
        "chain": "ergo",
        "nonce": "short",
        "collected_at": time.time(),
    }
    ok, bonus, reason = validate_pow_proof(proof, "miner_1", 100)
    assert ok is False
    assert reason == "missing_or_short_nonce"


def test_validate_pow_proof_node_rpc_success(conn):
    proof = {
        "chain": "ergo",
        "nonce": "nonce_ergo_node_999",
        "collected_at": time.time(),
        "proof_type": "node_rpc",
        "node": {
            "is_mining": True,
            "height": 1350000,
            "peers": 28,
        }
    }
    ok, bonus, reason = validate_pow_proof(proof, "miner_1", 100, conn)
    assert ok is True
    assert bonus == POW_BONUS_NODE
    assert "ergo_node_rpc_verified" in reason

    record_pow_proof(conn, "miner_1", 100, proof, ok, bonus, reason)

    # Test replay protection within same epoch
    ok_replay, bonus_replay, reason_replay = validate_pow_proof(proof, "miner_1", 100, conn)
    assert ok_replay is False
    assert reason_replay == "duplicate_proof_for_epoch"


def test_validate_pow_proof_node_rpc_implausible_height():
    proof = {
        "chain": "monero",
        "nonce": "nonce_xmr_fake",
        "collected_at": time.time(),
        "proof_type": "node_rpc",
        "node": {"is_mining": True, "height": 500}
    }
    ok, bonus, reason = validate_pow_proof(proof, "miner_1", 100)
    assert ok is False
    assert "implausible_node_height" in reason


def test_validate_pow_proof_pool_success(conn):
    proof = {
        "chain": "monero",
        "nonce": "nonce_pool_xmr_777",
        "collected_at": time.time(),
        "proof_type": "pool",
        "pool": {
            "url": "https://p2pool.io",
            "hashrate": 18500.5,
        }
    }
    ok, bonus, reason = validate_pow_proof(proof, "miner_2", 100, conn)
    assert ok is True
    assert bonus == POW_BONUS_POOL
    assert "monero_pool_mining_verified" in reason


def test_validate_pow_proof_pool_zero_hashrate():
    proof = {
        "chain": "kaspa",
        "nonce": "nonce_kaspa_pool_00",
        "collected_at": time.time(),
        "proof_type": "pool",
        "pool": {"url": "https://herominers.com", "hashrate": 0}
    }
    ok, bonus, reason = validate_pow_proof(proof, "miner_3", 100)
    assert ok is False
    assert reason == "pool_zero_hashrate"


def test_validate_pow_proof_process_detection_success(conn):
    proof = {
        "chain": "warthog",
        "nonce": "nonce_wart_proc_88",
        "collected_at": time.time(),
        "proof_type": "process",
        "process": {
            "name": "wart-miner-cpu",
            "pid": 41250,
        }
    }
    ok, bonus, reason = validate_pow_proof(proof, "miner_4", 100, conn)
    assert ok is True
    assert bonus == POW_BONUS_PROCESS
    assert "warthog_process_detected" in reason


def test_get_pow_bonus_default(conn):
    conn.execute("INSERT INTO miner_attest_recent (miner, pow_bonus) VALUES ('miner_10', 1.5)")
    assert get_pow_bonus(conn, "miner_10") == 1.5
    assert get_pow_bonus(conn, "unknown_miner") == 1.0
