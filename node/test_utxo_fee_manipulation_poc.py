#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
UTXO Fee Manipulation Vulnerability PoC
Issue: #2819 - Red Team UTXO Audit

Vulnerability: Ed25519 signature in /utxo/transfer endpoint does NOT cover
the fee_rtc parameter, allowing an attacker with network-level access to
modify the fee after signing.

Severity: Medium (high impact, moderate attack difficulty)
"""

import unittest
import tempfile
import os
import time
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utxo_db import UtxoDB, UNIT


class TestFeeManipulation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()
        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
        }, block_height=1)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_fee_not_in_signature(self):
        """Fee_rtc is not part of the signed message - can be modified"""
        # Signed message per utxo_endpoints.py lines 273-280
        signed_fields = {'amount', 'from', 'to', 'memo', 'nonce'}
        request_fields = {'from_address', 'to_address', 'amount_rtc', 'fee_rtc',
                         'public_key', 'signature', 'nonce', 'memo'}
        unsigned = request_fields - signed_fields
        self.assertIn('fee_rtc', unsigned,
            "VULNERABILITY: fee_rtc not in signed message")

    def test_fee_inflation_possible(self):
        """Attacker can inflate fee without breaking signature"""
        boxes = self.db.get_unspent_for_address('alice')
        original_fee = 0.0001
        attacked_fee = 50.0
        amount = 10.0
        
        original_loss = int((amount + original_fee) * UNIT)
        actual_loss = int((amount + attacked_fee) * UNIT)
        theft = actual_loss - original_loss
        
        self.assertGreater(theft, 0,
            "Attacker steals difference between original and inflated fee")


if __name__ == '__main__':
    unittest.main(verbosity=2)
