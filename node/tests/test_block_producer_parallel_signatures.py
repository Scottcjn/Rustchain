# SPDX-License-Identifier: MIT

import importlib.util
import json
import sys
import types
from pathlib import Path

NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_block_producer.py"


def _load_block_producer_module():
    crypto_mod = types.SimpleNamespace(
        CanonicalBlockHeader=object,
        MerkleTree=object,
        SignedTransaction=object,
        Ed25519Signer=object,
        blake2b256_hex=lambda data: "0" * 64,
        canonical_json=lambda data: json.dumps(data, sort_keys=True).encode(),
    )
    tx_handler_mod = types.SimpleNamespace(TransactionPool=object)
    sys.modules["rustchain_crypto"] = crypto_mod
    sys.modules["rustchain_tx_handler"] = tx_handler_mod

    spec = importlib.util.spec_from_file_location(
        "rustchain_block_producer_parallel_signature_test",
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


block_producer = _load_block_producer_module()


class DummyTx:
    def __init__(self, tx_hash, valid=True):
        self.tx_hash = tx_hash
        self.valid = valid
        self.verify_calls = 0

    def verify(self):
        self.verify_calls += 1
        return self.valid


class DummyBody:
    merkle_root = "m" * 64

    def __init__(self, transactions):
        self.transactions = transactions

    def compute_attestations_hash(self):
        return "a" * 64


class DummyHeader:
    merkle_root = "m" * 64
    attestations_hash = "a" * 64


class RecordingExecutor:
    calls = []

    def __init__(self, max_workers):
        self.max_workers = max_workers
        self.calls.append(max_workers)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def map(self, func, values):
        return [func(value) for value in values]


def _block(transactions):
    return block_producer.Block(header=DummyHeader(), body=DummyBody(transactions))


def test_validate_structure_keeps_small_blocks_on_serial_path(monkeypatch):
    def fail_if_used(*args, **kwargs):
        raise AssertionError("parallel executor should not be used for small blocks")

    monkeypatch.setattr(block_producer, "ThreadPoolExecutor", fail_if_used)
    monkeypatch.setattr(block_producer, "MIN_PARALLEL_SIGNATURE_CHECKS", 8)
    transactions = [DummyTx(f"tx-{i}") for i in range(4)]

    valid, error = _block(transactions).validate_structure()

    assert valid is True
    assert error == ""
    assert [tx.verify_calls for tx in transactions] == [1, 1, 1, 1]


def test_validate_structure_parallelizes_large_block_signature_checks(monkeypatch):
    RecordingExecutor.calls = []
    monkeypatch.setattr(block_producer, "ThreadPoolExecutor", RecordingExecutor)
    monkeypatch.setattr(block_producer, "MIN_PARALLEL_SIGNATURE_CHECKS", 4)
    monkeypatch.setattr(block_producer.os, "cpu_count", lambda: 3)
    transactions = [DummyTx(f"tx-{i}") for i in range(10)]

    valid, error = _block(transactions).validate_structure()

    assert valid is True
    assert error == ""
    assert RecordingExecutor.calls == [3]
    assert [tx.verify_calls for tx in transactions] == [1] * 10


def test_validate_structure_reports_first_invalid_transaction_in_block_order(monkeypatch):
    RecordingExecutor.calls = []
    monkeypatch.setattr(block_producer, "ThreadPoolExecutor", RecordingExecutor)
    monkeypatch.setattr(block_producer, "MIN_PARALLEL_SIGNATURE_CHECKS", 4)
    transactions = [
        DummyTx("tx-0"),
        DummyTx("tx-1", valid=False),
        DummyTx("tx-2"),
        DummyTx("tx-3", valid=False),
    ]

    valid, error = _block(transactions).validate_structure()

    assert valid is False
    assert error == "Invalid transaction signature: tx-1"
