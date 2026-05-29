# SPDX-License-Identifier: MIT
"""
Tests that block-producer duty weights are driven from the authoritative
epoch_enroll table, not just local device heuristics.

Regression test for https://github.com/Scottcjn/Rustchain/issues/6463
"""

import json
import os
import sqlite3
import sys
import tempfile
import time
import types
from pathlib import Path

NODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NODE_DIR))

# Stub out heavy dependencies that aren't needed for block-producer logic
_crypto = types.ModuleType("rustchain_crypto")
_crypto.CanonicalBlockHeader = object
_crypto.Ed25519Signer = object
_crypto.SignedTransaction = object
_crypto.blake2b256_hex = lambda payload: "0" * 64
_crypto.canonical_json = lambda payload: json.dumps(payload, sort_keys=True).encode("utf-8")
_crypto.address_from_public_key = lambda pk: "addr_stub"
_crypto.generate_wallet_keypair = lambda: ("addr", "pub", "priv")

class _MerkleTree:
    root_hex = "0" * 64
    def add_leaf_hash(self, _tx_hash):
        return None

_crypto.MerkleTree = _MerkleTree
sys.modules.setdefault("rustchain_crypto", _crypto)

_beacon = types.ModuleType("randomness_beacon")
_beacon.GENESIS_RANDOMNESS = "0" * 64
_beacon.build_randomness_record = lambda **kw: {}
_beacon.verify_randomness_record = lambda *a, **kw: True
sys.modules.setdefault("randomness_beacon", _beacon)

_redis = types.ModuleType("redis")
sys.modules.setdefault("redis", _redis)

from rustchain_block_producer import BlockProducer, GENESIS_TIMESTAMP, BLOCK_TIME  # noqa: E402


def _make_db(tmpdir, attested_miners, enroll_weights, epoch=0):
    """Create a minimal SQLite DB with miner_attest_recent and epoch_enroll.

    *attested_miners* is a list of (miner_id, device_arch, device_family) tuples.
    *enroll_weights* is a dict mapping miner_id → weight (int).
    """
    db_path = os.path.join(tmpdir, "test.db")
    # Place the attestation timestamp well inside the epoch AND within
    # ATTESTATION_TTL of "now" so get_attested_miners picks it up.
    now_ts = int(time.time())
    epoch_for_ts = (now_ts - GENESIS_TIMESTAMP) // BLOCK_TIME // 144

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE miner_attest_recent (
                miner TEXT PRIMARY KEY,
                ts_ok INTEGER NOT NULL,
                device_family TEXT,
                device_arch TEXT,
                device_model TEXT,
                device_year INTEGER
            )
        """)
        for miner_id, arch, family in attested_miners:
            conn.execute(
                "INSERT INTO miner_attest_recent (miner, ts_ok, device_arch, device_family) VALUES (?, ?, ?, ?)",
                (miner_id, now_ts, arch, family),
            )

        conn.execute("""
            CREATE TABLE epoch_enroll (
                epoch INTEGER,
                miner_pk TEXT,
                weight INTEGER,
                PRIMARY KEY (epoch, miner_pk)
            )
        """)
        use_epoch = epoch if epoch != 0 else epoch_for_ts
        for miner_id, weight in enroll_weights.items():
            conn.execute(
                "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                (use_epoch, miner_id, weight),
            )

    return db_path, now_ts


class TestEnrollWeightGate:
    """Miners with epoch_enroll.weight == 0 must be excluded from producer duty."""

    def test_zero_enroll_weight_excluded_from_rotation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            miners = [
                ("alice", "modern_x86", "desktop"),
                ("bob", "modern_x86", "desktop"),
                ("vm_miner", "modern_x86", "vm"),
            ]
            enroll = {"alice": 5, "bob": 5, "vm_miner": 0}
            db_path, now_ts = _make_db(tmpdir, miners, enroll)

            bp = BlockProducer(db_path=db_path, tx_pool=None)

            attested = bp.get_attested_miners(now_ts)
            assert len(attested) == 3

            # vm_miner should have enroll_weight=0 in device_info
            vm_entry = [m for m in attested if m[0] == "vm_miner"][0]
            assert vm_entry[2]["enroll_weight"] == 0

            # _miner_selection_weight must return 0 for vm_miner
            assert BlockProducer._miner_selection_weight(vm_entry) == 0.0

            # vm_miner must NOT appear in the producer rotation
            rotation = BlockProducer._build_balanced_producer_rotation(attested)
            assert "vm_miner" not in rotation
            assert "alice" in rotation
            assert "bob" in rotation

    def test_positive_enroll_weight_included_in_rotation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            miners = [
                ("alice", "modern_x86", "desktop"),
                ("bob", "modern_x86", "desktop"),
            ]
            enroll = {"alice": 5, "bob": 3}
            db_path, now_ts = _make_db(tmpdir, miners, enroll)

            bp = BlockProducer(db_path=db_path, tx_pool=None)
            attested = bp.get_attested_miners(now_ts)

            rotation = BlockProducer._build_balanced_producer_rotation(attested)
            assert "alice" in rotation
            assert "bob" in rotation

    def test_missing_enroll_weight_allows_heuristic(self):
        """When a miner has no epoch_enroll row, the heuristic weight applies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            miners = [
                ("alice", "modern_x86", "desktop"),
                ("new_miner", "modern_x86", "desktop"),
            ]
            enroll = {"alice": 5}  # new_miner has no enroll entry
            db_path, now_ts = _make_db(tmpdir, miners, enroll)

            bp = BlockProducer(db_path=db_path, tx_pool=None)
            attested = bp.get_attested_miners(now_ts)

            new_entry = [m for m in attested if m[0] == "new_miner"][0]
            assert new_entry[2]["enroll_weight"] is None

            # Should fall through to heuristic (default 1.0)
            assert BlockProducer._miner_selection_weight(new_entry) == 1.0

            rotation = BlockProducer._build_balanced_producer_rotation(attested)
            assert "new_miner" in rotation

    def test_get_round_robin_producer_skips_zero_weight(self):
        """The full producer selection path must never return a zero-enroll miner."""
        with tempfile.TemporaryDirectory() as tmpdir:
            miners = [
                ("alice", "modern_x86", "desktop"),
                ("vm_miner", "modern_x86", "vm"),
            ]
            enroll = {"alice": 5, "vm_miner": 0}
            db_path, now_ts = _make_db(tmpdir, miners, enroll)

            bp = BlockProducer(db_path=db_path, tx_pool=None)
            # Use the slot that corresponds to now_ts so attestations are fresh
            base_slot = (now_ts - GENESIS_TIMESTAMP) // BLOCK_TIME

            # Check several slots near the current time
            for offset in range(min(5, base_slot + 1)):
                slot = base_slot - offset
                if slot < 0:
                    continue
                producer = bp.get_round_robin_producer(slot)
                assert producer == "alice", (
                    f"vm_miner with enroll_weight=0 was selected as producer at slot {slot}"
                )

    def test_all_zero_enroll_returns_none(self):
        """If all attested miners have zero enroll weight, no producer is selected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            miners = [
                ("vm1", "modern_x86", "vm"),
                ("vm2", "modern_x86", "vm"),
            ]
            enroll = {"vm1": 0, "vm2": 0}
            db_path, now_ts = _make_db(tmpdir, miners, enroll)

            bp = BlockProducer(db_path=db_path, tx_pool=None)
            base_slot = (now_ts - GENESIS_TIMESTAMP) // BLOCK_TIME
            producer = bp.get_round_robin_producer(base_slot)
            assert producer is None

    def test_no_enroll_table_graceful_fallback(self):
        """If epoch_enroll table doesn't exist, heuristic weights still work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            now_ts = int(time.time())

            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    CREATE TABLE miner_attest_recent (
                        miner TEXT PRIMARY KEY,
                        ts_ok INTEGER NOT NULL,
                        device_family TEXT,
                        device_arch TEXT,
                        device_model TEXT,
                        device_year INTEGER
                    )
                """)
                conn.execute(
                    "INSERT INTO miner_attest_recent (miner, ts_ok, device_arch, device_family) VALUES (?, ?, ?, ?)",
                    ("alice", now_ts, "modern_x86", "desktop"),
                )
                # No epoch_enroll table created

            bp = BlockProducer(db_path=db_path, tx_pool=None)
            attested = bp.get_attested_miners(now_ts)
            assert len(attested) == 1
            assert attested[0][2]["enroll_weight"] is None

            rotation = BlockProducer._build_balanced_producer_rotation(attested)
            assert "alice" in rotation
