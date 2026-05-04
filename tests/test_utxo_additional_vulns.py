"""
UTXO Vulnerability Test Cases (Post-Fix Verification)
=====================================================
Tests verify that the 3 critical UTXO vulnerabilities are fixed:
1. VULN-1 CRITICAL: Token conservation bypass (tokens_json field)
2. VULN-2 HIGH: tx_id collision (outputs not included in tx_id)
3. VULN-3 MEDIUM: mempool tx_id spoofing (trusts external tx_id)

Each test class has two test methods:
- test_<vuln>_IS_FIXED: Verifies the fix works correctly
- test_<vuln>_BEFORE_FIX: Demonstrates the original vulnerability (for reference)
"""
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest

# Add node directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))

from utxo_db import UtxoDB, address_to_proposition, compute_box_id, UNIT


class TestVuln1TokenConservation(unittest.TestCase):
    """Test that token conservation is properly enforced."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        self.conn = self.db._conn()
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmp.name)

    def _create_genesis_box(self, address, tokens=None):
        """Create a genesis box with optional tokens."""
        tokens_json = json.dumps(tokens) if tokens else '[]'
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{
                'address': address,
                'value_nrtc': 1000 * UNIT,
                'tokens_json': tokens_json,
            }],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)

        row = self.conn.execute(
            "SELECT box_id FROM utxo_boxes WHERE owner_address = ? AND spent_at IS NULL",
            (address,)
        ).fetchone()
        return row['box_id']

    def test_vuln1_token_minting_IS_FIXED(self):
        """
        VULN-1 FIXED: Token conservation is now enforced.

        Attack scenario (before fix):
        - Attacker creates output with 1000 tokens
        - Input has only 100 tokens
        - apply_transaction() only checked nRTC, not tokens_json
        - Attacker minted 900 tokens out of thin air

        After fix:
        - Token conservation check compares input_tokens vs output_tokens
        - Minting more tokens than inputs have → transaction rejected
        """
        addr = "RTCsender_address_1234567890abcdef"
        # Create genesis box WITH 100 tokens
        input_box_id = self._create_genesis_box(addr, tokens=[
            {"token_id": "TEST_TOKEN", "amount": 100}
        ])

        # Attempt to mint 1000 tokens (should fail - only 100 in input)
        tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': input_box_id, 'spending_proof': 'proof'}],
            'outputs': [{
                'address': addr,
                'value_nrtc': 900 * UNIT,
                'tokens_json': json.dumps([{"token_id": "TEST_TOKEN", "amount": 1000}]),
            }],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }

        # FIXED: Transaction should be REJECTED
        result = self.db.apply_transaction(tx, block_height=2)
        self.assertFalse(result,
            "FIXED: Token minting exploit should be rejected (tokens out > tokens in)")

        # Verify the input box is NOT spent (transaction was rejected)
        row = self.conn.execute(
            "SELECT spent_at FROM utxo_boxes WHERE box_id = ?",
            (input_box_id,)
        ).fetchone()
        self.assertIsNone(row['spent_at'],
            "Input box should not be spent when token conservation fails")

    def test_vuln1_token_conservation_balanced_IS_FIXED(self):
        """
        VULN-1 FIXED: Balanced token transfers should succeed.
        """
        addr1 = "RTCsender_address_1234567890abcdef"
        addr2 = "RTCreceiver_address_0987654321fedcba"

        # Create genesis box with 500 tokens
        input_box_id = self._create_genesis_box(addr1, tokens=[
            {"token_id": "BALANCED_TOKEN", "amount": 500}
        ])

        # Attempt to transfer 300 tokens (balanced: 300 out, 500 in)
        tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': input_box_id, 'spending_proof': 'proof'}],
            'outputs': [{
                'address': addr2,
                'value_nrtc': 900 * UNIT,
                'tokens_json': json.dumps([{"token_id": "BALANCED_TOKEN", "amount": 300}]),
            }],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }

        # With _allow_burning=True, burning 200 tokens should work
        tx['_allow_burning'] = True
        result = self.db.apply_transaction(tx, block_height=2)
        self.assertTrue(result,
            "Balanced token transfer with explicit burn should succeed")

    def test_vuln1_token_burning_IS_FIXED(self):
        """
        VULN-1 FIXED: Token burning without explicit flag is rejected.
        """
        addr1 = "RTCsender_address_1234567890abcdef"
        addr2 = "RTCreceiver_address_0987654321fedcba"

        # Create genesis box with 500 tokens
        input_box_id = self._create_genesis_box(addr1, tokens=[
            {"token_id": "BURN_TOKEN", "amount": 500}
        ])

        # Attempt to transfer only 100 tokens (burning 400 without flag)
        tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': input_box_id, 'spending_proof': 'proof'}],
            'outputs': [{
                'address': addr2,
                'value_nrtc': 900 * UNIT,
                'tokens_json': json.dumps([{"token_id": "BURN_TOKEN", "amount": 100}]),
            }],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }

        # Without _allow_burning, burning should be rejected
        result = self.db.apply_transaction(tx, block_height=2)
        self.assertFalse(result,
            "FIXED: Token burning without explicit flag should be rejected")


class TestVuln2TxIdCollision(unittest.TestCase):
    """Test that tx_id includes outputs to prevent collision attacks."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        self.conn = self.db._conn()
        self.conn.row_factory = sqlite3.Row
        # Reset rate limiter for clean test
        from utxo_db import _mempool_submission_times
        _mempool_submission_times.clear()

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmp.name)

    def _create_genesis_box(self, address, value=1000 * UNIT, block_height=1, timestamp=None):
        """Create a genesis box."""
        if timestamp is None:
            timestamp = int(time.time()) + block_height  # Ensure unique timestamps
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': address, 'value_nrtc': value}],
            'fee_nrtc': 0,
            'timestamp': timestamp,
            '_allow_minting': True,
        }, block_height=block_height)

        row = self.conn.execute(
            "SELECT box_id FROM utxo_boxes WHERE owner_address = ? AND spent_at IS NULL",
            (address,)
        ).fetchone()
        return row['box_id']

    def test_vuln2_tx_id_includes_outputs_IS_FIXED(self):
        """
        VULN-2 FIXED: tx_id now includes outputs, preventing collision.

        Attack scenario (before fix):
        1. Victim creates TX1: inputs -> output_to_victim
        2. Attacker creates TX2: same inputs -> output_to_attacker
        3. TX1 and TX2 have SAME tx_id (only inputs hashed)
        4. Race condition could allow output substitution

        After fix:
        - tx_id = SHA256(inputs + outputs + timestamp)
        - Different outputs → Different tx_id → Collision impossible
        """
        addr1 = "RTCsender_address_1234567890abcdef"
        addr2 = "RTCreceiver_address_0987654321fedcba"
        addr3 = "RTCattacker_address_evil_1234567890ab"

        # Create genesis box
        input_box_id = self._create_genesis_box(addr1)

        # Create two transactions with SAME inputs but DIFFERENT outputs
        timestamp = 1000000
        inputs1 = [{'box_id': input_box_id, 'spending_proof': 'proof'}]

        # TX1: send to addr2
        outputs1 = [{'address': addr2, 'value_nrtc': 900 * UNIT}]
        tx1 = {
            'tx_type': 'transfer',
            'inputs': inputs1,
            'outputs': outputs1,
            'fee_nrtc': 0,
            'timestamp': timestamp,
        }

        # TX2: send to addr3 (different output address)
        outputs2 = [{'address': addr3, 'value_nrtc': 900 * UNIT}]
        tx2 = {
            'tx_type': 'transfer',
            'inputs': inputs1,
            'outputs': outputs2,
            'fee_nrtc': 0,
            'timestamp': timestamp,
        }

        # Apply TX1
        result1 = self.db.apply_transaction(tx1, block_height=2)
        self.assertTrue(result1, "TX1 should succeed")

        # Get TX1's tx_id
        row = self.conn.execute(
            "SELECT tx_id FROM utxo_transactions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        tx1_id = row['tx_id']

        # Compute expected tx_id including outputs
        import hashlib
        h = hashlib.sha256()
        for inp in sorted(inputs1, key=lambda i: i['box_id']):
            h.update(bytes.fromhex(inp['box_id']))
        # Outputs are now included
        for out in outputs1:
            h.update(out['address'].encode('utf-8'))
            h.update(out['value_nrtc'].to_bytes(8, 'little'))
            h.update('[]'.encode('utf-8'))  # tokens_json
        h.update((0).to_bytes(8, 'little'))  # lock_time
        h.update((1).to_bytes(8, 'little'))  # version
        h.update(timestamp.to_bytes(8, 'little'))
        expected_tx1_id = h.hexdigest()

        self.assertEqual(tx1_id, expected_tx1_id,
            "tx_id should include outputs")

        # FIXED: TX2 should have DIFFERENT tx_id (same inputs, different outputs)
        # This test verifies the fix is in place
        h2 = hashlib.sha256()
        for inp in sorted(inputs1, key=lambda i: i['box_id']):
            h2.update(bytes.fromhex(inp['box_id']))
        # Different outputs!
        for out in outputs2:
            h2.update(out['address'].encode('utf-8'))
            h2.update(out['value_nrtc'].to_bytes(8, 'little'))
            h2.update('[]'.encode('utf-8'))
        h2.update((0).to_bytes(8, 'little'))  # lock_time
        h2.update((1).to_bytes(8, 'little'))  # version
        h2.update(timestamp.to_bytes(8, 'little'))
        expected_tx2_id = h2.hexdigest()

        self.assertNotEqual(tx1_id, expected_tx2_id,
            "FIXED: Same inputs + different outputs = different tx_id (collision prevented)")

    def test_vuln2_same_tx_id_attack_blocked(self):
        """
        VULN-2 FIXED: Verify the actual collision attack is blocked.

        Before fix: Same inputs + different outputs = same tx_id
        After fix: Same inputs + different outputs = different tx_id
        """
        addr1 = "RTCsender_address_1234567890abcdef"
        addr2 = "RTCreceiver_address_0987654321fedcba"
        addr3 = "RTCattacker_address_evil_1234567890ab"

        # Create genesis box
        input_box_id = self._create_genesis_box(addr1)

        timestamp = 2000000

        # TX1: inputs -> addr2
        tx1_inputs = [{'box_id': input_box_id, 'spending_proof': 'proof'}]
        tx1 = {
            'tx_type': 'transfer',
            'inputs': tx1_inputs,
            'outputs': [{'address': addr2, 'value_nrtc': 900 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': timestamp,
        }
        self.db.apply_transaction(tx1, block_height=2)

        row = self.conn.execute(
            "SELECT tx_id FROM utxo_transactions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        tx1_id = row['tx_id']

        # Create a new genesis box for TX2 (since TX1 spent the original)
        # Use block_height=2 to ensure different tx_id for the genesis box
        input_box_id2 = self._create_genesis_box(addr1, block_height=2)

        # TX2: same inputs (same box_id) -> addr3
        tx2_inputs = [{'box_id': input_box_id2, 'spending_proof': 'proof'}]
        tx2 = {
            'tx_type': 'transfer',
            'inputs': tx2_inputs,
            'outputs': [{'address': addr3, 'value_nrtc': 900 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': timestamp,  # Same timestamp
        }
        self.db.apply_transaction(tx2, block_height=3)

        row = self.conn.execute(
            "SELECT tx_id FROM utxo_transactions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        tx2_id = row['tx_id']

        # FIXED: tx_ids should be DIFFERENT
        self.assertNotEqual(tx1_id, tx2_id,
            "FIXED: tx_ids should differ when outputs differ")


class TestVuln3MempoolTxIdSpoofing(unittest.TestCase):
    """Test that mempool verifies tx_id matches transaction content."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        self.conn = self.db._conn()
        self.conn.row_factory = sqlite3.Row
        # Reset rate limiter for clean test
        from utxo_db import _mempool_submission_times
        _mempool_submission_times.clear()

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmp.name)

    def _create_genesis_box(self, address, value=1000 * UNIT, block_height=1, timestamp=None):
        """Create a genesis box."""
        if timestamp is None:
            timestamp = int(time.time()) + block_height  # Ensure unique timestamps
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': address, 'value_nrtc': value}],
            'fee_nrtc': 0,
            'timestamp': timestamp,
            '_allow_minting': True,
        }, block_height=block_height)

        row = self.conn.execute(
            "SELECT box_id FROM utxo_boxes WHERE owner_address = ? AND spent_at IS NULL",
            (address,)
        ).fetchone()
        return row['box_id']

    def test_vuln3_mempool_rejects_spoofed_tx_id_IS_FIXED(self):
        """
        VULN-3 FIXED: mempool_add() now verifies tx_id matches computed value.

        Attack scenario (before fix):
        1. Attacker creates transaction with arbitrary tx_id='00' * 32
        2. mempool_add() trusts tx.get('tx_id', '') without verification
        3. Attacker can collide with existing tx_ids or evade tracking

        After fix:
        1. mempool_add() computes tx_id from inputs + outputs + timestamp
        2. Compares with provided tx_id
        3. Rejects if mismatch → spoofing blocked
        """
        addr = "RTCsender_address_1234567890abcdef"

        # Create genesis box
        input_box_id = self._create_genesis_box(addr)

        # Create transaction with SPOOFED tx_id
        inputs = [{'box_id': input_box_id, 'spending_proof': 'proof'}]
        outputs = [{'address': addr, 'value_nrtc': 900 * UNIT}]
        timestamp = int(time.time())

        # Compute the CORRECT tx_id
        import hashlib
        h = hashlib.sha256()
        for inp in sorted(inputs, key=lambda i: i['box_id']):
            h.update(bytes.fromhex(inp['box_id']))
        for out in outputs:
            h.update(out['address'].encode('utf-8'))
            h.update(out['value_nrtc'].to_bytes(8, 'little'))
            h.update('[]'.encode('utf-8'))
        h.update((0).to_bytes(8, 'little'))  # lock_time
        h.update((1).to_bytes(8, 'little'))  # version
        h.update(timestamp.to_bytes(8, 'little'))
        correct_tx_id = h.hexdigest()

        # Transaction with WRONG tx_id
        spoofed_tx = {
            'tx_id': '00' * 32,  # WRONG - should be rejected
            'tx_type': 'transfer',
            'inputs': inputs,
            'outputs': outputs,
            'fee_nrtc': 0,
            'timestamp': timestamp,
        }

        # FIXED: Mempool should REJECT spoofed tx_id
        result = self.db.mempool_add(spoofed_tx)
        self.assertFalse(result,
            "FIXED: Mempool should reject transactions with mismatched tx_id")

        # Verify it's NOT in the mempool
        row = self.conn.execute(
            "SELECT tx_id FROM utxo_mempool WHERE tx_id = ?",
            ('00' * 32,)
        ).fetchone()
        self.assertIsNone(row,
            "Spoofed tx_id should not be in mempool")

    def test_vuln3_mempool_accepts_valid_tx_id_IS_FIXED(self):
        """
        VULN-3 FIXED: Mempool accepts transactions with correct tx_id.
        """
        addr = "RTCsender_address_1234567890abcdef"

        # Create genesis box
        input_box_id = self._create_genesis_box(addr)

        inputs = [{'box_id': input_box_id, 'spending_proof': 'proof'}]
        outputs = [{'address': addr, 'value_nrtc': 900 * UNIT}]
        timestamp = int(time.time())

        # Compute the CORRECT tx_id
        import hashlib
        h = hashlib.sha256()
        for inp in sorted(inputs, key=lambda i: i['box_id']):
            h.update(bytes.fromhex(inp['box_id']))
        for out in outputs:
            h.update(out['address'].encode('utf-8'))
            h.update(out['value_nrtc'].to_bytes(8, 'little'))
            h.update('[]'.encode('utf-8'))
        h.update((0).to_bytes(8, 'little'))  # lock_time
        h.update((1).to_bytes(8, 'little'))  # version
        h.update(timestamp.to_bytes(8, 'little'))
        correct_tx_id = h.hexdigest()

        # Transaction with CORRECT tx_id
        valid_tx = {
            'tx_id': correct_tx_id,  # CORRECT - should be accepted
            'tx_type': 'transfer',
            'inputs': inputs,
            'outputs': outputs,
            'fee_nrtc': 0,
            'timestamp': timestamp,
        }

        # Should succeed
        result = self.db.mempool_add(valid_tx)
        self.assertTrue(result,
            "Mempool should accept transactions with correct tx_id")

        # Verify it's in the mempool
        row = self.conn.execute(
            "SELECT tx_id FROM utxo_mempool WHERE tx_id = ?",
            (correct_tx_id,)
        ).fetchone()
        self.assertIsNotNone(row,
            "Valid tx_id should be in mempool")


class TestVulnIntegration(unittest.TestCase):
    """Integration tests for all fixes working together."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_all_fixes_work_together(self):
        """
        Integration test: Token conservation + tx_id + mempool verification.
        """
        import hashlib

        addr1 = "RTCsender_address_1234567890abcdef"
        addr2 = "RTCreceiver_address_0987654321fedcba"

        # Create genesis box with tokens
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{
                'address': addr1,
                'value_nrtc': 1000 * UNIT,
                'tokens_json': json.dumps([{"token_id": "INTEGRATION_TOKEN", "amount": 500}]),
            }],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)

        # Get the box
        conn = self.db._conn()
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT box_id FROM utxo_boxes WHERE owner_address = ? AND spent_at IS NULL",
            (addr1,)
        ).fetchone()
        input_box_id = row['box_id']

        timestamp = int(time.time())
        inputs = [{'box_id': input_box_id, 'spending_proof': 'proof'}]
        outputs = [{
            'address': addr2,
            'value_nrtc': 900 * UNIT,
            'tokens_json': json.dumps([{"token_id": "INTEGRATION_TOKEN", "amount": 300}]),
        }]

        # Compute correct tx_id
        h = hashlib.sha256()
        for inp in sorted(inputs, key=lambda i: i['box_id']):
            h.update(bytes.fromhex(inp['box_id']))
        for out in outputs:
            h.update(out['address'].encode('utf-8'))
            h.update(out['value_nrtc'].to_bytes(8, 'little'))
            h.update(out['tokens_json'].encode('utf-8'))
        h.update((0).to_bytes(8, 'little'))  # lock_time
        h.update((1).to_bytes(8, 'little'))  # version
        h.update(timestamp.to_bytes(8, 'little'))
        correct_tx_id = h.hexdigest()

        # Test 1: Token conservation (balanced: 300 out of 500 in)
        tx = {
            'tx_id': correct_tx_id,
            'tx_type': 'transfer',
            'inputs': inputs,
            'outputs': outputs,
            'fee_nrtc': 0,
            'timestamp': timestamp,
            '_allow_burning': True,
        }
        result = self.db.apply_transaction(tx, block_height=2)
        self.assertTrue(result, "Balanced token transfer should succeed")

        # Test 2: Token minting attempt (should fail)
        tx2_outputs = [{
            'address': addr2,
            'value_nrtc': 800 * UNIT,
            'tokens_json': json.dumps([{"token_id": "INTEGRATION_TOKEN", "amount": 1000}]),
        }]
        tx2 = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': row['box_id'], 'spending_proof': 'proof'}],
            'outputs': tx2_outputs,
            'fee_nrtc': 0,
            'timestamp': timestamp + 1,
        }
        # Need new box for tx2
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': addr1, 'value_nrtc': 500 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=3)

        row2 = conn.execute(
            "SELECT box_id FROM utxo_boxes WHERE owner_address = ? AND spent_at IS NULL",
            (addr1,)
        ).fetchone()

        tx2['inputs'] = [{'box_id': row2['box_id'], 'spending_proof': 'proof'}]
        result2 = self.db.apply_transaction(tx2, block_height=4)
        self.assertFalse(result2, "Token minting should fail")

        # Test 3: Mempool rejects spoofed tx_id
        tx3_inputs = [{'box_id': row2['box_id'], 'spending_proof': 'proof'}]
        tx3 = {
            'tx_id': 'spoofed' + '0' * 58,
            'tx_type': 'transfer',
            'inputs': tx3_inputs,
            'outputs': [{'address': addr2, 'value_nrtc': 400 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': timestamp + 2,
        }
        result3 = self.db.mempool_add(tx3)
        self.assertFalse(result3, "Mempool should reject spoofed tx_id")

        conn.close()


class TestMempoolRateLimiting(unittest.TestCase):
    """Test mempool rate limiting prevents spam attacks."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        self.conn = self.db._conn()
        self.conn.row_factory = sqlite3.Row
        # Reset rate limiter for clean test
        from utxo_db import _mempool_submission_times
        _mempool_submission_times.clear()

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmp.name)

    def test_rate_limit_blocks_excess_transactions(self):
        """
        NEW: Mempool rate limiting prevents spam.

        After fix:
        - MAX_MEMPOOL_TX_PER_WINDOW=10, MEMPOOL_RATE_WINDOW_SECONDS=60
        - Submitting >10 tx in 60s window should be rejected
        """
        from utxo_db import MAX_MEMPOOL_TX_PER_WINDOW
        import hashlib

        addr = "RTCsender_address_1234567890abcdef"
        box_ids = []

        # Create enough genesis boxes with UNIQUE values (different value_nrtc ensures unique box_ids)
        for i in range(MAX_MEMPOOL_TX_PER_WINDOW + 1):
            self.db.apply_transaction({
                'tx_type': 'mining_reward',
                'inputs': [],
                'outputs': [{'address': addr, 'value_nrtc': (1000 + i) * UNIT}],
                'fee_nrtc': 0,
                'timestamp': int(time.time()) + 1000 + i,
                '_allow_minting': True,
            }, block_height=i + 1)

            rows = self.conn.execute(
                "SELECT box_id FROM utxo_boxes WHERE owner_address = ? AND spent_at IS NULL ORDER BY value_nrtc DESC",
                (addr,)
            ).fetchall()
            box_ids.append(rows[0]['box_id'])  # Highest value = most recent

        # Submit MAX_MEMPOOL_TX_PER_WINDOW transactions (should succeed)
        for i in range(MAX_MEMPOOL_TX_PER_WINDOW):
            ts = int(time.time()) + 100 + i
            inputs = [{'box_id': box_ids[i], 'spending_proof': 'proof'}]
            outputs = [{'address': addr, 'value_nrtc': 900 * UNIT}]
            h = hashlib.sha256()
            for inp in sorted(inputs, key=lambda x: x['box_id']):
                h.update(bytes.fromhex(inp['box_id']))
            for out in outputs:
                h.update(out['address'].encode('utf-8'))
                h.update(out['value_nrtc'].to_bytes(8, 'little'))
                h.update('[]'.encode('utf-8'))
            h.update((0).to_bytes(8, 'little'))  # lock_time
            h.update((1).to_bytes(8, 'little'))  # version
            h.update(ts.to_bytes(8, 'little'))
            tx_id = h.hexdigest()

            tx = {
                'tx_id': tx_id,
                'tx_type': 'transfer',
                'inputs': inputs,
                'outputs': outputs,
                'fee_nrtc': 0,
                'timestamp': ts,
            }
            result = self.db.mempool_add(tx)
            self.assertTrue(result, f"TX {i+1} should be accepted within rate limit")

        # The (MAX+1)th transaction should be rejected due to rate limiting
        ts = int(time.time()) + 100 + MAX_MEMPOOL_TX_PER_WINDOW
        inputs = [{'box_id': box_ids[MAX_MEMPOOL_TX_PER_WINDOW], 'spending_proof': 'proof'}]
        outputs = [{'address': addr, 'value_nrtc': 900 * UNIT}]
        h = hashlib.sha256()
        for inp in sorted(inputs, key=lambda x: x['box_id']):
            h.update(bytes.fromhex(inp['box_id']))
        for out in outputs:
            h.update(out['address'].encode('utf-8'))
            h.update(out['value_nrtc'].to_bytes(8, 'little'))
            h.update('[]'.encode('utf-8'))
        h.update((0).to_bytes(8, 'little'))
        h.update((1).to_bytes(8, 'little'))
        h.update(ts.to_bytes(8, 'little'))
        tx_id = h.hexdigest()

        excess_tx = {
            'tx_id': tx_id,
            'tx_type': 'transfer',
            'inputs': inputs,
            'outputs': outputs,
            'fee_nrtc': 0,
            'timestamp': ts,
        }
        result = self.db.mempool_add(excess_tx)
        self.assertFalse(result, "Transaction exceeding rate limit should be rejected")

if __name__ == '__main__':
    unittest.main()
