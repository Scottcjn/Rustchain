"""
Unit tests for coin_select — UTXO coin selection algorithm
Tests edge cases not covered by existing test suite.
"""
import sys, os, unittest, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "node"))

from utxo_db import coin_select, DUST_THRESHOLD

class TestCoinSelectEdgeCases(unittest.TestCase):

    def test_empty_utxo_list(self):
        """Empty UTXO list should return empty selection."""
        result, change = coin_select([], 1000)
        self.assertEqual(result, [])
        self.assertEqual(change, 0)

    def test_zero_target(self):
        """Zero target should return empty."""
        utxos = [{"value_nrtc": 1000}]
        result, change = coin_select(utxos, 0)
        self.assertEqual(result, [])
        self.assertEqual(change, 0)

    def test_negative_target(self):
        """Negative target should return empty."""
        utxos = [{"value_nrtc": 1000}]
        result, change = coin_select(utxos, -100)
        self.assertEqual(result, [])
        self.assertEqual(change, 0)

    def test_exact_match(self):
        """Single UTXO exactly matching target."""
        utxos = [{"value_nrtc": 1000}]
        result, change = coin_select(utxos, 1000)
        self.assertEqual(len(result), 1)
        self.assertEqual(change, 0)

    def test_insufficient_funds(self):
        """Not enough funds should return empty."""
        utxos = [{"value_nrtc": 100}]
        result, change = coin_select(utxos, 200)
        self.assertEqual(result, [])
        self.assertEqual(change, 0)

    def test_dust_change_absorbed(self):
        """Change below DUST_THRESHOLD should be absorbed (returned as 0)."""
        utxos = [{"value_nrtc": 1100}]
        result, change = coin_select(utxos, 1000)
        self.assertEqual(len(result), 1)
        # change 100 should be below DUST_THRESHOLD (1000)
        if 100 < DUST_THRESHOLD:
            self.assertEqual(change, 0)
        else:
            self.assertEqual(change, 100)

    def test_largest_first_when_many_inputs(self):
        """When more than 20 small inputs selected, should switch to largest-first."""
        utxos = [{"value_nrtc": 1} for _ in range(25)]
        utxos.append({"value_nrtc": 10000})
        result, change = coin_select(utxos, 5000)
        self.assertGreater(len(result), 0)
        # Should pick the large one, not lots of small ones
        self.assertLessEqual(len(result), 2)

    def test_mixed_values(self):
        """Mix of values: smallest-first accumulation."""
        utxos = [
            {"value_nrtc": 500},
            {"value_nrtc": 200},
            {"value_nrtc": 100},
            {"value_nrtc": 50},
        ]
        result, change = coin_select(utxos, 350)
        # Smallest-first: 50+100+200 = 350
        self.assertEqual(len(result), 3)

    def test_multiple_utxos_accumulated(self):
        """Multiple small UTXOs accumulate to cover target."""
        utxos = [{"value_nrtc": 100} for _ in range(10)]
        result, change = coin_select(utxos, 350)
        self.assertEqual(len(result), 4)

if __name__ == "__main__":
    unittest.main()
