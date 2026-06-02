#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests for weighted-fair block producer duty balancing."""

import hashlib
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

from rustchain_block_producer import BlockProducer  # noqa: E402


def _miner(wallet, arch="modern_x86", **device_info):
    info = {"arch": arch, "family": "", "model": "", "year": 2025}
    info.update(device_info)
    return (wallet, arch, info)


def test_equal_weights_preserve_round_robin_order():
    rotation = BlockProducer._build_balanced_producer_rotation([
        _miner("alice"),
        _miner("bob"),
        _miner("carol"),
    ])

    assert rotation == ["alice", "bob", "carol"]


def test_weighted_rotation_spreads_higher_weight_duties():
    rotation = BlockProducer._build_balanced_producer_rotation([
        _miner("alice", weight=2),
        _miner("bob", weight=1),
        _miner("carol", weight=1),
    ])

    assert rotation.count("alice") == 2
    assert rotation.count("bob") == 1
    assert rotation.count("carol") == 1
    assert rotation == ["alice", "bob", "carol", "alice"]


def test_device_family_supplies_selection_weight():
    rotation = BlockProducer._build_balanced_producer_rotation([
        _miner("g4-miner", "ppc", family="PowerPC G4"),
        _miner("modern-miner", "x86_64", family="modern_x86"),
    ])

    assert rotation.count("g4-miner") == 2
    assert rotation.count("modern-miner") == 1


def test_balance_summary_counts_future_slot_duties(monkeypatch):
    producer = BlockProducer.__new__(BlockProducer)
    producer.get_slot_start_time = lambda slot: 1_700_000_000 + slot
    producer.get_attested_miners = lambda current_ts: [
        _miner("alice", weight=2),
        _miner("bob", weight=1),
    ]

    summary = producer.get_producer_balance_summary(0, slots=6)

    assert summary["rotation_size"] == 3
    assert summary["duty_counts"] == {"alice": 4, "bob": 2}
    assert [entry["producer"] for entry in summary["schedule"]] == [
        "alice",
        "bob",
        "alice",
        "alice",
        "bob",
        "alice",
    ]
