#!/usr/bin/env python3
"""
Tests for BFT view-change signature verification (CRIT-BFT-1).

Demonstrates that unsigned or forged view-change messages are rejected,
preventing unauthenticated consensus leader hijacking.
"""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rustchain_bft_consensus import BFTConsensus, MessageType, CONSENSUS_MESSAGE_TTL


SECRET_KEY = "test_bft_key_for_unit_tests_2025"


class TestBFTViewChangeSecurity(unittest.TestCase):
    """CRIT-BFT-1: View-change messages must be HMAC-authenticated."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.bft = BFTConsensus("node-A", self.tmp.name, SECRET_KEY)
        # Register peers so quorum math is meaningful (4 nodes, quorum=3)
        self.bft.register_peer("node-B", "http://localhost:9001")
        self.bft.register_peer("node-C", "http://localhost:9002")
        self.bft.register_peer("node-D", "http://localhost:9003")

    def tearDown(self):
        # Cancel any pending view-change timers that hold DB connections
        self.bft._cancel_view_change_timer()
        try:
            os.unlink(self.tmp.name)
        except PermissionError:
            pass  # Windows file locking; temp dir cleanup handles it

    def _make_valid_vc(self, node_id: str, view: int) -> dict:
        """Construct a properly signed view-change message."""
        ts = int(time.time())
        sign_data = f"{MessageType.VIEW_CHANGE.value}:{view}:{self.bft.current_epoch}:{ts}"
        sig = self.bft._sign_message(sign_data)
        return {
            "view": view,
            "epoch": self.bft.current_epoch,
            "node_id": node_id,
            "prepared_cert": None,
            "signature": sig,
            "timestamp": ts,
        }

    # -- Tests ---------------------------------------------------------------

    def test_unsigned_view_change_rejected(self):
        """Unsigned view-change must NOT be accepted."""
        self.bft.handle_view_change({
            "view": 1,
            "epoch": 0,
            "node_id": "attacker",
            "prepared_cert": None,
            "signature": "",            # empty signature
            "timestamp": int(time.time()),
        })
        # attacker should NOT be in the log
        self.assertNotIn("attacker", self.bft.view_change_log.get(1, {}))

    def test_forged_signature_rejected(self):
        """View-change with wrong HMAC must be rejected."""
        self.bft.handle_view_change({
            "view": 1,
            "epoch": 0,
            "node_id": "node-B",
            "prepared_cert": None,
            "signature": "deadbeef" * 8,  # forged
            "timestamp": int(time.time()),
        })
        self.assertNotIn("node-B", self.bft.view_change_log.get(1, {}))

    def test_stale_view_change_rejected(self):
        """View-change for a past or current view must be rejected."""
        # current_view is 0, so view=0 is stale
        msg = self._make_valid_vc("node-B", view=0)
        self.bft.handle_view_change(msg)
        self.assertNotIn("node-B", self.bft.view_change_log.get(0, {}))

    def test_expired_timestamp_rejected(self):
        """View-change with timestamp outside TTL window must be rejected."""
        ts = int(time.time()) - CONSENSUS_MESSAGE_TTL - 60
        sign_data = f"{MessageType.VIEW_CHANGE.value}:1:{self.bft.current_epoch}:{ts}"
        sig = self.bft._sign_message(sign_data)
        self.bft.handle_view_change({
            "view": 1,
            "epoch": 0,
            "node_id": "node-B",
            "prepared_cert": None,
            "signature": sig,
            "timestamp": ts,
        })
        self.assertNotIn("node-B", self.bft.view_change_log.get(1, {}))

    def test_valid_view_change_accepted(self):
        """Properly signed and fresh view-change must be accepted."""
        msg = self._make_valid_vc("node-B", view=1)
        self.bft.handle_view_change(msg)
        self.assertIn("node-B", self.bft.view_change_log.get(1, {}))

    def test_spoofed_node_id_rejected(self):
        """Attacker cannot spoof node_id with fake identities to reach quorum.

        Before the fix, an attacker could send 3 unsigned messages with
        node_ids 'node-B', 'node-C', 'node-D' to reach quorum and
        force a view change. Now each must have a valid HMAC.
        """
        initial_view = self.bft.current_view
        for fake_id in ["node-B", "node-C", "node-D"]:
            self.bft.handle_view_change({
                "view": 1,
                "epoch": 0,
                "node_id": fake_id,
                "prepared_cert": None,
                "signature": "fake_sig_000000000000000000000000",
                "timestamp": int(time.time()),
            })
        # View should NOT have changed
        self.assertEqual(self.bft.current_view, initial_view)
        # Log should be empty — all were rejected
        self.assertEqual(len(self.bft.view_change_log.get(1, {})), 0)


if __name__ == "__main__":
    unittest.main()
