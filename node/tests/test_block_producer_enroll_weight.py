#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests for #6463 fix: epoch_enroll weight as single source of truth for producer duty.

Miners with zero epoch_enroll weight (VM/emulator) must get zero duty weight,
regardless of device heuristics or explicit weight in device_info.
"""

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Stub out randomness_beacon
beacon = types.ModuleType("randomness_beacon")
GENESIS_RANDOMNESS = "0" * 64
def build_randomness_record(*a, **kw):
    return {}
def verify_randomness_record(*a, **kw):
    return True
class BeaconClient:
    pass
beacon.GENESIS_RANDOMNESS = GENESIS_RANDOMNESS
beacon.build_randomness_record = build_randomness_record
beacon.verify_randomness_record = verify_randomness_record
beacon.BeaconClient = BeaconClient
sys.modules["randomness_beacon"] = beacon

# Stub out rustchain_crypto
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

# Stub out rustchain_tx_handler
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


def _make_db_with_epoch_enroll(db_path, epoch, enrollments):
    """Create a DB with epoch_enroll table populated with the given enrollments."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS epoch_enroll "
        "(epoch INTEGER, miner_pk TEXT, weight INTEGER, PRIMARY KEY (epoch, miner_pk))"
    )
    for miner_pk, weight in enrollments:
        conn.execute(
            "INSERT OR REPLACE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
            (epoch, miner_pk, weight),
        )
    conn.commit()
    conn.close()


def test_zero_enroll_weight_yields_zero_duty_weight():
    """Miner with zero epoch_enroll weight must get zero producer duty weight."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        epoch = 1
        _make_db_with_epoch_enroll(db_path, epoch, [
            ("alice", 5),
            ("vm-miner", 0),
        ])

        alice_weight = BlockProducer._miner_selection_weight(_miner("alice"), epoch=epoch, db_path=db_path)
        vm_weight = BlockProducer._miner_selection_weight(_miner("vm-miner"), epoch=epoch, db_path=db_path)

        assert alice_weight > 0, f"Alice should have positive duty weight, got {alice_weight}"
        assert vm_weight == 0.0, f"VM miner with zero enroll weight should have zero duty weight, got {vm_weight}"


def test_zero_enroll_weight_excluded_from_rotation():
    """Miner with zero enroll weight must not appear in the producer rotation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        epoch = 1
        _make_db_with_epoch_enroll(db_path, epoch, [
            ("alice", 3),
            ("vm-miner", 0),
        ])

        rotation = BlockProducer._build_balanced_producer_rotation(
            [_miner("alice"), _miner("vm-miner")],
            epoch=epoch,
            db_path=db_path,
        )

        assert "vm-miner" not in rotation, "Zero-enroll-weight miner must not appear in rotation"
        assert "alice" in rotation, "Normal miner must appear in rotation"


def test_enroll_weight_overrides_device_heuristic():
    """Even if device_info claims high weight, epoch_enroll is authoritative."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        epoch = 1
        _make_db_with_epoch_enroll(db_path, epoch, [
            ("g4-miner", 1),
        ])

        # device heuristic would give 2.5 for G4, but enroll says 1
        weight = BlockProducer._miner_selection_weight(
            _miner("g4-miner", "ppc", family="PowerPC G4"),
            epoch=epoch,
            db_path=db_path,
        )
        assert weight == 1.0, f"Enroll weight (1) should override device heuristic (2.5), got {weight}"


def test_fallback_to_heuristic_when_no_enroll_row():
    """If no epoch_enroll row exists, device heuristic is used as fallback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        epoch = 99  # no enrollments for this epoch
        _make_db_with_epoch_enroll(db_path, epoch=1, enrollments=[("someone", 5)])

        weight = BlockProducer._miner_selection_weight(
            _miner("g4-miner", "ppc", family="PowerPC G4"),
            epoch=epoch,
            db_path=db_path,
        )
        # No enroll row -> fallback to device heuristic -> G4 = 2.5
        assert weight == 2.5, f"Expected heuristic fallback weight 2.5, got {weight}"


def test_multiple_zero_enroll_miners_all_excluded():
    """Multiple VM miners with zero enroll weight are all excluded from rotation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        epoch = 1
        _make_db_with_epoch_enroll(db_path, epoch, [
            ("alice", 2),
            ("vm1", 0),
            ("vm2", 0),
            ("bob", 1),
        ])

        rotation = BlockProducer._build_balanced_producer_rotation(
            [_miner("alice"), _miner("vm1"), _miner("vm2"), _miner("bob")],
            epoch=epoch,
            db_path=db_path,
        )

        assert "vm1" not in rotation
        assert "vm2" not in rotation
        assert "alice" in rotation
        assert "bob" in rotation
        assert rotation.count("alice") == 2
        assert rotation.count("bob") == 1
