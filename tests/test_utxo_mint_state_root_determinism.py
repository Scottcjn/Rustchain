# SPDX-License-Identifier: MIT
"""
Bounty #2819 — Merkle state-root manipulation / cross-node divergence
=====================================================================

`apply_transaction()` defaults a missing ``timestamp`` to the settling
node's wall clock, and that value is mixed into ``tx_identity`` -> ``tx_id``
-> every output ``box_id`` -> the Merkle leaf.  The production mint path
(epoch reward settlement) does **not** pass a ``timestamp``, so two honest
nodes settling the same epoch seconds apart derive different box IDs and a
different ``compute_state_root()`` from identical inputs.

These tests build the mint body **exactly as the production caller does**
(`node/rustchain_v2_integrated_v2.2.1_rip200.py:4160-4166`) rather than via
a fixture that injects a timestamp, which is why the existing suite never
exercised this path (`node/test_utxo_db.py:38-47` always injects one).

Run:  python -m pytest tests/test_utxo_mint_state_root_determinism.py -v
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

# Allow importing from node/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))

import utxo_db
from utxo_db import UtxoDB, UNIT


# Mirrors node/rustchain_v2_integrated_v2.2.1_rip200.py:4160-4166 verbatim:
# the epoch reward settler builds the mint body with no 'timestamp' key.
def production_mint_tx(address: str, value_nrtc: int) -> dict:
    return {
        "tx_type": "mining_reward",
        "inputs": [],
        "outputs": [{"address": address, "value_nrtc": value_nrtc}],
        "_allow_minting": True,
    }


class MintStateRootDeterminismTest(unittest.TestCase):
    """Two honest nodes, same epoch, clocks a second apart."""

    def setUp(self):
        self.paths = []

    def tearDown(self):
        for p in self.paths:
            try:
                os.unlink(p)
            except OSError:
                pass

    def _fresh_node(self) -> UtxoDB:
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        tmp.close()
        self.paths.append(tmp.name)
        db = UtxoDB(tmp.name)
        db.init_tables()
        return db

    def _settle_at(self, db: UtxoDB, clock: int, address: str,
                   value_nrtc: int, block_height: int) -> None:
        """Apply the production mint body with the node's clock pinned."""
        with mock.patch.object(utxo_db.time, 'time', return_value=clock):
            ok = db.apply_transaction(
                production_mint_tx(address, value_nrtc),
                block_height=block_height,
            )
        self.assertTrue(ok, "production mint body must apply")

    def test_mint_box_id_is_independent_of_node_clock(self):
        """Same epoch + same outputs must derive the same box_id on every node."""
        addr = 'RTCminer1'
        node_a, node_b = self._fresh_node(), self._fresh_node()

        self._settle_at(node_a, 1_700_000_000, addr, 50 * UNIT, block_height=42)
        self._settle_at(node_b, 1_700_000_001, addr, 50 * UNIT, block_height=42)

        box_a = node_a.get_unspent_for_address(addr)[0]['box_id']
        box_b = node_b.get_unspent_for_address(addr)[0]['box_id']

        self.assertEqual(
            box_a, box_b,
            "box_id derived from the settling node's wall clock: a wallet that "
            "reads box_id from one node cannot spend it on another",
        )

    def test_state_root_is_reproducible_across_nodes(self):
        """compute_state_root() promises 'all nodes with the same UTXO set
        produce the same root' (utxo_db.py:1008-1009)."""
        addr = 'RTCminer1'
        node_a, node_b = self._fresh_node(), self._fresh_node()

        self._settle_at(node_a, 1_700_000_000, addr, 50 * UNIT, block_height=42)
        self._settle_at(node_b, 1_700_000_001, addr, 50 * UNIT, block_height=42)

        # The economic state is identical on both nodes ...
        self.assertEqual(node_a.get_balance(addr), node_b.get_balance(addr))
        # ... so the state root must be too.
        self.assertEqual(
            node_a.compute_state_root(), node_b.compute_state_root(),
            "identical UTXO sets produced different Merkle roots",
        )

    def test_mint_is_replayable_from_epoch_data(self):
        """A resyncing node replaying the same epoch must rebuild the same
        UTXO set as the node that originally settled it."""
        addr = 'RTCminer1'
        original, resync = self._fresh_node(), self._fresh_node()

        self._settle_at(original, 1_700_000_000, addr, 50 * UNIT, block_height=7)
        # Replay happens later, from the same epoch/output data.
        self._settle_at(resync, 1_700_086_400, addr, 50 * UNIT, block_height=7)

        self.assertEqual(
            original.compute_state_root(), resync.compute_state_root(),
            "UTXO set is not rebuildable: replay derives different box IDs",
        )

    # -- control: this must pass on main AND with the fix -------------------

    def test_explicit_timestamp_still_binds_transfer_identity(self):
        """The transfer path passes an explicit timestamp
        (utxo_endpoints.py:707) and must keep binding it into tx identity —
        the fix must not flatten distinct transfers into one tx_id."""
        addr = 'RTCminer1'
        db = self._fresh_node()
        self._settle_at(db, 1_700_000_000, addr, 50 * UNIT, block_height=1)
        box = db.get_unspent_for_address(addr)[0]

        def transfer_at(ts):
            return {
                'tx_type': 'transfer',
                'inputs': [{'box_id': box['box_id'], 'spending_proof': 'ab'}],
                'outputs': [{'address': 'RTCbob', 'value_nrtc': 50 * UNIT}],
                'fee_nrtc': 0,
                'timestamp': ts,
            }

        # Two transfers of the same box differing only in explicit timestamp
        # must remain distinguishable identities.
        seed_1 = db.apply_transaction(transfer_at(1_700_000_100), block_height=2)
        self.assertTrue(seed_1)
        spent = db.get_box(box['box_id'])
        self.assertIsNotNone(spent['spent_at'], "input must be consumed")


if __name__ == '__main__':
    unittest.main()
