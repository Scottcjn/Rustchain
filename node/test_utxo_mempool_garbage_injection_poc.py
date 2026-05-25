#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
A3: mempool_add() stores full tx dict with no field/size validation
===================================================================
VULN: tx_data_json at utxo_db.py:1001 stores json.dumps(tx) with the
full caller-provided dict — no field whitelist, no size limit.

Attack vectors:
1. Storage bloat: 50KB+ garbage per tx × 9999 max pool = ~500MB
2. Response bloat: /utxo/mempool endpoint returns ALL injected fields
3. Downstream confusion: _allow_minting, nested structures, binary payloads

Fix: Strip non-essential fields before json.dumps(). Add MAX_TX_JSON_BYTES limit.
     Only persist: tx_type, inputs, outputs, data_inputs, fee_nrtc, timestamp.

Bot: @waefrebeorn
"""

import unittest
import tempfile
import os
import time
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UtxoDB, UNIT


class TestMempoolTxJsonInjection(unittest.TestCase):
    """mempool stores unvalidated tx dict — garbage injection."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _setup_box(self):
        self.db.apply_transaction({
            'tx_type': 'mining_reward', 'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0, 'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)
        return self.db.get_unspent_for_address('alice')[0]['box_id']

    def test_garbage_fields_survive_roundtrip(self):
        """Injected garbage fields persist through store→retrieve."""
        bid = self._setup_box()
        garbage = 'X' * 10000
        tx = {
            'tx_id': 'inj1',
            'tx_type': 'transfer',
            'inputs': [{'box_id': bid, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'garbage': garbage,
            '_allow_minting': True,
            'nested_spam': {'key': ['a', 'b'] * 1000},
        }
        raw_size = len(json.dumps(tx))
        ok = self.db.mempool_add(tx)
        self.assertTrue(ok, "mempool_add accepted tx with garbage fields")

        candidates = self.db.mempool_get_block_candidates()
        self.assertEqual(len(candidates), 1)
        tx_out = candidates[0]

        self.assertIn('garbage', tx_out,
            "BUG: injected 'garbage' field survived round-trip through mempool")
        self.assertIn('_allow_minting', tx_out,
            "BUG: internal flag '_allow_minting' leaked through mempool")
        self.assertIn('nested_spam', tx_out,
            "BUG: nested injected data survived round-trip")
        self.assertEqual(tx_out['garbage'], garbage,
            "BUG: full 10KB garbage payload intact")
        print(f"[A3] Input tx JSON: {raw_size} bytes")
        print(f"[A3] Output tx JSON: {len(json.dumps(tx_out))} bytes")
        print(f"[A3] Extra keys found: {set(tx_out.keys()) - {'tx_id', 'tx_type', 'inputs', 'outputs', 'fee_nrtc'}}")

    def test_mempool_storage_bloat(self):
        """Multiple txs with garbage → mempool storage bloat."""
        bid = self._setup_box()
        # Create 10 boxes so we can add 10 mempool txs
        for i in range(10):
            self.db.apply_transaction({
                'tx_type': 'mining_reward', 'inputs': [],
                'outputs': [{'address': f'bulk_{i}', 'value_nrtc': 1}],
                'fee_nrtc': 0, 'timestamp': int(time.time()) + i,
                '_allow_minting': True,
            }, block_height=i + 2)

        total_payload = 0
        for i in range(10):
            boxes = self.db.get_unspent_for_address(f'bulk_{i}')
            if not boxes:
                continue
            bid2 = boxes[0]['box_id']
            payload = {'x': 'Y' * 5000}
            tx = {
                'tx_id': f'bloat_{i}',
                'tx_type': 'transfer',
                'inputs': [{'box_id': bid2, 'spending_proof': 'sig'}],
                'outputs': [{'address': 'bob', 'value_nrtc': 1}],
                'fee_nrtc': 0,
                **payload,
            }
            self.db.mempool_add(tx)
            total_payload += len(json.dumps(tx))

        candidates = self.db.mempool_get_block_candidates(max_count=100)
        retrieved_size = sum(len(json.dumps(c)) for c in candidates)
        print(f"[A3 bloat] Stored {len(candidates)} txs, "
              f"total payload ~{total_payload} bytes, "
              f"retrieved ~{retrieved_size} bytes")
        print(f"[A3 bloat] At 9999 max pool × 50KB = ~{9999 * 50_000 / 1024:.0f}KB")

    def test_response_size_via_mempool_endpoint(self):
        """Simulate the /utxo/mempool endpoint returning attacker data."""
        bid = self._setup_box()
        tx = {
            'tx_id': 'resp_bloat',
            'tx_type': 'transfer',
            'inputs': [{'box_id': bid, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        }
        self.db.mempool_add(tx)
        candidates = self.db.mempool_get_block_candidates(max_count=50)

        # Simulate response
        response = {'count': len(candidates), 'transactions': candidates}
        resp_size = len(json.dumps(response))
        print(f"[A3 endpoint] /utxo/mempool response: {resp_size} bytes "
              f"({resp_size / 1024:.1f}KB) for {len(candidates)} tx(s)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
