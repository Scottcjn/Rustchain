# SPDX-License-Identifier: MIT
"""
C3: Mempool output injection via A3 garbage fields — adversarial
VULN: A3 found mempool_add stores json.dumps(tx) with no field whitelist.
  The /utxo/mempool endpoint returns raw candidates. Combined, an attacker
  injects arbitrary JSON into mempool responses that miners, explorers,
  and monitoring tools consume.

Impact: Attacker-controlled fields in mempool output. Fake status flags
  (e.g. _allow_minting: True), monitoring confusion, poisoned explorer
  data, and potential manipulation of miner block-candidate selection.

Fix: Whitelist tx fields in mempool_add() storage AND sanitize mempool
  response in the endpoint layer.
"""
import unittest
import tempfile
import os
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utxo_db import UtxoDB, UNIT


class TestMempoolOutputInjection(unittest.TestCase):
    """C3: Mempool output injection via garbage fields."""

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
            '_allow_minting': True,
        }, block_height=1)
        boxes = self.db.get_unspent_for_address('alice')
        self.box_id = boxes[0]['box_id']

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_c3_mempool_output_injection(self):
        """C3: Injected fields survive into /utxo/mempool output."""
        # Inject a tx with garbage payloads
        self.db.mempool_add({
            'tx_id': 'inj_c3',
            'tx_type': 'transfer',
            'inputs': [{'box_id': self.box_id, 'spending_proof': 'sig'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            # Garbage fields (this is what /utxo/mempool returns)
            '_allow_minting': True,
            'priority': 'critical',
            'fake_from': 'system',
            'nested_spam': {'a': ['x', 'y'] * 100},
        })

        # What /utxo/mempool returns
        candidates = self.db.mempool_get_block_candidates(max_count=50)
        injected_tx = None
        for c in candidates:
            if c['tx_id'] == 'inj_c3':
                injected_tx = c
                break

        self.assertIsNotNone(injected_tx, "injected tx should be in mempool")

        extra_keys = set(injected_tx.keys()) - {
            'tx_id', 'tx_type', 'inputs', 'outputs', 'fee_nrtc',
            'data_inputs', 'timestamp'
        }
        print(f"\n[C3] Extra keys in mempool output: {extra_keys}")

        if extra_keys:
            print(f"[C3] ✅ VULN: {len(extra_keys)} injected fields leaked to mempool output")
            for k in extra_keys:
                print(f"  {k}: {str(injected_tx[k])[:80]}")
            print("[C3] Miners/explorers consuming /utxo/mempool see attacker-controlled data")
            print("[C3] Fix: whitelist fields at store AND sanitize at endpoint output")

        self.assertGreater(len(extra_keys), 0,
            "C3: Extra keys should appear in mempool output")


if __name__ == '__main__':
    unittest.main(verbosity=2)
