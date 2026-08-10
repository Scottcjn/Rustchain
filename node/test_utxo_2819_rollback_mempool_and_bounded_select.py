#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Regression tests for two findings on bounty #2819.

Reported by @AInoAKARI.

1. rollback_genesis() left mempool claims behind. Genesis box ids are
   deterministic, so re-running the migration recreated the exact box a stale
   pending transaction still claimed, and it came back already reserved.

2. utxo_transfer() coin selection fetched every unspent box for the sender.
   Anyone can send dust to any address, so a third party could fragment a
   wallet and inflate the cost of its owner's transfers.
"""

import hashlib
import os
import sqlite3
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_genesis_migration import migrate, rollback_genesis
from utxo_db import (
    UtxoDB,
    UNIT,
    MAX_COINBASE_OUTPUT_NRTC,
    COIN_SELECT_MAX_INPUTS,
    coin_select,
)


class TestRollbackEvictsMempoolClaims(unittest.TestCase):
    """Finding 1: rollback must clear pending intent, not just state."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "rollback_mempool.db")
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS balances (
                   miner_id TEXT PRIMARY KEY,
                   amount_i64 INTEGER NOT NULL DEFAULT 0
               )"""
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?,?)",
            ("wallet_a", 100 * UNIT),
        )
        conn.commit()
        conn.close()
        self.db = UtxoDB(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _genesis_box_id(self):
        boxes = self.db.get_unspent_for_address("wallet_a")
        self.assertEqual(len(boxes), 1, "expected exactly one genesis box")
        return boxes[0]["box_id"]

    def test_stale_claim_does_not_survive_rollback_and_remigrate(self):
        migrate(self.db_path, dry_run=False)
        box_id = self._genesis_box_id()
        box_value = self.db.get_unspent_for_address("wallet_a")[0]["value_nrtc"]

        ok = self.db.mempool_add(
            {
                "tx_id": "pending_before_rollback",
                "tx_type": "transfer",
                "inputs": [{"box_id": box_id, "spending_proof": "sig"}],
                "outputs": [{"address": "wallet_b", "value_nrtc": box_value}],
                "fee_nrtc": 0,
            }
        )
        self.assertTrue(ok, "mempool should accept a spend of the genesis box")
        self.assertTrue(
            self.db.mempool_check_double_spend(box_id),
            "precondition: the box is claimed while the tx is pending",
        )

        rollback_genesis(self.db_path)

        self.assertFalse(
            self.db.mempool_check_double_spend(box_id),
            "rollback must not leave a claim on a box it deleted",
        )

        # Same balances in, so the migration is expected to rebuild the very
        # same box id. That determinism is what made the stale claim dangerous.
        migrate(self.db_path, dry_run=False)
        self.assertEqual(
            self._genesis_box_id(),
            box_id,
            "precondition: genesis box ids are deterministic",
        )
        self.assertFalse(
            self.db.mempool_check_double_spend(box_id),
            "a freshly migrated box must not be born already reserved",
        )

    def test_rollback_leaves_unrelated_mempool_entries_alone(self):
        """Eviction must be scoped to genesis boxes, not the whole mempool."""
        migrate(self.db_path, dry_run=False)
        genesis_box = self._genesis_box_id()
        genesis_value = self.db.get_unspent_for_address("wallet_a")[0]["value_nrtc"]

        self.db.apply_transaction(
            {
                "tx_id": "coinbase_for_carol",
                "tx_type": "mining_reward",
                "inputs": [],
                "outputs": [{"address": "carol", "value_nrtc": 50 * UNIT}],
                "fee_nrtc": 0,
                "_allow_minting": True,
            },
            block_height=1,
        )
        carol_box = self.db.get_unspent_for_address("carol")[0]["box_id"]

        self.db.mempool_add(
            {
                "tx_id": "genesis_spender",
                "tx_type": "transfer",
                "inputs": [{"box_id": genesis_box, "spending_proof": "sig"}],
                "outputs": [{"address": "wallet_b", "value_nrtc": genesis_value}],
                "fee_nrtc": 0,
            }
        )
        self.db.mempool_add(
            {
                "tx_id": "unrelated_spender",
                "tx_type": "transfer",
                "inputs": [{"box_id": carol_box, "spending_proof": "sig"}],
                "outputs": [{"address": "dave", "value_nrtc": 50 * UNIT}],
                "fee_nrtc": 0,
            }
        )

        # Non-genesis UTXO state exists, so rollback is expected to refuse.
        with self.assertRaises(RuntimeError):
            rollback_genesis(self.db_path)

        # And having refused, it must not have evicted anything.
        self.assertTrue(self.db.mempool_check_double_spend(genesis_box))
        self.assertTrue(self.db.mempool_check_double_spend(carol_box))


class TestBoundedCoinSelectCandidates(unittest.TestCase):
    """Finding 2: coin selection must not scale with wallet fragmentation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "bounded_select.db")
        self.db = UtxoDB(self.db_path)
        self.db.init_tables()
        self._next_block = 1

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _fragment(self, address, count, value_nrtc):
        """Give `address` `count` boxes, the way a dust sender would.

        Uses the real minting path in batches, since MAX_OUTPUTS caps how many
        boxes one transaction may create.
        """
        # A minting tx may not exceed MAX_COINBASE_OUTPUT_NRTC in total, and
        # MAX_OUTPUTS caps how many boxes one tx may create, so size batches to
        # respect both.
        per_batch = min(100, max(1, MAX_COINBASE_OUTPUT_NRTC // value_nrtc))
        remaining = count
        batch = 0
        while remaining > 0:
            n = min(remaining, per_batch)
            tx_id = hashlib.sha256(
                f"frag:{address}:{batch}".encode()
            ).hexdigest()
            ok = self.db.apply_transaction(
                {
                    "tx_id": tx_id,
                    "tx_type": "mining_reward",
                    "inputs": [],
                    "outputs": [
                        {"address": address, "value_nrtc": value_nrtc}
                        for _ in range(n)
                    ],
                    "fee_nrtc": 0,
                    "_allow_minting": True,
                },
                block_height=self._next_block,
            )
            self.assertTrue(ok, f"failed to mint fragment batch {batch}")
            self._next_block += 1
            remaining -= n
            batch += 1

    def test_candidate_set_is_bounded(self):
        self._fragment("victim", 500, 1000)
        candidates = self.db.get_coin_select_candidates("victim")
        self.assertLessEqual(
            len(candidates),
            2 * COIN_SELECT_MAX_INPUTS + 1,
            "candidate set must not grow with the size of the wallet",
        )
        self.assertEqual(
            len(self.db.get_unspent_for_address("victim")),
            500,
            "precondition: the wallet really is fragmented",
        )

    def test_candidates_are_deduplicated(self):
        """The two slices overlap on small wallets and must not double up."""
        self._fragment("small", 5, 1000)
        candidates = self.db.get_coin_select_candidates("small")
        ids = [c["box_id"] for c in candidates]
        self.assertEqual(len(ids), len(set(ids)), "duplicate boxes returned")
        self.assertEqual(len(ids), 5, "a small wallet returns every box once")

    def test_selection_matches_unbounded_input(self):
        """Bounded candidates must not change what coin_select() picks."""
        cases = [
            ("dusty", 300, 1000, 5000),          # many tiny boxes
            ("mixed", 60, 1 * UNIT, 15 * UNIT),   # comfortably covered
            ("tight", 40, 1000, 39_000),          # needs most of the wallet
        ]
        for address, count, value, target in cases:
            with self.subTest(address=address):
                self._fragment(address, count, value)
                full = self.db.get_unspent_for_address(address)
                bounded = self.db.get_coin_select_candidates(address)

                sel_full, change_full = coin_select(full, target)
                sel_bounded, change_bounded = coin_select(bounded, target)

                self.assertEqual(
                    sorted(b["box_id"] for b in sel_full),
                    sorted(b["box_id"] for b in sel_bounded),
                    f"{address}: bounded selection diverged from unbounded",
                )
                self.assertEqual(change_full, change_bounded)

    def test_insufficient_funds_still_reported(self):
        """A bounded fetch must not turn 'too poor' into a wrong selection."""
        self._fragment("poor", 100, 1000)  # 100_000 nrtc total
        bounded = self.db.get_coin_select_candidates("poor")
        selected, change = coin_select(bounded, 10 * UNIT)
        self.assertEqual(selected, [])
        self.assertEqual(change, 0)

    def test_rejects_bad_max_inputs(self):
        for bad in (0, -1, True, "20", None):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.db.get_coin_select_candidates("anyone", max_inputs=bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
