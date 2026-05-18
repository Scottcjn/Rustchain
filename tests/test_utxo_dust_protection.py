# SPDX-License-Identifier: MIT
"""Regression tests for #9273: UTXO dust/bloat protections"""
import hashlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "node"))

from utxo_db import UtxoDB, address_to_proposition, compute_box_id, DUST_THRESHOLD


class TestUTXODustProtection(unittest.TestCase):
    """Verify #9273 fixes: max outputs + dust threshold enforcement"""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = UtxoDB(self.db_path)
        self.db.init_tables()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _fund(self, address="funder", amount_nrtc=100_000_000_000):
        """Create a spending UTXO worth `amount_nrtc` nrtc"""
        conn = self.db._conn()
        conn.execute("BEGIN IMMEDIATE")
        fund_id = hashlib.sha256(address.encode()).hexdigest()
        box_id = compute_box_id(amount_nrtc, address_to_proposition(address), 1, fund_id, 0)
        self.db.add_box(
            {
                "box_id": box_id,
                "value_nrtc": amount_nrtc,
                "proposition": address_to_proposition(address),
                "owner_address": address,
                "creation_height": 1,
                "transaction_id": fund_id,
                "output_index": 0,
                "tokens_json": "[]",
                "registers_json": "{}",
            },
            conn,
        )
        conn.execute("COMMIT")
        return box_id

    # --- MAX_OUTPUTS threshold ---

    def test_reject_excessive_outputs(self):
        """Transactions with > MAX_OUTPUTS outputs must be rejected"""
        box_id = self._fund()
        tx = {
            "tx_type": "transfer",
            "inputs": [{"box_id": box_id, "spending_proof": "dummy"}],
            "outputs": [
                {"address": f"out_{i}", "value_nrtc": DUST_THRESHOLD}
                for i in range(1001)
            ],
            "fee_nrtc": 0,
            "timestamp": 1,
        }
        result = self.db.apply_transaction(tx)
        self.assertFalse(result, "1001-output tx must be rejected")

    def test_accept_1000_outputs(self):
        """Transactions with exactly MAX_OUTPUTS outputs must be accepted"""
        box_id = self._fund()
        tx = {
            "tx_type": "transfer",
            "inputs": [{"box_id": box_id, "spending_proof": "dummy"}],
            "outputs": [
                {"address": f"out_{i}", "value_nrtc": DUST_THRESHOLD}
                for i in range(1000)
            ],
            "fee_nrtc": 0,
            "timestamp": 1,
        }
        result = self.db.apply_transaction(tx)
        self.assertTrue(result, "1000-output tx within limit must be accepted")

    # --- DUST_THRESHOLD enforcement ---

    def test_reject_dust_output(self):
        """Output below DUST_THRESHOLD must be rejected"""
        box_id = self._fund()
        tx = {
            "tx_type": "transfer",
            "inputs": [{"box_id": box_id, "spending_proof": "dummy"}],
            "outputs": [
                {"address": "dusty", "value_nrtc": DUST_THRESHOLD - 1},
            ],
            "fee_nrtc": 0,
            "timestamp": 1,
        }
        result = self.db.apply_transaction(tx)
        self.assertFalse(result, "dust output must be rejected")

    def test_reject_one_dust_among_valid(self):
        """If any output is below DUST_THRESHOLD, entire tx must be rejected"""
        box_id = self._fund()
        tx = {
            "tx_type": "transfer",
            "inputs": [{"box_id": box_id, "spending_proof": "dummy"}],
            "outputs": [
                {"address": "valid", "value_nrtc": DUST_THRESHOLD * 10},
                {"address": "dusty", "value_nrtc": 1},  # well below DUST_THRESHOLD
            ],
            "fee_nrtc": 0,
            "timestamp": 1,
        }
        result = self.db.apply_transaction(tx)
        self.assertFalse(result, "tx with one dust output must be rejected")

    def test_accept_minimum_valid_output(self):
        """Output exactly at DUST_THRESHOLD must be accepted"""
        box_id = self._fund()
        tx = {
            "tx_type": "transfer",
            "inputs": [{"box_id": box_id, "spending_proof": "dummy"}],
            "outputs": [
                {"address": "min_valid", "value_nrtc": DUST_THRESHOLD},
            ],
            "fee_nrtc": 0,
            "timestamp": 1,
        }
        result = self.db.apply_transaction(tx)
        self.assertTrue(result, "output at DUST_THRESHOLD must be accepted")

    # --- UTXO preservation on rejection ---

    def test_input_not_spent_on_rejection(self):
        """Rejected tx must leave input UTXO unspent"""
        box_id = self._fund()
        tx = {
            "tx_type": "transfer",
            "inputs": [{"box_id": box_id, "spending_proof": "dummy"}],
            "outputs": [
                {"address": "tiny", "value_nrtc": 1},
            ],
            "fee_nrtc": 0,
            "timestamp": 1,
        }
        result = self.db.apply_transaction(tx)
        self.assertFalse(result)

        # Verify UTXO still exists and is unspent
        conn = self.db._conn()
        row = conn.execute(
            "SELECT spent_at FROM utxo_boxes WHERE box_id = ?", (box_id,)
        ).fetchone()
        self.assertIsNotNone(row, "UTXO must still exist after rejection")
        self.assertIsNone(row["spent_at"], "UTXO must remain unspent after rejection")

    # --- Mining reward exemption ---

    def test_mining_reward_exempt_from_limits(self):
        """Mining rewards must be exempt from both MAX_OUTPUTS and DUST_THRESHOLD"""
        tx = {
            "tx_type": "mining_reward",
            "_allow_minting": True,
            "inputs": [],
            "outputs": [
                {"address": f"miner_{i}", "value_nrtc": 1}
                for i in range(1500)
            ],
            "fee_nrtc": 0,
            "timestamp": 1,
        }
        result = self.db.apply_transaction(tx)
        self.assertTrue(result, "mining reward must be exempt from output/dust limits")


if __name__ == "__main__":
    unittest.main()
