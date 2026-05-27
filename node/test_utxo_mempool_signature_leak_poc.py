#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
C4: /utxo/mempool leaks spending_proof (Ed25519 signatures) and full calldata
VULN: utxo_endpoints.py:316-319 returns mempool_get_block_candidates() raw
  output, which includes the full tx dict stored via json.dumps(tx) at
  utxo_db.py:1001. This includes spending_proof (Ed25519 signature) for
  every input, exposing user signing keys and transaction data.

Impact: Any caller can harvest active user signatures from the mempool.
  While Ed25519 signatures are message-bound, full calldata exposure
  enables transaction analysis, frontrunning, and signature collection
  for offline cryptanalysis.

Fix: Strip spending_proof fields from mempool response, or only expose
  tx_id + fee + summary, not the raw calldata.
"""
import unittest
import tempfile
import os
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utxo_db import UtxoDB, UNIT


class TestMempoolSignatureLeak(unittest.TestCase):
    """C4: Mempool endpoint leaks signatures."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

        # Create a UTXO and add it to mempool with a realistic signature
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

        self.test_signature = "ab" * 32 + "cd" * 32  # 128-byte hex Ed25519 sig
        self.test_pubkey = "ef" * 32  # 32-byte hex pubkey
        self.test_nonce = "1234567890"

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_c4_mempool_signature_leak(self):
        """C4: Mempool get_block_candidates returns spending_proof."""
        # Add a tx with a real-looking signature
        self.db.mempool_add({
            'tx_id': 'signed_tx_c4',
            'tx_type': 'transfer',
            'inputs': [{
                'box_id': self.box_id,
                'spending_proof': self.test_signature,
            }],
            'outputs': [{'address': 'bob', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
        })

        # This is what /utxo/mempool endpoint returns
        candidates = self.db.mempool_get_block_candidates(max_count=50)

        self.assertGreater(len(candidates), 0, "mempool should have candidates")
        first_tx = candidates[0]

        has_spending_proof = False
        for inp in first_tx.get('inputs', []):
            if 'spending_proof' in inp:
                has_spending_proof = True
                sp = inp['spending_proof']
                print(f"[C4] spending_proof exposed: {sp[:32]}...{sp[-8:]}")
                print(f"[C4] Length: {len(sp)} hex chars ({len(sp)//2} bytes)")

        print(f"\n[C4] Full candidate tx keys: {list(first_tx.keys())}")
        print(f"[C4] Inputs contain spending_proof: {has_spending_proof}")

        if has_spending_proof:
            print(f"[C4] ✅ VULN CONFIRMED: spending_proof leaked in mempool output")
            print("[C4] Every /utxo/mempool caller sees full calldata + signatures")
            print("[C4] Fix: strip spending_proof from mempool response, or")
            print("[C4] only expose tx_id, fee, and summary info")

        self.assertTrue(has_spending_proof,
            "C4: spending_proof should be present in mempool output")


if __name__ == '__main__':
    unittest.main(verbosity=2)
