#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""PoC for fee-ordered mempool candidate scan-window starvation.

Issue: rustchain-bounties#2819

Transactions that conflict only at block assembly time are valid mempool
entries.  A high-fee spend followed by enough lower-fee transactions that use
the spent box as a read-only data input can consume the bounded candidate scan
window.  Independent transactions below that window are never considered, so
a block producer receives fewer than ``max_count`` candidates despite eligible
transactions being available.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UNIT, UtxoDB


class TestMempoolCandidateScanStarvation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _mint(self, address, height):
        self.assertTrue(
            self.db.apply_transaction(
                {
                    "tx_type": "mining_reward",
                    "inputs": [],
                    "outputs": [{"address": address, "value_nrtc": 10 * UNIT}],
                    "fee_nrtc": 0,
                    "_allow_minting": True,
                },
                block_height=height,
            )
        )
        return self.db.get_unspent_for_address(address)[0]

    def _add_transfer(self, tx_id, source_box, fee, data_inputs=None):
        self.assertTrue(
            self.db.mempool_add(
                {
                    "tx_id": tx_id,
                    "inputs": [{"box_id": source_box["box_id"]}],
                    "data_inputs": data_inputs or [],
                    "outputs": [
                        {
                            "address": f"recipient-{tx_id}",
                            "value_nrtc": source_box["value_nrtc"] - fee,
                        }
                    ],
                    "fee_nrtc": fee,
                    "timestamp": 1_800_000_000,
                }
            )
        )

    def test_conflicts_cannot_hide_independent_candidates_below_scan_window(self):
        """Candidate selection should fill the requested block when possible."""
        oracle_box = self._mint("oracle", 1)
        conflict_boxes = [
            self._mint(f"conflict-{index}", index + 2)
            for index in range(7)
        ]
        independent_box = self._mint("independent", 9)

        # Highest-fee transaction spends the oracle box.
        self._add_transfer("spend-oracle", oracle_box, fee=10_000)

        # Seven valid transactions consume the rest of the 2 * 4 scan window.
        # They cannot share a block with spend-oracle because they read the box
        # it spends, but they remain valid mempool entries.
        for index, box in enumerate(conflict_boxes):
            self._add_transfer(
                f"conflict-{index}",
                box,
                fee=9_000 - index,
                data_inputs=[oracle_box["box_id"]],
            )

        # This independent transaction is eligible but falls immediately below
        # the bounded scan window.
        self._add_transfer("independent", independent_box, fee=1)

        candidates = self.db.mempool_get_block_candidates(max_count=2)

        self.assertEqual(
            [tx["tx_id"] for tx in candidates],
            ["spend-oracle", "independent"],
            "MEDIUM: conflicting high-fee rows starve eligible transactions "
            "below the bounded candidate scan window",
        )

    def test_pagination_does_not_skip_transactions_with_equal_fees(self):
        """The continuation cursor must be deterministic across fee ties."""
        oracle_box = self._mint("oracle", 1)
        conflict_boxes = [
            self._mint(f"conflict-{index}", index + 2)
            for index in range(7)
        ]
        independent_box = self._mint("independent", 9)

        self._add_transfer("a-spend-oracle", oracle_box, fee=10_000)
        for index, box in enumerate(conflict_boxes):
            self._add_transfer(
                f"b-conflict-{index}",
                box,
                fee=10_000,
                data_inputs=[oracle_box["box_id"]],
            )
        self._add_transfer("z-independent", independent_box, fee=10_000)

        candidates = self.db.mempool_get_block_candidates(max_count=2)

        self.assertEqual(
            [tx["tx_id"] for tx in candidates],
            ["a-spend-oracle", "z-independent"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
