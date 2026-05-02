import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest

crypto = types.ModuleType("rustchain_crypto")


class CanonicalBlockHeader:
    pass


class MerkleTree:
    root_hex = "0" * 64


class SignedTransaction:
    pass


class Ed25519Signer:
    pass


def canonical_json(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode()


def blake2b256_hex(data):
    return hashlib.blake2b(data, digest_size=32).hexdigest()


crypto.CanonicalBlockHeader = CanonicalBlockHeader
crypto.MerkleTree = MerkleTree
crypto.SignedTransaction = SignedTransaction
crypto.Ed25519Signer = Ed25519Signer
crypto.canonical_json = canonical_json
crypto.blake2b256_hex = blake2b256_hex
sys.modules["rustchain_crypto"] = crypto

tx_handler = types.ModuleType("rustchain_tx_handler")


class TransactionPool:
    pass


tx_handler.TransactionPool = TransactionPool
sys.modules["rustchain_tx_handler"] = tx_handler

from rustchain_block_producer import BlockProducer
from utxo_db import UNIT, UtxoDB


class DummyPool:
    pass


class FailingUtxoDB:
    def compute_state_root(self):
        raise RuntimeError("boom")


class TestBlockProducerStateRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        with sqlite3.connect(self.tmp.name) as conn:
            conn.execute(
                "CREATE TABLE balances (wallet TEXT PRIMARY KEY, balance_urtc INTEGER NOT NULL, wallet_nonce INTEGER DEFAULT 0)"
            )
            conn.executemany(
                "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
                [
                    ("alice", 200 * UNIT, 1),
                    ("bob", 50 * UNIT, 2),
                ],
            )
            conn.commit()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _legacy_root(self):
        state = [
            {"wallet": "alice", "balance": 200 * UNIT, "nonce": 1},
            {"wallet": "bob", "balance": 50 * UNIT, "nonce": 2},
        ]
        return blake2b256_hex(canonical_json(state))

    def _make_utxo_db(self):
        utxo = UtxoDB(self.tmp.name)
        utxo.init_tables()
        utxo.apply_transaction(
            {
                "tx_type": "mining_reward",
                "inputs": [],
                "outputs": [{"address": "alice", "value_nrtc": 150 * UNIT}],
                "fee_nrtc": 0,
            },
            block_height=1,
        )
        utxo.apply_transaction(
            {
                "tx_type": "mining_reward",
                "inputs": [],
                "outputs": [{"address": "bob", "value_nrtc": 25 * UNIT}],
                "fee_nrtc": 0,
            },
            block_height=2,
        )
        return utxo

    def test_utxo_state_root_used_when_utxo_db_available(self):
        utxo = self._make_utxo_db()
        producer = BlockProducer(self.tmp.name, DummyPool(), utxo_db=utxo)
        self.assertEqual(producer.get_state_root(), utxo.compute_state_root())

    def test_fallback_to_account_model_when_no_utxo_db(self):
        producer = BlockProducer(self.tmp.name, DummyPool())
        self.assertEqual(producer.get_state_root(), self._legacy_root())

    def test_utxo_and_account_roots_differ(self):
        utxo = self._make_utxo_db()
        producer = BlockProducer(self.tmp.name, DummyPool(), utxo_db=utxo)
        self.assertNotEqual(producer.get_state_root(), self._legacy_root())

    def test_empty_utxo_state_root(self):
        utxo = UtxoDB(self.tmp.name)
        utxo.init_tables()
        producer = BlockProducer(self.tmp.name, DummyPool(), utxo_db=utxo)
        self.assertEqual(producer.get_state_root(), utxo.compute_state_root())
        self.assertEqual(len(producer.get_state_root()), 64)

    def test_utxo_state_root_changes_after_spend(self):
        utxo = self._make_utxo_db()
        before = utxo.compute_state_root()
        box = utxo.get_unspent_for_address("alice")[0]
        utxo.apply_transaction(
            {
                "tx_type": "transfer",
                "inputs": [{"box_id": box["box_id"], "spending_proof": "sig"}],
                "outputs": [
                    {"address": "bob", "value_nrtc": 100 * UNIT},
                    {"address": "alice", "value_nrtc": 50 * UNIT},
                ],
                "fee_nrtc": 0,
            },
            block_height=3,
        )
        producer = BlockProducer(self.tmp.name, DummyPool(), utxo_db=utxo)
        self.assertNotEqual(producer.get_state_root(), before)

    def test_utxo_state_root_deterministic(self):
        utxo = self._make_utxo_db()
        producer = BlockProducer(self.tmp.name, DummyPool(), utxo_db=utxo)
        self.assertEqual(producer.get_state_root(), producer.get_state_root())

    def test_utxo_failure_falls_back_to_legacy_root(self):
        producer = BlockProducer(self.tmp.name, DummyPool(), utxo_db=FailingUtxoDB())
        self.assertEqual(producer.get_state_root(), self._legacy_root())


if __name__ == "__main__":
    unittest.main()
