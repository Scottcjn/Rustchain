"""
Additional UTXO Vulnerability Test Cases
=========================================
Demonstrates multiple security issues in the UTXO layer.

Vulnerabilities covered:
1. Transaction ID collision (HIGH - 100 RTC)
2. Mempool tx_id spoofing (MEDIUM - 50 RTC)
3. Transaction log incompleteness (LOW - 25 RTC)
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import time

# Add node directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))

from utxo_db import UtxoDB, address_to_proposition, compute_box_id, UNIT


class TestTransactionIDCollision(unittest.TestCase):
    """Test that transaction IDs can collide when outputs differ."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_tx_id_collision_with_different_outputs(self):
        """
        HIGH: Transaction ID does not include outputs for non-coinbase txs.
        
        Two transactions with the same inputs and timestamp but DIFFERENT
        outputs will have the SAME tx_id.
        
        Attack scenario:
        1. Victim creates TX1: inputs -> output_to_victim
        2. Attacker creates TX2: same inputs -> output_to_attacker
        3. If TX1 and TX2 have same timestamp, they get same tx_id
        4. Both transactions produce same output box_ids
        5. Race condition could allow output substitution
        
        The tx_id is computed as SHA256(sorted input box_ids + timestamp).
        Outputs are NOT included (except for coinbase).
        """
        # Create two input boxes
        addr1 = "RTCsender_address_1234567890abcdef"
        addr2 = "RTCreceiver_address_0987654321fedcba"
        attacker = "RTCattacker_address_evil_1234567890ab"
        
        # Create a genesis box using internal minting flag
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [
                {'address': addr1, 'value_nrtc': 1000 * UNIT},
            ],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,  # Internal flag
        }, block_height=1)
        
        # Get the input box_id
        conn = self.db._conn()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT box_id FROM utxo_boxes WHERE owner_address = ? AND spent_at IS NULL",
            (addr1,)
        ).fetchone()
        input_box_id = row['box_id']
        
        # Create TX1: send to victim
        inputs1 = [{'box_id': input_box_id, 'spending_proof': 'proof1'}]
        outputs1 = [{'address': addr2, 'value_nrtc': 900 * UNIT}]
        tx1 = {
            'tx_type': 'transfer',
            'inputs': inputs1,
            'outputs': outputs1,
            'fee_nrtc': 0,
            'timestamp': 1000000,  # Fixed timestamp
        }
        
        # Apply TX1
        result1 = self.db.apply_transaction(tx1, block_height=2)
        self.assertTrue(result1, "TX1 should succeed")
        
        # Get TX1's tx_id from the transaction record
        row = conn.execute(
            "SELECT tx_id FROM utxo_transactions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        tx1_id = row['tx_id']
        
        # Now try to create TX2 with same inputs but different output address
        # Note: TX1 already spent the input, so TX2 will fail
        # But the POINT is that TX1 and TX2 would have the SAME tx_id
        # if they were applied independently
        
        # Verify the tx_id computation doesn't include outputs
        import hashlib
        h = hashlib.sha256()
        for inp in sorted(inputs1, key=lambda i: i['box_id']):
            h.update(bytes.fromhex(inp['box_id']))
        h.update((1000000).to_bytes(8, 'little'))
        expected_tx_id = h.hexdigest()
        
        self.assertEqual(tx1_id, expected_tx_id,
            "TX_ID should match the expected computation (inputs + timestamp only)")
        
        # The vulnerability: tx_id doesn't bind to outputs
        # This means output substitution is theoretically possible in race conditions
        conn.close()


class TestMempoolTxIDSpoofing(unittest.TestCase):
    """Test that mempool accepts transactions with arbitrary tx_id."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_mempool_accepts_spoofed_tx_id(self):
        """
        MEDIUM: mempool_add() doesn't verify tx_id matches transaction content.
        
        An attacker can provide any tx_id value, and the mempool will accept it.
        This could be used to:
        1. Collide with existing mempool transactions
        2. Evade mempool tracking
        3. Create confusion during block production
        """
        # Create a genesis box
        addr = "RTCsender_address_1234567890abcdef"
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': addr, 'value_nrtc': 1000 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        
        # Get the input box_id
        conn = self.db._conn()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT box_id FROM utxo_boxes WHERE owner_address = ? AND spent_at IS NULL",
            (addr,)
        ).fetchone()
        input_box_id = row['box_id']
        
        # Create a transaction with a SPOOFED tx_id
        inputs = [{'box_id': input_box_id, 'spending_proof': 'proof'}]
        outputs = [{'address': addr, 'value_nrtc': 900 * UNIT}]
        tx = {
            'tx_id': '00' * 32,  # FAKE tx_id
            'tx_type': 'transfer',
            'inputs': inputs,
            'outputs': outputs,
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }
        
        # Mempool should reject this or verify the tx_id
        # But currently it accepts ANY tx_id
        result = self.db.mempool_add(tx)
        
        # Check what tx_id was stored
        row = conn.execute(
            "SELECT tx_id FROM utxo_mempool WHERE tx_id = ?",
            ('00' * 32,)
        ).fetchone()
        
        self.assertIsNotNone(row,
            "BUG: Mempool accepted spoofed tx_id without verification")
        
        conn.close()


class TestTransactionLogIncompleteness(unittest.TestCase):
    """Test that transaction logs don't store full transaction data."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_transaction_log_missing_token_data(self):
        """
        LOW: Transaction record doesn't store tokens_json or registers_json.
        
        The utxo_transactions table stores:
        - inputs_json: only box_id
        - outputs_json: only box_id, value_nrtc, owner
        
        Missing:
        - tokens_json (created/destroyed tokens)
        - registers_json (output registers)
        - data_inputs (read-only data inputs)
        
        This means you cannot reconstruct the full transaction from the log.
        Token creation/destruction is not auditable.
        """
        # Create a transaction with tokens
        addr = "RTCsender_address_1234567890abcdef"
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': addr, 'value_nrtc': 1000 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        
        # Get the input box_id
        conn = self.db._conn()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT box_id FROM utxo_boxes WHERE owner_address = ? AND spent_at IS NULL",
            (addr,)
        ).fetchone()
        input_box_id = row['box_id']
        
        # Create a transaction that creates tokens
        inputs = [{'box_id': input_box_id, 'spending_proof': 'proof'}]
        outputs = [{
            'address': addr,
            'value_nrtc': 900 * UNIT,
            'tokens_json': json.dumps([{"token_id": "test_token", "amount": 100}]),
        }]
        tx = {
            'tx_type': 'transfer',
            'inputs': inputs,
            'outputs': outputs,
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }
        
        self.db.apply_transaction(tx, block_height=2)
        
        # Check the transaction record
        row = conn.execute(
            "SELECT inputs_json, outputs_json FROM utxo_transactions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        
        inputs_json = json.loads(row['inputs_json'])
        outputs_json = json.loads(row['outputs_json'])
        
        # Verify token data is NOT in the transaction log
        self.assertNotIn('tokens_json', outputs_json[0],
            "BUG: Token data should be in transaction log for auditability")
        
        conn.close()


if __name__ == '__main__':
    unittest.main()
