# SPDX-License-Identifier: MIT
"""
Unit tests for UTXO value conservation, fee bounds, and input uniqueness invariants.
Security Bounty Reference: #2819
"""

import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _load_utxo_ledger_module():
    root = Path(__file__).resolve().parents[1]
    package = "rustchain_core_utxo_test"

    for name, path in (
        (package, root),
        (f"{package}.config", root / "config"),
        (f"{package}.ledger", root / "ledger"),
    ):
        module = sys.modules.get(name)
        if module is None:
            module = types.ModuleType(name)
            module.__path__ = [str(path)]
            sys.modules[name] = module

    module_name = f"{package}.ledger.utxo_ledger"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(
        module_name,
        root / "ledger" / "utxo_ledger.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


utxo_mod = _load_utxo_ledger_module()
Box = utxo_mod.Box
Transaction = utxo_mod.Transaction
TransactionInput = utxo_mod.TransactionInput
TransactionType = utxo_mod.TransactionType
UtxoSet = utxo_mod.UtxoSet
TransactionPool = utxo_mod.TransactionPool


class TestUtxoConservation(unittest.TestCase):
    def setUp(self):
        self.utxo = UtxoSet()
        self.miner_wallet = "RTC1TestMinerAddress"
        self.recipient = "RTC1TestRecipientAddress"

        # Seed initial box in UTXO set
        self.genesis_box = Box(
            box_id=b'',
            value=100_000_000,  # 1 RTC
            proposition_bytes=Box.wallet_to_proposition(self.miner_wallet),
            creation_height=1,
            transaction_id=b'\x01' * 32,
            output_index=0,
        )
        self.utxo.add_box(self.genesis_box, self.miner_wallet)

    def test_box_creation_rejects_non_positive_value(self):
        """Boxes must not be instantiated with zero or negative nanoRTC values."""
        with self.assertRaises(ValueError):
            Box(
                box_id=b'',
                value=-50_000_000,
                proposition_bytes=Box.wallet_to_proposition(self.recipient),
                creation_height=2,
                transaction_id=b'\x02' * 32,
                output_index=0,
            )

        with self.assertRaises(ValueError):
            Box(
                box_id=b'',
                value=0,
                proposition_bytes=Box.wallet_to_proposition(self.recipient),
                creation_height=2,
                transaction_id=b'\x02' * 32,
                output_index=0,
            )

    def test_apply_transaction_rejects_negative_fee(self):
        """Negative fees must not be used to bypass value conservation."""
        # Attempt to spend 100_000_000 (1 RTC) to create 150_000_000 (1.5 RTC) with -50_000_000 fee
        out_inflated = Box(
            box_id=b'',
            value=150_000_000,
            proposition_bytes=Box.wallet_to_proposition(self.recipient),
            creation_height=2,
            transaction_id=b'\x02' * 32,
            output_index=0,
        )
        tx = Transaction(
            tx_type=TransactionType.TRANSFER,
            inputs=[TransactionInput(box_id=self.genesis_box.box_id, spending_proof=b'proof')],
            outputs=[out_inflated],
            fee=-50_000_000,
        )
        applied = self.utxo.apply_transaction(tx, block_height=2)
        self.assertFalse(applied, "Transaction with negative fee must be rejected")
        self.assertEqual(self.utxo.get_balance(self.miner_wallet), 100_000_000)

    def test_apply_transaction_rejects_duplicate_inputs(self):
        """Duplicate inputs in the same transaction must be rejected."""
        out = Box(
            box_id=b'',
            value=180_000_000,
            proposition_bytes=Box.wallet_to_proposition(self.recipient),
            creation_height=2,
            transaction_id=b'\x02' * 32,
            output_index=0,
        )
        tx = Transaction(
            tx_type=TransactionType.TRANSFER,
            inputs=[
                TransactionInput(box_id=self.genesis_box.box_id, spending_proof=b'proof'),
                TransactionInput(box_id=self.genesis_box.box_id, spending_proof=b'proof'),
            ],
            outputs=[out],
            fee=10_000,
        )
        applied = self.utxo.apply_transaction(tx, block_height=2)
        self.assertFalse(applied, "Transaction with duplicate inputs must be rejected")

    def test_mempool_rejects_negative_fee_and_inflation(self):
        """TransactionPool must reject negative fees, negative outputs, and inflation."""
        pool = TransactionPool(self.utxo)

        out_inflated = Box(
            box_id=b'',
            value=200_000_000,
            proposition_bytes=Box.wallet_to_proposition(self.recipient),
            creation_height=2,
            transaction_id=b'\x03' * 32,
            output_index=0,
        )
        tx_neg_fee = Transaction(
            tx_type=TransactionType.TRANSFER,
            inputs=[TransactionInput(box_id=self.genesis_box.box_id, spending_proof=b'proof')],
            outputs=[out_inflated],
            fee=-100_000_000,
        )
        self.assertFalse(pool.add_transaction(tx_neg_fee), "Mempool must reject negative fee tx")

        tx_inflation = Transaction(
            tx_type=TransactionType.TRANSFER,
            inputs=[TransactionInput(box_id=self.genesis_box.box_id, spending_proof=b'proof')],
            outputs=[out_inflated],
            fee=10_000,
        )
        self.assertFalse(pool.add_transaction(tx_inflation), "Mempool must reject inflation tx")

    def test_valid_transaction_succeeds_and_conserves_value(self):
        """Valid transaction spending inputs and creating outputs succeeds cleanly."""
        out_recipient = Box(
            box_id=b'',
            value=60_000_000,
            proposition_bytes=Box.wallet_to_proposition(self.recipient),
            creation_height=2,
            transaction_id=b'\x04' * 32,
            output_index=0,
        )
        out_change = Box(
            box_id=b'',
            value=39_990_000,
            proposition_bytes=Box.wallet_to_proposition(self.miner_wallet),
            creation_height=2,
            transaction_id=b'\x04' * 32,
            output_index=1,
        )
        tx = Transaction(
            tx_type=TransactionType.TRANSFER,
            inputs=[TransactionInput(box_id=self.genesis_box.box_id, spending_proof=b'proof')],
            outputs=[out_recipient, out_change],
            fee=10_000,
        )
        applied = self.utxo.apply_transaction(tx, block_height=2)
        self.assertTrue(applied, "Valid transaction must apply successfully")
        self.assertEqual(self.utxo.get_balance(self.recipient), 60_000_000)
        self.assertEqual(self.utxo.get_balance(self.miner_wallet), 39_990_000)


if __name__ == "__main__":
    unittest.main()
