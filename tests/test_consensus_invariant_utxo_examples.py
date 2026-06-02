#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""UTXO examples for the consensus invariant attractor harness."""

import contextlib
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "node"))

from utxo_db import UNIT, UtxoDB
from utxo_genesis_migration import migrate
from tests.consensus_invariant_harness import (
    ConsensusInvariantCase,
    assert_consensus_invariant,
)


class TestConsensusInvariantUtxoExamples(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.db_path = tmp.name
        self.db = UtxoDB(self.db_path)
        self.db.init_tables()

    def tearDown(self):
        for path in (self.db_path, f"{self.db_path}-wal", f"{self.db_path}-shm"):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass

    def unspent_total(self) -> int:
        conn = self.db._conn()
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(value_nrtc), 0) AS total "
                "FROM utxo_boxes WHERE spent_at IS NULL"
            ).fetchone()
            return int(row["total"])
        finally:
            conn.close()

    def state_snapshot(self) -> dict:
        conn = self.db._conn()
        try:
            total = conn.execute(
                "SELECT COALESCE(SUM(value_nrtc), 0) AS total "
                "FROM utxo_boxes WHERE spent_at IS NULL"
            ).fetchone()["total"]
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM utxo_boxes WHERE spent_at IS NULL"
            ).fetchone()["n"]
        finally:
            conn.close()

        return {
            "unspent_count": count,
            "unspent_total": int(total),
            "alice": self.db.get_balance("alice"),
            "bob": self.db.get_balance("bob"),
            "root": self.db.compute_state_root(),
        }

    def mint(self, address: str, value_nrtc: int, block_height: int, timestamp: int):
        ok = self.db.apply_transaction(
            {
                "tx_type": "mining_reward",
                "inputs": [],
                "outputs": [{"address": address, "value_nrtc": value_nrtc}],
                "fee_nrtc": 0,
                "timestamp": timestamp,
                "_allow_minting": True,
            },
            block_height=block_height,
        )
        self.assertTrue(ok)

    def test_consensus__utxo_supply_conserved__declared_fee_only(self):
        def oracle():
            self.mint("alice", 100 * UNIT, block_height=1, timestamp=1728000000)
            before_total = self.unspent_total()
            box = self.db.get_unspent_for_address("alice")[0]
            fee = 5 * UNIT

            ok = self.db.apply_transaction(
                {
                    "tx_type": "transfer",
                    "inputs": [{"box_id": box["box_id"], "spending_proof": "sig"}],
                    "outputs": [
                        {"address": "bob", "value_nrtc": 60 * UNIT},
                        {"address": "alice", "value_nrtc": 35 * UNIT},
                    ],
                    "fee_nrtc": fee,
                    "timestamp": 1728000001,
                },
                block_height=2,
            )

            self.assertTrue(ok)
            self.assertEqual(before_total - self.unspent_total(), fee)

        assert_consensus_invariant(
            ConsensusInvariantCase(
                invariant_id="consensus.utxo.supply_conserved_after_fee",
                statement="A non-mint UTXO transfer can only reduce unspent supply by its declared fee.",
                fixture="One fixed-height 100 RTC mining reward UTXO owned by alice.",
                adversarial_move="Spend the box into two outputs while declaring a 5 RTC fee.",
                oracle=oracle,
            )
        )

    def test_consensus__utxo_double_spend_rejected__state_unchanged(self):
        def oracle():
            self.mint("alice", 20 * UNIT, block_height=1, timestamp=1728000100)
            box = self.db.get_unspent_for_address("alice")[0]
            tx = {
                "tx_type": "transfer",
                "inputs": [{"box_id": box["box_id"], "spending_proof": "sig"}],
                "outputs": [{"address": "bob", "value_nrtc": 20 * UNIT}],
                "fee_nrtc": 0,
                "timestamp": 1728000101,
            }

            self.assertTrue(self.db.apply_transaction(tx, block_height=2))
            after_first = self.state_snapshot()
            self.assertFalse(self.db.apply_transaction(tx, block_height=3))
            self.assertEqual(after_first, self.state_snapshot())

        assert_consensus_invariant(
            ConsensusInvariantCase(
                invariant_id="consensus.utxo.double_spend_rejected",
                statement="A spent UTXO cannot be consumed by a later transaction.",
                fixture="One fixed-height 20 RTC mining reward UTXO owned by alice.",
                adversarial_move="Apply the same spend transaction twice.",
                oracle=oracle,
            )
        )

    def test_consensus__genesis_migration_rerun_refused__state_unchanged(self):
        def oracle():
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)"
                )
                conn.executemany(
                    "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                    [("alice", 7), ("bob", 11)],
                )
                conn.commit()
            finally:
                conn.close()

            with contextlib.redirect_stdout(io.StringIO()):
                first = migrate(self.db_path)
            after_first = self.state_snapshot()

            with contextlib.redirect_stdout(io.StringIO()):
                second = migrate(self.db_path)

            self.assertEqual(first["wallets_migrated"], 2)
            self.assertEqual(second.get("error"), "genesis_already_exists")
            self.assertEqual(after_first, self.state_snapshot())

        assert_consensus_invariant(
            ConsensusInvariantCase(
                invariant_id="consensus.genesis.idempotent_rerun_refused",
                statement="Genesis migration cannot duplicate account balances when rerun.",
                fixture="Two positive legacy account balances migrated into genesis UTXOs.",
                adversarial_move="Run the same genesis migration a second time.",
                oracle=oracle,
            )
        )


if __name__ == "__main__":
    unittest.main()
