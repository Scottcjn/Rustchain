# SPDX-License-Identifier: MIT
import hashlib
import importlib
import json
import os
import sys
import threading
import time
import types

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _install_block_producer_stubs(monkeypatch):
    crypto = types.ModuleType("rustchain_crypto")

    class CanonicalBlockHeader:
        def __init__(
            self, version, height, timestamp, prev_hash, merkle_root,
            state_root, attestations_hash, producer,
        ):
            self.version = version
            self.height = height
            self.timestamp = timestamp
            self.prev_hash = prev_hash
            self.merkle_root = merkle_root
            self.state_root = state_root
            self.attestations_hash = attestations_hash
            self.producer = producer
            self.producer_sig = ""

        def sign(self, signer):
            self.producer_sig = "sig"

        def compute_hash(self):
            payload = f"{self.height}:{self.prev_hash}:{self.merkle_root}".encode()
            return hashlib.sha256(payload).hexdigest()

    class MerkleTree:
        root_hex = "0" * 64

        def add_leaf_hash(self, tx_hash):
            pass

    crypto.CanonicalBlockHeader = CanonicalBlockHeader
    crypto.MerkleTree = MerkleTree
    crypto.SignedTransaction = object
    crypto.Ed25519Signer = object
    crypto.blake2b256_hex = lambda data: hashlib.blake2b(data, digest_size=32).hexdigest()
    crypto.canonical_json = lambda obj: json.dumps(
        obj, separators=(",", ":"), sort_keys=True
    ).encode()
    monkeypatch.setitem(sys.modules, "rustchain_crypto", crypto)

    tx_handler = types.ModuleType("rustchain_tx_handler")
    tx_handler.TransactionPool = object
    monkeypatch.setitem(sys.modules, "rustchain_tx_handler", tx_handler)


class FakeTx:
    tx_hash = "aa" * 32

    def to_dict(self):
        return {"tx_hash": self.tx_hash}


class FakeBody:
    transactions = [FakeTx()]
    attestations = []

    def to_dict(self):
        return {
            "transactions": [tx.to_dict() for tx in self.transactions],
            "attestations": [],
        }


class FakeHeader:
    prev_hash = "old-head"
    timestamp = 123
    merkle_root = "m" * 64
    state_root = "s" * 64
    attestations_hash = "a" * 64
    producer = "miner"
    producer_sig = "sig"


class FakeBlock:
    height = 1
    hash = "saved-head"
    header = FakeHeader()
    body = FakeBody()


class BlockingPool:
    def __init__(self):
        self.confirm_entered = threading.Event()
        self.release_confirm = threading.Event()

    def confirm_transaction(self, tx_hash, block_height, block_hash, conn=None):
        self.confirm_entered.set()
        assert self.release_confirm.wait(2)
        return True

    def get_pending_transactions(self, max_count):
        return []


def test_save_block_serializes_with_template_production(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(NODE_DIR)
    _install_block_producer_stubs(monkeypatch)
    sys.modules.pop("rustchain_block_producer", None)
    block_producer = importlib.import_module("rustchain_block_producer")

    pool = BlockingPool()
    producer = block_producer.BlockProducer(
        str(tmp_path / "chain.db"),
        pool,
        signer=object(),
        wallet_address="miner",
    )
    producer.get_round_robin_producer = lambda slot: "miner"
    producer.get_state_root = lambda: "s" * 64
    producer.get_attestations_for_block = lambda: []

    save_thread = threading.Thread(target=lambda: producer.save_block(FakeBlock()))
    save_thread.start()
    assert pool.confirm_entered.wait(2)

    produced = []
    produce_thread = threading.Thread(
        target=lambda: produced.append(producer.produce_block(slot=1))
    )
    produce_thread.start()

    time.sleep(0.1)
    assert produce_thread.is_alive()

    pool.release_confirm.set()
    save_thread.join(2)
    produce_thread.join(2)

    assert produced[0] is not None
    assert produced[0].header.prev_hash == "saved-head"
