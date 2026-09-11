#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regression coverage for the epoch mining-reward mirror-provenance fix
(danaher-j #2819, same class as the /utxo/transfer receiver residual).

Under UTXO_DUAL_WRITE=1, epoch settlement credits each miner's ACCOUNT balance
AND mints a UTXO reward box for them. If that box is not registered in
account_mirror_boxes, the same reward is spendable via BOTH models (UTXO box +
account balance) = double spend. The fix (a) makes account_mirror_boxes canonical
UTXO schema, and (b) registers each reward box in finalize_epoch's dual-write
batch loop.

These tests avoid the expensive full-settlement harness (as the existing
test_epoch_utxo_dual_write_guard.py does for finalize_epoch) and instead cover:
  1. init_tables now creates account_mirror_boxes (schema),
  2. a registered reward box is excluded from UTXO spendable candidates
     (the mechanism that closes the double-spend), and
  3. finalize_epoch wires the registration into the dual-write path (source/AST).
"""
import ast
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

NODE_DIR = os.path.abspath(os.path.dirname(__file__))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

from utxo_db import UtxoDB, UNIT
from utxo_endpoints import _spendable_utxo_candidates

SERVER_PATH = Path(NODE_DIR) / "rustchain_v2_integrated_v2.2.1_rip200.py"


class TestRewardProvenanceSchemaAndMechanism(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        self.db = UtxoDB(self.db_path)
        self.db.init_tables()

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_init_tables_creates_account_mirror_boxes(self):
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='account_mirror_boxes'"
            ).fetchone()
            self.assertIsNotNone(row, "init_tables must create account_mirror_boxes (canonical schema)")
        finally:
            conn.close()

    def test_registered_reward_box_is_not_utxo_spendable(self):
        """A minted reward box that IS registered as mirror provenance must be
        excluded from UTXO coin-selection — so the reward can only move via the
        account path, closing the double-spend."""
        miner = 'miner-reward-1'
        height = 42 * 144  # epoch*EPOCH_SLOTS style height
        # Mint a reward box exactly as finalize_epoch does (mining_reward, minting).
        self.db.apply_transaction({
            'tx_type': 'mining_reward', 'inputs': [],
            'outputs': [{'address': miner, 'value_nrtc': 5 * UNIT}],
            'timestamp': int(time.time()), '_allow_minting': True,
        }, block_height=height)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Register exactly as the fix does: every box at this creation_height.
            for r in conn.execute(
                "SELECT box_id, owner_address, value_nrtc FROM utxo_boxes WHERE creation_height = ?",
                (height,),
            ).fetchall():
                conn.execute(
                    "INSERT OR IGNORE INTO account_mirror_boxes "
                    "(box_id, account_wallet, value_nrtc, created_epoch) VALUES (?,?,?,?)",
                    (r['box_id'], r['owner_address'], r['value_nrtc'], 42),
                )
            conn.commit()

            boxes = [dict(r) for r in conn.execute(
                "SELECT * FROM utxo_boxes WHERE owner_address=? AND spent_at IS NULL", (miner,)
            ).fetchall()]
            self.assertEqual(len(boxes), 1)
            spendable, mirrored = _spendable_utxo_candidates(conn, boxes)
            self.assertEqual(spendable, [], "reward box is UTXO-spendable — double-spend open")
            self.assertEqual(mirrored, [boxes[0]['box_id']])
        finally:
            conn.close()

    def test_unregistered_reward_box_would_be_spendable(self):
        """Control: WITHOUT registration the reward box IS UTXO-spendable — this is
        the double-spend the fix closes (and proves the mechanism test is meaningful)."""
        miner = 'miner-reward-2'
        self.db.apply_transaction({
            'tx_type': 'mining_reward', 'inputs': [],
            'outputs': [{'address': miner, 'value_nrtc': 5 * UNIT}],
            'timestamp': int(time.time()), '_allow_minting': True,
        }, block_height=99)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            boxes = [dict(r) for r in conn.execute(
                "SELECT * FROM utxo_boxes WHERE owner_address=? AND spent_at IS NULL", (miner,)
            ).fetchall()]
            spendable, mirrored = _spendable_utxo_candidates(conn, boxes)
            self.assertEqual(len(spendable), 1)
            self.assertEqual(mirrored, [])
        finally:
            conn.close()


class TestFinalizeEpochWiresRewardProvenance(unittest.TestCase):
    """Source-level: finalize_epoch registers reward boxes as mirror provenance
    inside its dual-write batch loop (same convention as test_epoch_utxo_dual_write_guard)."""

    def _finalize_source(self):
        source = SERVER_PATH.read_text(encoding='utf-8')
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == 'finalize_epoch':
                return ast.get_source_segment(source, node)
        raise AssertionError('finalize_epoch() not found')

    def test_finalize_epoch_registers_reward_mirror_provenance(self):
        src = self._finalize_source()
        self.assertIn("INSERT OR IGNORE INTO account_mirror_boxes", src,
                      "finalize_epoch must register reward boxes as mirror provenance")
        self.assertIn("creation_height = ?", src,
                      "reward boxes must be located by their batch creation_height")
        # Registration must live inside the UTXO_DUAL_WRITE block.
        gate = src.index("if UTXO_DUAL_WRITE and utxo_reward_outputs")
        reg = src.index("INSERT OR IGNORE INTO account_mirror_boxes")
        self.assertGreater(reg, gate, "registration must be inside the dual-write block")


if __name__ == '__main__':
    unittest.main()
