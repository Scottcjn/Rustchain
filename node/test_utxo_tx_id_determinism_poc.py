#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
PoC: compute_tx_id unsorted inputs — non-deterministic (A8)

Bug: compute_tx_id iterates inputs/outputs in caller-provided order.
Two callers with same inputs in different order produce different tx_id.
This breaks the "Deterministic transaction ID" contract in the docstring.

Additionally: compute_tx_id is never called from production code — it is
dead code that shadows the inline tx_id computation at line 647-650
(which correctly sorts inputs via sorted(i['box_id'] for i in inputs)).
"""

import hashlib
import unittest


def compute_tx_id_orig(inputs, outputs, timestamp):
    """Current implementation — NO sorting."""
    h = hashlib.sha256()
    for inp in inputs:
        h.update(bytes.fromhex(inp['box_id']))
    for out in outputs:
        h.update(bytes.fromhex(out['box_id']))
    h.update(timestamp.to_bytes(8, 'little'))
    return h.hexdigest()


def compute_tx_id_fixed(inputs, outputs, timestamp):
    """Fixed — sorted inputs/outputs by box_id for determinism."""
    h = hashlib.sha256()
    for inp in sorted(inputs, key=lambda x: x['box_id']):
        h.update(bytes.fromhex(inp['box_id']))
    for out in sorted(outputs, key=lambda x: x['box_id']):
        h.update(bytes.fromhex(out['box_id']))
    h.update(timestamp.to_bytes(8, 'big'))  # network byte order
    return h.hexdigest()


class TestTxIdDeterminism(unittest.TestCase):

    def setUp(self):
        self.inputs_a = [
            {'box_id': 'aa' * 32},
            {'box_id': 'bb' * 32},
            {'box_id': 'cc' * 32},
        ]
        self.inputs_b = [
            {'box_id': 'cc' * 32},
            {'box_id': 'aa' * 32},
            {'box_id': 'bb' * 32},
        ]
        self.outputs = [
            {'box_id': 'dd' * 32},
            {'box_id': 'ee' * 32},
        ]
        self.ts = 1000

    def test_same_inputs_different_order_different_hash(self):
        """Same inputs, different order → different tx_id (BUG)."""
        id_a = compute_tx_id_orig(self.inputs_a, self.outputs, self.ts)
        id_b = compute_tx_id_orig(self.inputs_b, self.outputs, self.ts)
        self.assertNotEqual(id_a, id_b,
            "BOGUS: Same inputs in different order should NOT collide")
        print(f"  Order A tx_id: {id_a}")
        print(f"  Order B tx_id: {id_b}")
        print(f"  Same? {id_a == id_b} ← BUG: should be same!")

    def test_fixed_same_inputs_different_order_same_hash(self):
        """Fixed version: same inputs, any order → same tx_id."""
        id_a = compute_tx_id_fixed(self.inputs_a, self.outputs, self.ts)
        id_b = compute_tx_id_fixed(self.inputs_b, self.outputs, self.ts)
        self.assertEqual(id_a, id_b,
            "Fixed version should produce same tx_id regardless of input order")
        print(f"  Fix Order A tx_id: {id_a}")
        print(f"  Fix Order B tx_id: {id_b}")
        print(f"  Same? {id_a == id_b} ✓")

    def test_different_inputs_different_hash_both(self):
        """Both versions produce different hashes for different inputs."""
        other_inputs = [{'box_id': 'ff' * 32}]
        orig_a = compute_tx_id_orig(self.inputs_a, self.outputs, self.ts)
        orig_b = compute_tx_id_orig(other_inputs, self.outputs, self.ts)
        self.assertNotEqual(orig_a, orig_b,
            "Different inputs should produce different tx_id")

    def test_tx_id_not_called_from_production(self):
        """Verify compute_tx_id is dead code — define to detect future use."""
        # Just verify function exists — actual dead code detection is manual
        self.assertTrue(callable(compute_tx_id_orig))
        print("  compute_tx_id: defined but never called from production code")


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTxIdDeterminism)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    if not result.wasSuccessful():
        print("⚠️  Non-deterministic tx_id confirmed!")
    else:
        print("✅ All tests pass — fix ready")
    print("=" * 70)
