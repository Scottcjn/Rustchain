# SPDX-License-Identifier: MIT
"""
Unit tests for UTXO value conservation, fee bounds, coinbase invariants, and mempool alignment.
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
            transaction_id=b'' * 32,
            output_index=0,
        )
        self.utxo.add_box(self.genesis_box, self.miner_wallet)

    def test_box_creation_rejects_negative_and_zero_values(self):
        """Boxes must not be instantiated with zero or negative nanoRTC values."""
        with self.assertRaises(ValueError):
            Box(
                box_id=b'',
                value=-50_000_000,
                proposition_bytes=Box.wallet_to_proposition(self.recipient),
                creation_height=2,
                transaction_id=b'' * 32,
                output_index=0,
            )

        with self.assertRaises(ValueError):
            Box(
                box_id=b'',
                value=-1,
                proposition_bytes=Box.wallet_to_proposition(self.recipient),
                creation_height=2,
                transaction_id=b'' * 32,
                output_index=0,
            )

        with self.assertRaises(ValueError):
            Box(
                box_id=b'',
                value=0,
                proposition_bytes=Box.wallet_to_proposition(self.recipient),
                creation_height=2,
                transaction_id=b'' * 32,
                output_index=0,
            )

    def test_apply_transaction_rejects_negative_fee(self):
        """Negative fees must not be used to bypass value conservation."""
        out_inflated = Box(
            box_id=b'',
            value=150_000_000,
            proposition_bytes=Box.wallet_to_proposition(self.recipient),
            creation_height=2,
            transaction_id=b'' * 32,
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
            transaction_id=b'' * 32,
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

    def test_empty_input_non_reward_rejected_at_both_mempool_and_apply(self):
        """Empty-input transactions that are not MINING_REWARD must be rejected at both mempool and apply."""
        pool = TransactionPool(self.utxo)
        out_box = Box(
            box_id=b'',
            value=10_000_000,
            proposition_bytes=Box.wallet_to_proposition(self.recipient),
            creation_height=2,
            transaction_id=b'' * 32,
            output_index=0,
        )

        for non_reward_type in [
            TransactionType.TRANSFER,
            TransactionType.BADGE_MINT,
            TransactionType.GOVERNANCE_VOTE,
            TransactionType.CONTRACT_CALL,
        ]:
            tx_empty_input = Transaction(
                tx_type=non_reward_type,
                inputs=[],
                outputs=[out_box],
                fee=0,
            )
            self.assertFalse(
                self.utxo.apply_transaction(tx_empty_input, block_height=2),
                f"apply_transaction must reject empty-input {non_reward_type.value}",
            )
            self.assertFalse(
                pool.add_transaction(tx_empty_input),
                f"add_transaction (mempool) must reject empty-input {non_reward_type.value}",
            )

    def test_mining_reward_with_nonzero_fee_rejected_at_both_mempool_and_apply(self):
        """MINING_REWARD transactions with non-zero fee must be rejected at both mempool and apply."""
        pool = TransactionPool(self.utxo)
        reward_tx = Transaction.mining_reward(
            miner_wallet=self.miner_wallet,
            reward_amount=50_000_000,
            block_height=2,
            antiquity_score=1.5,
            hardware_model="PowerBook_G4",
        )
        reward_tx.fee = 10_000  # corrupt fee

        self.assertFalse(
            self.utxo.apply_transaction(reward_tx, block_height=2),
            "apply_transaction must reject MINING_REWARD with non-zero fee",
        )
        self.assertFalse(
            pool.add_transaction(reward_tx),
            "add_transaction must reject MINING_REWARD with non-zero fee",
        )

    def test_valid_mining_reward_applies_and_enters_mempool(self):
        """A valid MINING_REWARD transaction succeeds at apply and enters mempool."""
        pool = TransactionPool(self.utxo)
        valid_reward = Transaction.mining_reward(
            miner_wallet=self.miner_wallet,
            reward_amount=50_000_000,
            block_height=2,
            antiquity_score=2.0,
            hardware_model="iMac_G5",
        )

        self.assertTrue(
            pool.add_transaction(valid_reward),
            "Valid MINING_REWARD must be accepted by mempool",
        )
        self.assertTrue(
            self.utxo.apply_transaction(valid_reward, block_height=2),
            "Valid MINING_REWARD must apply cleanly to UTXO set",
        )
        self.assertEqual(
            self.utxo.get_balance(self.miner_wallet),
            150_000_000,
            "Miner balance must increase by mining reward amount",
        )

    def test_mempool_rejects_negative_fee_and_inflation(self):
        """TransactionPool must reject negative fees, negative outputs, and inflation."""
        pool = TransactionPool(self.utxo)

        out_inflated = Box(
            box_id=b'',
            value=200_000_000,
            proposition_bytes=Box.wallet_to_proposition(self.recipient),
            creation_height=2,
            transaction_id=b'' * 32,
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
            transaction_id=b'' * 32,
            output_index=0,
        )
        out_change = Box(
            box_id=b'',
            value=39_990_000,
            proposition_bytes=Box.wallet_to_proposition(self.miner_wallet),
            creation_height=2,
            transaction_id=b'' * 32,
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
