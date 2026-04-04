"""
[UTXO-BUG] Security bug report — Failing test cases for UTXO implementation
============================================================================

Submitted for: https://github.com/Scottcjn/rustchain-bounties/issues/2819

Bugs found:
1. CRITICAL: No spending_proof validation — anyone can spend any UTXO
2. MEDIUM: Silent fund destruction — inputs > outputs+fee is silently accepted
3. LOW: Zero/negative output values accepted — can create worthless UTXOs
4. LOW: No duplicate input validation — same box_id can appear twice in inputs
"""

import os
import sqlite3
import tempfile
import unittest

# Adjust path so we can import utxo_db from the node directory
import sys
sys.path.insert(0, os.path.dirname(__file__))

from utxo_db import UTXODatabase, compute_box_id, address_to_proposition


class UTXOBugTests(unittest.TestCase):
    """Failing tests that demonstrate security vulnerabilities."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test_utxo.db")
        self.db = UTXODatabase(self.db_path)
        # Seed a UTXO owned by Alice
        self._seed_utxo("alice", 1_000_000_000)  # 10 RTC

    def _seed_utxo(self, address, value_nrtc):
        """Create a genesis UTXO for testing."""
        tx = {
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': address, 'value_nrtc': value_nrtc}],
            'fee_nrtc': 0,
            'timestamp': 1000,
        }
        self.db.apply_transaction(tx, block_height=1)

    def _get_utxos(self, address):
        return self.db.get_unspent_for_address(address)

    # -----------------------------------------------------------------------
    # BUG 1 (CRITICAL): No spending_proof validation
    # -----------------------------------------------------------------------
    def test_bug1_anyone_can_spend_without_valid_proof(self):
        """
        CRITICAL: apply_transaction never validates spending_proof.
        An attacker (Bob) can spend Alice's UTXO with a garbage proof.

        Expected: Transaction should FAIL (return False)
        Actual:   Transaction SUCCEEDS — funds stolen
        """
        alice_utxos = self._get_utxos("alice")
        self.assertEqual(len(alice_utxos), 1)

        # Bob tries to spend Alice's UTXO with a completely fake proof
        stolen_tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': alice_utxos[0]['box_id'],
                        'spending_proof': 'FAKE_PROOF_NOT_VALID'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 1_000_000_000}],
            'fee_nrtc': 0,
            'timestamp': 2000,
        }
        result = self.db.apply_transaction(stolen_tx, block_height=2)

        # This SHOULD fail but currently succeeds — that's the bug
        self.assertFalse(result,
            "BUG: Transaction succeeded with fake spending_proof! "
            "Anyone can spend anyone's UTXOs.")

    # -----------------------------------------------------------------------
    # BUG 2 (MEDIUM): Silent fund destruction
    # -----------------------------------------------------------------------
    def test_bug2_silent_fund_destruction(self):
        """
        MEDIUM: When output_total + fee < input_total, the difference
        just vanishes. There's no strict conservation law enforcement.

        The check is: (output_total + fee) > input_total → reject
        But it should also reject: (output_total + fee) < input_total
        (unless the difference is explicitly assigned as a miner fee)

        Expected: Transaction should FAIL or the excess should be
                  explicitly handled as fee
        Actual:   500M nanoRTC (5 RTC) silently destroyed
        """
        alice_utxos = self._get_utxos("alice")

        # Alice sends 5 RTC but her input is 10 RTC, fee=0
        # 5 RTC just vanishes into thin air
        destroy_tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': alice_utxos[0]['box_id'],
                        'spending_proof': 'valid'}],
            'outputs': [{'address': 'bob', 'value_nrtc': 500_000_000}],
            'fee_nrtc': 0,  # fee is 0, but 500M nRTC disappears
            'timestamp': 2000,
        }
        result = self.db.apply_transaction(destroy_tx, block_height=2)

        if result:
            # If the tx succeeds, verify the funds are actually destroyed
            bob_balance = self.db.get_balance("bob")
            alice_balance = self.db.get_balance("alice")
            total = bob_balance + alice_balance
            self.assertEqual(total, 1_000_000_000,
                "BUG: Funds destroyed! Input was 1B nRTC, but "
                f"Alice has {alice_balance} + Bob has {bob_balance} = {total}. "
                f"Missing: {1_000_000_000 - total} nRTC")

    # -----------------------------------------------------------------------
    # BUG 3 (LOW): Zero/negative output values accepted
    # -----------------------------------------------------------------------
    def test_bug3_zero_value_output_accepted(self):
        """
        LOW: An output with value_nrtc=0 is accepted and creates a
        UTXO with 0 value. This pollutes the UTXO set.

        Expected: Should reject outputs with value <= 0
        Actual:   Creates a zero-value UTXO
        """
        alice_utxos = self._get_utxos("alice")

        zero_tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': alice_utxos[0]['box_id'],
                        'spending_proof': 'valid'}],
            'outputs': [
                {'address': 'bob', 'value_nrtc': 1_000_000_000},
                {'address': 'spam', 'value_nrtc': 0},  # zero-value output
            ],
            'fee_nrtc': 0,
            'timestamp': 2000,
        }
        result = self.db.apply_transaction(zero_tx, block_height=2)
        self.assertFalse(result,
            "BUG: Zero-value output accepted. This allows UTXO set pollution.")

    def test_bug3b_negative_value_output_accepted(self):
        """
        LOW: An output with negative value_nrtc bypasses conservation.
        output_total + fee could be <= input_total while creating
        a large positive output elsewhere.

        Expected: Should reject
        Actual:   May succeed depending on sum arithmetic
        """
        alice_utxos = self._get_utxos("alice")

        neg_tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': alice_utxos[0]['box_id'],
                        'spending_proof': 'valid'}],
            'outputs': [
                {'address': 'bob', 'value_nrtc': 2_000_000_000},   # 20 RTC!
                {'address': 'sink', 'value_nrtc': -1_000_000_000}, # negative
            ],
            'fee_nrtc': 0,
            'timestamp': 2000,
        }
        result = self.db.apply_transaction(neg_tx, block_height=2)
        self.assertFalse(result,
            "BUG: Negative output value accepted! "
            "This can be used to create RTC from nothing.")

    # -----------------------------------------------------------------------
    # BUG 4 (LOW): Duplicate inputs not detected
    # -----------------------------------------------------------------------
    def test_bug4_duplicate_input_double_count(self):
        """
        LOW: The same box_id can appear multiple times in the inputs list.
        The first spend succeeds, the second one should fail but the
        input_total already double-counted the value.

        Expected: Should detect and reject duplicate inputs upfront
        Actual:   Relies on the UPDATE WHERE spent_at IS NULL for second
                  input, but input_total was already inflated
        """
        alice_utxos = self._get_utxos("alice")
        box_id = alice_utxos[0]['box_id']

        # Same input listed twice — input_total = 2B but only 1B exists
        dup_tx = {
            'tx_type': 'transfer',
            'inputs': [
                {'box_id': box_id, 'spending_proof': 'valid'},
                {'box_id': box_id, 'spending_proof': 'valid'},
            ],
            'outputs': [{'address': 'bob', 'value_nrtc': 2_000_000_000}],
            'fee_nrtc': 0,
            'timestamp': 2000,
        }
        result = self.db.apply_transaction(dup_tx, block_height=2)
        # The second UPDATE will fail (spent_at already set), so tx rolls back
        # But the bug is that input_total was calculated as 2B, passing conservation
        # This test documents the behavior
        if result:
            bob_balance = self.db.get_balance("bob")
            self.fail(
                f"BUG: Duplicate input accepted! Bob now has {bob_balance} nRTC "
                "from a 1B nRTC input listed twice.")


if __name__ == '__main__':
    unittest.main()
