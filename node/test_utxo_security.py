"""
UTXO Security Tests — [UTXO-BUG] Critical Vulnerabilities Found
===============================================================

These tests demonstrate 3 critical/high severity vulnerabilities in the UTXO layer.

Run with: python -m pytest node/test_utxo_security.py -v

FINDING 1 [CRITICAL] — Coinbase Conservation Law Bypass (200 RTC)
===================================================================
File:   utxo_db.py, apply_transaction()
Bug:    Conservation check is skipped when inputs=[]
Impact: A malicious miner can create unlimited RTC via coinbase tx

FINDING 2 [HIGH] — Genesis Migration Non-Idempotency (100 RTC)
==============================================================
File:   utxo_genesis_migration.py, migrate()
Bug:    Partial migration leaves DB in unrecoverable stuck state
Impact: Node crash mid-migration → permanently blocked from completing

FINDING 3 [MEDIUM] — Negative/Zero Value Outputs (50 RTC)
=========================================================
File:   utxo_db.py, apply_transaction()
Bug:    No validation that output values are positive
Impact: Dust/zero-value box spam, potential consensus issues
"""

import hashlib
import os
import tempfile
import unittest

from utxo_db import UtxoDB, UNIT


class TestCoinbaseConservationBypass(unittest.TestCase):
    """
    [UTXO-BUG-CRITICAL-01] Coinbase transactions bypass conservation law.

    apply_transaction checks: if inputs and (output_total + fee) > input_total: return False
    The 'if inputs' means coinbase (no inputs) skips the check entirely.
    A miner can mint unlimited RTC.
    """

    def setUp(self):
        self.db = UtxoDB(tempfile.mktemp(suffix='.db'))
        self.db.init_tables()

    def test_coinbase_can_create_max_value(self):
        """A miner can create a coinbase tx with outputs exceeding any reasonable reward."""
        # Normal miner reward should be capped, but there's NO cap in the code
        miner_reward = 1_000_000 * UNIT  # 1M RTC — far exceeding any block reward

        coinbase_tx = {
            'tx_type': 'coinbase',
            'inputs': [],  # NO INPUTS — skips conservation check
            'outputs': [
                {'address': 'miner001', 'value_nrtc': miner_reward}
            ],
            'fee_nrtc': 0,
            'timestamp': 0,
        }

        result = self.db.apply_transaction(coinbase_tx, block_height=1)
        # This returns TRUE — the conservation law was bypassed!
        self.assertTrue(result, "Bug: coinbase tx should be rejected for exceeding conservation law")

    def test_coinbase_zero_value_input_inflation(self):
        """A miner can create RTC from nothing with zero-value inputs ignored."""
        # Even with a technically-empty input list item
        coinbase_with_empty_inputs = {
            'tx_type': 'coinbase',
            'inputs': [],  # explicitly empty
            'outputs': [
                {'address': 'attacker', 'value_nrtc': 999_999 * UNIT}
            ],
            'fee_nrtc': 0,
        }

        result = self.db.apply_transaction(coinbase_with_empty_inputs, block_height=1)
        self.assertFalse(result, "Bug: coinbase must respect total supply caps")

    def test_coinbase_multiple_outputs_exceed_supply(self):
        """Multiple outputs that collectively exceed total supply should be rejected."""
        # Create outputs totalling 5M RTC with no inputs
        malicious_coinbase = {
            'tx_type': 'coinbase',
            'inputs': [],
            'outputs': [
                {'address': 'addr1', 'value_nrtc': 2_000_000 * UNIT},
                {'address': 'addr2', 'value_nrtc': 2_000_000 * UNIT},
                {'address': 'addr3', 'value_nrtc': 1_000_000 * UNIT},
            ],
            'fee_nrtc': 0,
        }
        result = self.db.apply_transaction(malicious_coinbase, block_height=1)
        self.assertFalse(result,
            "Bug: coinbase outputs totalling 5M RTC with zero inputs should be rejected")


class TestGenesisMigrationIdempotency(unittest.TestCase):
    """
    [UTXO-BUG-HIGH-01] Genesis migration is NOT idempotent.

    If migrate() crashes after inserting some boxes but before COMMIT,
    re-running it sees genesis boxes already exist → permanently aborts.
    No recovery path exists without manual SQL intervention.
    """

    def setUp(self):
        self.db_path = tempfile.mktemp(suffix='.db')
        self.db = UtxoDB(self.db_path)
        self.db.init_tables()

    def test_partial_migration_blocks_rerun(self):
        """
        Simulate partial migration by inserting ONE genesis box,
        then trying to run migrate() again — it should either complete
        or provide a recovery path, but instead it permanently blocks.
        """
        import sqlite3
        from utxo_db import address_to_proposition, compute_box_id

        miner_id = 'test_miner_001'
        amount_i64 = 1000 * UNIT
        tx_id = hashlib.sha256(('rustchain_genesis:' + miner_id).encode()).hexdigest()
        prop = address_to_proposition(miner_id)
        box_id = compute_box_id(amount_i64, prop, 0, tx_id, 0)

        # Manually insert ONE genesis box (simulating partial migration crash)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO utxo_boxes
            (box_id, value_nrtc, proposition, owner_address, creation_height,
             transaction_id, output_index, tokens_json, registers_json, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (box_id, amount_i64, prop, miner_id, 0, tx_id, 0, '[]', '{}', 0))
        conn.commit()
        conn.close()

        # Now try to migrate again
        from utxo_genesis_migration import migrate

        # This should either: (a) complete the migration, or (b) provide recovery
        # But instead it returns {'error': 'genesis_already_exists'}
        # — permanently blocking the migration with no recovery path
        result = migrate(self.db_path, dry_run=False)

        # The bug: it refuses to run even though only PARTIAL migration exists
        # A proper implementation would be idempotent or provide rollback
        self.assertIn('error', result,
            "Bug: partial migration permanently blocks re-run — should be idempotent or provide recovery")

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except:
            pass


class TestNegativeValueOutputs(unittest.TestCase):
    """
    [UTXO-BUG-MEDIUM-01] No validation that output values are positive.

    apply_transaction never checks: out['value_nrtc'] > 0
    A transaction can create zero or negative value boxes.
    """

    def setUp(self):
        self.db = UtxoDB(tempfile.mktemp(suffix='.db'))
        self.db.init_tables()

        # Create a funding box first
        funder_box = {
            'box_id': 'aabbccdd' * 4,
            'value_nrtc': 100 * UNIT,
            'proposition': '0011' + '22' * 29,
            'owner_address': 'funder',
            'creation_height': 1,
            'transaction_id': '00' * 32,
            'output_index': 0,
        }
        self.db.add_box(funder_box)

    def test_zero_value_output_accepted(self):
        """Zero-value outputs should be rejected as economically meaningless."""
        tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': 'aabbccdd' * 4, 'spending_proof': ''}],
            'outputs': [
                {'address': 'victim', 'value_nrtc': 0}  # ZERO VALUE
            ],
            'fee_nrtc': 0,
        }
        result = self.db.apply_transaction(tx, block_height=2)
        # Should be rejected — zero value outputs are dust/spam
        self.assertFalse(result,
            "Bug: zero-value outputs should be rejected, they are economically meaningless")

    def test_negative_value_output_accepted(self):
        """Negative output values should be mathematically rejected."""
        tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': 'aabbccdd' * 4, 'spending_proof': ''}],
            'outputs': [
                {'address': 'attacker', 'value_nrtc': -5000}  # NEGATIVE — should not be possible
            ],
            'fee_nrtc': 0,
        }
        result = self.db.apply_transaction(tx, block_height=2)
        # Should be rejected — negative values are invalid
        self.assertFalse(result,
            "Bug: negative value outputs should be rejected as mathematically impossible")


if __name__ == '__main__':
    unittest.main()
