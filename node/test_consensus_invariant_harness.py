"""
Reference harness for consensus-invariant attractor submissions.

Run from the node directory:
    python -m unittest test_consensus_invariant_harness.py -v

Each example test pins one objective invariant and keeps setup, action, and
expected result close to the assertion so future bounty submissions are easy
to review without interpreting a long narrative.
"""

import contextlib
import io
import os
import sqlite3
import tempfile
import time
import unittest
from dataclasses import dataclass

from utxo_db import UNIT, UtxoDB
from utxo_genesis_migration import migrate


@dataclass(frozen=True)
class InvariantSpec:
    """Machine-readable header for one consensus-invariant test."""

    invariant_id: str
    claim: str
    setup: str
    action: str
    expected: str


class ConsensusInvariantCase(unittest.TestCase):
    """Small helpers shared by one-invariant-per-test attractor cases."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def assert_invariant(self, spec: InvariantSpec, condition: bool, detail: str = ""):
        if not condition:
            suffix = f" Detail: {detail}" if detail else ""
            self.fail(f"{spec.invariant_id} violated: {spec.claim}.{suffix}")

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
            return {
                "unspent_count": conn.execute(
                    "SELECT COUNT(*) AS n FROM utxo_boxes WHERE spent_at IS NULL"
                ).fetchone()["n"],
                "unspent_total": self.unspent_total(),
                "alice": self.db.get_balance("alice"),
                "bob": self.db.get_balance("bob"),
                "root": self.db.compute_state_root(),
            }
        finally:
            conn.close()

    def mint(self, address: str, value_nrtc: int, block_height: int = 1):
        ok = self.db.apply_transaction(
            {
                "tx_type": "mining_reward",
                "inputs": [],
                "outputs": [{"address": address, "value_nrtc": value_nrtc}],
                "fee_nrtc": 0,
                "timestamp": int(time.time()),
                "_allow_minting": True,
            },
            block_height=block_height,
        )
        self.assertTrue(ok)


class TestConsensusInvariantHarness(ConsensusInvariantCase):
    def test_non_mint_transfer_preserves_value_except_declared_fee(self):
        spec = InvariantSpec(
            invariant_id="utxo-conservation-001",
            claim="non-mint transactions cannot create value",
            setup="mint one 100 RTC UTXO to alice",
            action="spend it into two outputs with an explicit 5 RTC fee",
            expected="unspent supply decreases by exactly the declared fee",
        )
        self.mint("alice", 100 * UNIT)
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
                "timestamp": int(time.time()),
            },
            block_height=2,
        )

        self.assertTrue(ok)
        after_total = self.unspent_total()
        self.assert_invariant(
            spec,
            before_total - after_total == fee,
            f"before={before_total} after={after_total} fee={fee}",
        )

    def test_spent_input_cannot_be_applied_twice(self):
        spec = InvariantSpec(
            invariant_id="utxo-double-spend-001",
            claim="a spent UTXO cannot be consumed by a later transaction",
            setup="mint one 20 RTC UTXO to alice",
            action="apply the same spend twice",
            expected="the second apply fails and the post-first state is unchanged",
        )
        self.mint("alice", 20 * UNIT)
        box = self.db.get_unspent_for_address("alice")[0]
        tx = {
            "tx_type": "transfer",
            "inputs": [{"box_id": box["box_id"], "spending_proof": "sig"}],
            "outputs": [{"address": "bob", "value_nrtc": 20 * UNIT}],
            "fee_nrtc": 0,
            "timestamp": int(time.time()),
        }

        self.assertTrue(self.db.apply_transaction(tx, block_height=2))
        after_first = self.state_snapshot()
        self.assertFalse(self.db.apply_transaction(tx, block_height=3))
        after_second = self.state_snapshot()

        self.assert_invariant(
            spec,
            after_first == after_second,
            f"after_first={after_first} after_second={after_second}",
        )

    def test_genesis_migration_is_idempotent_by_refusing_rerun(self):
        spec = InvariantSpec(
            invariant_id="genesis-idempotency-001",
            claim="genesis migration cannot duplicate account balances",
            setup="create two positive account balances and run migration once",
            action="run the same migration a second time",
            expected="the second run returns genesis_already_exists and leaves UTXO state unchanged",
        )
        conn = sqlite3.connect(self.tmp.name)
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
            first = migrate(self.tmp.name)
        after_first = self.state_snapshot()

        with contextlib.redirect_stdout(io.StringIO()):
            second = migrate(self.tmp.name)
        after_second = self.state_snapshot()

        self.assertEqual(first["wallets_migrated"], 2)
        self.assertEqual(second.get("error"), "genesis_already_exists")
        self.assert_invariant(
            spec,
            after_first == after_second,
            f"after_first={after_first} after_second={after_second}",
        )


if __name__ == "__main__":
    unittest.main()
