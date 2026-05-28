#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
[UTXO-BUG] compute_state_root() used 'little'-endian for count_bytes (line 861)
================================================================================

VULN: utxo_db.py — count_bytes = len(rows).to_bytes(8, 'little')

All other integer encodings in the module use big-endian (network byte order):
  - compute_box_id():  value_nrtc.to_bytes(8, 'big'),
                       creation_height.to_bytes(8, 'big'),
                       output_index.to_bytes(2, 'big')
  - compute_tx_id():   timestamp.to_bytes(8, 'big')
  - Module docstring:  "Uses big-endian (network byte order) for integer
                        encodings … ensuring cross-platform deterministic hashing"

The Merkle state root leaf hash was:
    SHA256( count_bytes_LE || leaf_json )

When fixed to big-endian, the state root changes for the same UTXO set —
causing a consensus fork between old and new nodes.

Impact:
  - Medium: Merkle state root divergence between nodes running old vs fixed code
  - The docstring claims "All nodes with the same UTXO set produce the same root"
    — this is only true while ALL nodes share the same endianness bug.

Fix: change 'little' to 'big' in count_bytes = len(rows).to_bytes(8, ...)

Bot: Ivan-LB
"""

import hashlib
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UtxoDB, UNIT, MAX_COINBASE_OUTPUT_NRTC


def _mine_box(db: UtxoDB, value_rtc: float, address: str,
              block_height: int = 1) -> bool:
    nrtc = int(value_rtc * UNIT)
    return db.apply_transaction({
        'tx_type': 'mining_reward', 'inputs': [],
        'outputs': [{'address': address, 'value_nrtc': nrtc}],
        'fee_nrtc': 0, 'timestamp': int(time.time()),
        '_allow_minting': True,
    }, block_height=block_height)


def _compute_state_root_with_endian(db: UtxoDB, endian: str) -> str:
    """Compute state root using either 'little' (buggy) or 'big' (correct)."""
    conn = db._conn()
    try:
        rows = conn.execute(
            """SELECT box_id, value_nrtc, proposition, owner_address,
                      creation_height, transaction_id, output_index,
                      tokens_json, registers_json
               FROM utxo_boxes WHERE spent_at IS NULL ORDER BY box_id ASC"""
        ).fetchall()
        if not rows:
            return hashlib.sha256(b"empty").hexdigest()
        count_bytes = len(rows).to_bytes(8, endian)
        hashes = []
        for row in rows:
            leaf = {k: row[k] for k in (
                'box_id', 'value_nrtc', 'proposition', 'owner_address',
                'creation_height', 'transaction_id', 'output_index',
                'tokens_json', 'registers_json'
            )}
            leaf_bytes = json.dumps(leaf, sort_keys=True, separators=(',', ':')).encode()
            hashes.append(hashlib.sha256(count_bytes + leaf_bytes).digest())
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashlib.sha256(b'\x01' + hashes[-1]).digest())
            hashes = [hashlib.sha256(hashes[i] + hashes[i+1]).digest()
                      for i in range(0, len(hashes), 2)]
        return hashes[0].hex()
    finally:
        conn.close()


class TestStateRootEndianness(unittest.TestCase):
    """Demonstrate endian inconsistency bug in compute_state_root()."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_count_bytes_endian_divergence(self):
        """little vs big count_bytes are always different (except count=0)."""
        # For any count > 0, LE and BE differ because the non-zero byte lands
        # at opposite ends of the 8-byte representation.
        for count in (1, 2, 5, 100, 10_000):
            le = count.to_bytes(8, 'little')
            be = count.to_bytes(8, 'big')
            self.assertNotEqual(le, be,
                f"count={count}: LE={le.hex()} must differ from BE={be.hex()}")
            print(f"\n  count={count:>5}: little={le.hex()}  (old buggy)")
            print(f"  {'':>10}  big   ={be.hex()}  (correct)")
        print("\n  ⚠  Every leaf hash is prefixed with count_bytes → all roots diverge.")

    def test_state_root_diverges_for_two_boxes(self):
        """Same UTXO set → different root with little vs big count_bytes."""
        ok = _mine_box(self.db, 10, 'alice', block_height=1)
        self.assertTrue(ok)
        ok = _mine_box(self.db, 20, 'bob',   block_height=2)
        self.assertTrue(ok)

        root_little = _compute_state_root_with_endian(self.db, 'little')
        root_big    = _compute_state_root_with_endian(self.db, 'big')

        print(f"\n  Root (old little-endian): {root_little}")
        print(f"  Root (fix big-endian):    {root_big}")

        self.assertNotEqual(root_little, root_big,
            "With 2 boxes, little-endian and big-endian count_bytes must produce "
            "different state roots — confirming the consensus-divergence risk.")

    def test_fixed_code_uses_big_endian(self):
        """After fix, compute_state_root() must match the big-endian reference."""
        for i in range(5):
            ok = _mine_box(self.db, 1 + i, f'node_{i}', block_height=i + 1)
            self.assertTrue(ok, f"box {i}")

        root_actual    = self.db.compute_state_root()
        root_big_ref   = _compute_state_root_with_endian(self.db, 'big')
        root_little_ref = _compute_state_root_with_endian(self.db, 'little')

        print(f"\n  Fixed code root:           {root_actual}")
        print(f"  Big-endian reference:      {root_big_ref}")
        print(f"  Little-endian (old buggy): {root_little_ref}")

        self.assertEqual(root_actual, root_big_ref,
            "After fix, compute_state_root() must match the big-endian reference. "
            "If this fails, the fix was not applied.")
        self.assertNotEqual(root_actual, root_little_ref,
            "Fixed code must NOT match the old little-endian computation.")


if __name__ == '__main__':
    unittest.main(verbosity=2)
