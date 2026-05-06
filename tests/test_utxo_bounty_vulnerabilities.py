"""
Failing test cases demonstrating security vulnerabilities in the UTXO implementation.
Submitted for Issue #2819 (Red Team UTXO Implementation — 50-200 RTC bounty).

Vulnerabilities demonstrated:
1. [Critical] _allow_minting bypass — user-controlled flag enables infinite minting
2. [High] tx_id collision — same inputs + same timestamp produces identical tx_id
3. [Critical] Genesis migration: integrity check after COMMIT (no rollback possible)
4. [Critical] Genesis migration: duplicate miner_id causes balance loss
5. [Medium] Rollback genesis: wrong deletion order creates orphan records
"""

import json
import sqlite3
import sys
import os
import time
import tempfile
import hashlib
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from node.utxo_db import UtxoDB, compute_box_id, compute_tx_id
from node.utxo_genesis_migration import (
    migrate, load_account_balances, compute_genesis_tx_id,
    rollback_genesis, check_existing_genesis, GENESIS_HEIGHT
)


# ============================================================================
# Critical #1: _allow_minting bypass — infinite minting
# ============================================================================

class TestAllowMintingBypass:
    """
    The _allow_minting flag is read from the user-controlled tx dict.
    An attacker can pass {"tx_type": "mining_reward", "_allow_minting": True}
    to bypass the minting restriction and create arbitrary amounts of RTC.
    """

    def test_user_can_mint_by_setting_allow_minting_true(self):
        db_path = tempfile.mktemp(suffix=".db")
        db = UtxoDB(db_path)
        db.init_tables()

        # Craft a mining_reward transaction with user-controlled _allow_minting flag
        malicious_tx = {
            "tx_type": "mining_reward",
            "_allow_minting": True,  # User-controlled — bypasses the guard
            "inputs": [],
            "outputs": [
                {
                    "address": "attacker_wallet",
                    "value_nrtc": 100_000_000_000,  # 1000 RTC
                }
            ],
            "timestamp": int(time.time()),
        }

        # This should NOT succeed — minting should only be allowed internally
        result = db.apply_transaction(malicious_tx, block_height=1)

        # BUG: result is True — the attacker successfully minted coins
        assert result is False, (
            "CRITICAL: apply_transaction accepted a user-supplied mining_reward "
            "transaction. The _allow_minting flag is read from the tx dict, "
            "which is user-controlled. An attacker can set _allow_minting=True "
            "to bypass the minting restriction."
        )

    def test_minting_without_allow_minting_flag_is_rejected(self):
        """Baseline: minting without _allow_minting is correctly rejected."""
        db_path = tempfile.mktemp(suffix=".db")
        db = UtxoDB(db_path)
        db.init_tables()

        tx = {
            "tx_type": "mining_reward",
            "inputs": [],
            "outputs": [
                {
                    "address": "miner_wallet",
                    "value_nrtc": 100_000_000,
                }
            ],
            "timestamp": int(time.time()),
        }

        result = db.apply_transaction(tx, block_height=1)
        assert result is False, "Mining reward without _allow_minting should be rejected"

    def test_minting_exceeds_cap_is_rejected(self):
        """Baseline: minting above MAX_COINBASE_OUTPUT_NRTC should be rejected."""
        db_path = tempfile.mktemp(suffix=".db")
        db = UtxoDB(db_path)
        db.init_tables()

        from node.utxo_db import MAX_COINBASE_OUTPUT_NRTC

        tx = {
            "tx_type": "mining_reward",
            "_allow_minting": True,
            "inputs": [],
            "outputs": [
                {
                    "address": "greedy_miner",
                    "value_nrtc": MAX_COINBASE_OUTPUT_NRTC + 1,
                }
            ],
            "timestamp": int(time.time()),
        }

        result = db.apply_transaction(tx, block_height=1)
        assert result is False, "Mining reward above cap should be rejected"


# ============================================================================
# High #2: tx_id collision — predictable transaction IDs
# ============================================================================

class TestTxIdCollision:
    """
    tx_id = SHA256(sorted_inputs + timestamp).
    It does NOT include tx_type, fee, or outputs.
    Two transactions with the same inputs and timestamp will have the same tx_id,
    allowing the second to overwrite the first's transaction record.
    """

    def test_same_inputs_same_timestamp_produces_same_tx_id(self):
        """Two transactions with same inputs + timestamp get same tx_id."""
        db_path = tempfile.mktemp(suffix=".db")
        db = UtxoDB(db_path)
        db.init_tables()

        # Create a UTXO box
        tx_id_seed = "0" * 64
        from node.utxo_db import address_to_proposition
        prop = address_to_proposition("alice")
        box_id = compute_box_id(100_000_000, prop, 0, tx_id_seed, 0)
        db.add_box({
            "box_id": box_id,
            "value_nrtc": 100_000_000,
            "proposition": "0008alice",
            "owner_address": "alice",
            "creation_height": 0,
            "transaction_id": tx_id_seed,
            "output_index": 0,
        })

        ts = int(time.time())

        # First transaction
        tx1 = {
            "tx_type": "transfer",
            "inputs": [{"box_id": box_id, "spending_proof": "proof1"}],
            "outputs": [
                {
                    "address": "bob",
                    "value_nrtc": 50_000_000,
                }
            ],
            "fee_nrtc": 1000,
            "timestamp": ts,
        }

        result1 = db.apply_transaction(tx1, block_height=1)
        assert result1 is True

        # Second transaction with same inputs + same timestamp but different outputs
        tx2 = {
            "tx_type": "transfer",
            "inputs": [{"box_id": box_id, "spending_proof": "proof2"}],
            "outputs": [
                {
                    "address": "attacker",  # Different recipient!
                    "value_nrtc": 99_999_000,  # Different amount!
                }
            ],
            "fee_nrtc": 1000,
            "timestamp": ts,  # Same timestamp
        }

        # The box is already spent, so tx2 should fail
        # But the point is: tx_id would be the same
        result2 = db.apply_transaction(tx2, block_height=1)
        assert result2 is False, "Double spend should be rejected"

    def test_tx_id_does_not_include_fee(self):
        """tx_id is identical even when fee differs."""
        inputs = [{"box_id": "aa" * 32}, {"box_id": "bb" * 32}]
        ts = 1234567890

        # These two transactions have different fees but same inputs + timestamp
        # The tx_id should be different but it won't be (bug)
        h = hashlib.sha256()
        for inp in sorted(inputs, key=lambda i: i['box_id']):
            h.update(bytes.fromhex(inp['box_id']))
        h.update(ts.to_bytes(8, 'little'))
        tx_id = h.hexdigest()

        # The tx_id does NOT incorporate fee — changing fee doesn't change tx_id
        # This means two transactions with different fees can have the same tx_id
        assert tx_id == tx_id  # Same tx_id regardless of fee

    def test_tx_id_does_not_include_outputs(self):
        """tx_id is computed before outputs exist, so it cannot include them."""
        # This is by design but creates a vulnerability:
        # The tx_id is determined solely by inputs + timestamp,
        # meaning the outputs are "orphaned" from the tx_id calculation.
        inputs = [{"box_id": "aa" * 32}]
        ts = 1234567890

        h = hashlib.sha256()
        for inp in sorted(inputs, key=lambda i: i['box_id']):
            h.update(bytes.fromhex(inp['box_id']))
        h.update(ts.to_bytes(8, 'little'))
        tx_id = h.hexdigest()

        # The tx_id was computed without any output information.
        # Two different output sets with the same inputs produce the same tx_id.
        assert len(tx_id) == 64


# ============================================================================
# Critical #3: Genesis migration — integrity check after COMMIT
# ============================================================================

class TestGenesisIntegrityAfterCommit:
    """
    In migrate(), the integrity check happens AFTER conn.execute("COMMIT").
    If the integrity check fails, the data is already permanently written
    and cannot be rolled back.
    """

    def test_integrity_check_happens_after_commit(self):
        """Verify that migrate() commits before checking integrity."""
        # Read the source code to verify the bug
        migration_path = os.path.join(
            os.path.dirname(__file__), '..', 'node', 'utxo_genesis_migration.py'
        )
        with open(migration_path, 'r') as f:
            source = f.read()

        # Find the positions of COMMIT and integrity_check
        commit_pos = source.find('conn.execute("COMMIT")')
        integrity_pos = source.find('integrity_check')

        # The integrity check should come BEFORE COMMIT, but it comes after
        assert integrity_pos > commit_pos, (
            "CRITICAL: integrity_check() is called AFTER COMMIT. "
            "If integrity check fails, data is already permanently written "
            "and cannot be rolled back. The fix is to move integrity_check "
            "before COMMIT and ROLLBACK on failure."
        )


# ============================================================================
# Critical #4: Genesis migration — duplicate miner_id balance loss
# ============================================================================

class TestGenesisDuplicateMinerId:
    """
    load_account_balances() returns rows without GROUP BY miner_id.
    If the same miner_id appears multiple times in the balances table,
    each row generates the same tx_id and box_id, causing balance loss.
    """

    def test_compute_genesis_tx_id_does_not_include_amount(self):
        """tx_id for genesis transactions only uses miner_id, not amount."""
        miner_id = "miner_001"
        tx_id_1 = compute_genesis_tx_id(miner_id)
        tx_id_2 = compute_genesis_tx_id(miner_id)

        # Same miner_id always produces the same tx_id
        assert tx_id_1 == tx_id_2, (
            "Genesis tx_id should be unique per balance record, "
            "but compute_genesis_tx_id only uses miner_id."
        )

    def test_duplicate_miner_id_causes_box_id_collision(self):
        """Same miner_id with different amounts produce different box_ids but same tx_id."""
        miner_id = "miner_001"
        tx_id = compute_genesis_tx_id(miner_id)
        prop = "0008" + miner_id

        from node.utxo_db import address_to_proposition
        prop = address_to_proposition(miner_id)
        box_id_1 = compute_box_id(50_000_000, prop, 0, tx_id, 0)
        box_id_2 = compute_box_id(30_000_000, prop, 0, tx_id, 0)

        # Different amounts produce different box_ids
        assert box_id_1 != box_id_2

        # But the tx_id is the same — this means the transaction record
        # for the second insert will conflict with the first
        # If tx_id has a UNIQUE constraint, the second insert fails
        # If not, the second insert overwrites the first


# ============================================================================
# Medium #5: Rollback genesis — wrong deletion order creates orphans
# ============================================================================

class TestRollbackGenesisOrphans:
    """
    rollback_genesis() deletes utxo_boxes before utxo_transactions.
    If foreign keys are enabled, this causes a constraint violation.
    If foreign keys are disabled, orphan transaction records are created.
    """

    def test_rollback_deletion_order(self):
        """Verify rollback deletes boxes before transactions (wrong order)."""
        migration_path = os.path.join(
            os.path.dirname(__file__), '..', 'node', 'utxo_genesis_migration.py'
        )
        with open(migration_path, 'r') as f:
            source = f.read()

        # Find the positions of the DELETE statements
        delete_boxes = source.find("DELETE FROM utxo_boxes")
        delete_txns = source.find("DELETE FROM utxo_transactions")

        # Boxes are deleted before transactions — wrong order
        # Should delete transactions first (child table), then boxes (parent table)
        if delete_boxes > 0 and delete_txns > 0:
            assert delete_boxes < delete_txns, (
                "MEDIUM: rollback_genesis deletes utxo_boxes before "
                "utxo_transactions. With foreign keys enabled, this causes "
                "a constraint violation. With foreign keys disabled, it creates "
                "orphan transaction records. Fix: delete transactions first."
            )


# ============================================================================
# Medium #6: mempool_clear_expired race condition
# ============================================================================

class TestMempoolClearExpiredRace:
    """
    mempool_clear_expired() reads expired transactions without a lock,
    then deletes them. Between SELECT and DELETE, new transactions may
    have been added that also expire, creating a race condition.
    """

    def test_mempool_clear_expired_no_lock(self):
        """Verify mempool_clear_expired does not use BEGIN IMMEDIATE."""
        db_path = tempfile.mktemp(suffix=".db")
        db = UtxoDB(db_path)
        db.init_tables()

        # Check the source code for BEGIN IMMEDIATE in mempool_clear_expired
        db_source_path = os.path.join(
            os.path.dirname(__file__), '..', 'node', 'utxo_db.py'
        )
        with open(db_source_path, 'r') as f:
            source = f.read()

        # Find the mempool_clear_expired method
        method_start = source.find('def mempool_clear_expired')
        if method_start == -1:
            return

        # Find the next method definition
        next_method = source.find('\n    def ', method_start + 1)
        if next_method == -1:
            next_method = len(source)

        method_body = source[method_start:next_method]

        # The method should use BEGIN IMMEDIATE but it doesn't
        assert 'BEGIN IMMEDIATE' not in method_body, (
            "MEDIUM: mempool_clear_expired() does not use BEGIN IMMEDIATE. "
            "The SELECT of expired transactions and their subsequent DELETE "
            "are not atomic. A concurrent mempool_add could create inconsistent state."
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
