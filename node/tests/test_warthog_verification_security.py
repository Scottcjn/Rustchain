# SPDX-License-Identifier: MIT
"""
Tests for Warthog dual-mining verification security and anti-Sybil guarantees.
Covers:
1. Proof freshness enforcement (omitted, 0, None, float('nan'), float('inf'), stale timestamps).
2. Numerical validation for pool hashrate and node balance (NaN, Inf, negative, zero).
3. Anti-Sybil single-claim per wart_address per epoch enforcement.
"""

import time
import math
import sqlite3
import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NODE_DIR = PROJECT_ROOT / "node"
if str(NODE_DIR) not in sys.path:
    sys.path.insert(0, str(NODE_DIR))

import warthog_verification as wv


class WarthogVerificationSecurityTests(unittest.TestCase):
    def setUp(self):
        self.valid_node_proof = {
            "enabled": True,
            "wart_address": "wart1qtestvalidaddress123456",
            "proof_type": "own_node",
            "node": {"height": 500000, "synced": True},
            "balance": "50.0",
            "collected_at": int(time.time()),
        }
        self.valid_pool_proof = {
            "enabled": True,
            "wart_address": "wart1qtestvalidaddress123456",
            "proof_type": "pool",
            "pool": {"url": "https://acc-pool.pw", "hashrate": 125.0},
            "collected_at": int(time.time()),
        }

    def test_missing_or_zero_collected_at_is_rejected(self):
        """Omitting collected_at or sending 0 must fail rather than bypass age checks."""
        for bad_ts in (None, 0, "", {}, [], False):
            p = dict(self.valid_node_proof)
            if bad_ts is None:
                p.pop("collected_at", None)
            else:
                p["collected_at"] = bad_ts
            ok, tier, reason = wv.verify_warthog_proof(p, "miner_1")
            self.assertFalse(ok, f"Expected False for collected_at={bad_ts!r}")
            self.assertEqual(tier, wv.WART_BONUS_NONE)
            self.assertEqual(reason, "proof_stale_or_missing_timestamp")

    def test_non_finite_collected_at_is_rejected(self):
        """NaN and Inf timestamps must not bypass time delta calculations."""
        for bad_ts in (float("nan"), float("inf"), float("-inf")):
            p = dict(self.valid_node_proof)
            p["collected_at"] = bad_ts
            ok, tier, reason = wv.verify_warthog_proof(p, "miner_1")
            self.assertFalse(ok)
            self.assertEqual(tier, wv.WART_BONUS_NONE)
            self.assertEqual(reason, "proof_stale_or_missing_timestamp")

    def test_stale_timestamp_is_rejected(self):
        """Timestamps older than MAX_PROOF_AGE must be rejected."""
        p = dict(self.valid_node_proof)
        p["collected_at"] = int(time.time()) - (wv.MAX_PROOF_AGE + 60)
        ok, tier, reason = wv.verify_warthog_proof(p, "miner_1")
        self.assertFalse(ok)
        self.assertEqual(tier, wv.WART_BONUS_NONE)
        self.assertEqual(reason, "proof_stale_or_missing_timestamp")

    def test_pool_hashrate_non_finite_or_zero_is_rejected(self):
        """hashrate = NaN, Inf, 0, or negative must be rejected."""
        for bad_rate in (float("nan"), float("inf"), float("-inf"), 0, -10.0, None, "100"):
            p = dict(self.valid_pool_proof)
            p["pool"] = {"url": "https://acc-pool.pw", "hashrate": bad_rate}
            ok, tier, reason = wv.verify_warthog_proof(p, "miner_1")
            self.assertFalse(ok, f"Expected False for hashrate={bad_rate!r}")
            self.assertEqual(tier, wv.WART_BONUS_NONE)
            self.assertEqual(reason, "pool_zero_hashrate")

    def test_node_balance_non_finite_is_handled_safely(self):
        """Non-finite balance values must not crash and should downgrade to pool tier."""
        for bad_bal in ("nan", "inf", "-inf", "not_a_number"):
            p = dict(self.valid_node_proof)
            p["balance"] = bad_bal
            ok, tier, reason = wv.verify_warthog_proof(p, "miner_1")
            self.assertTrue(ok)
            self.assertEqual(tier, wv.WART_BONUS_POOL)
            self.assertEqual(reason, "node_no_balance_downgraded")

    def test_sybil_multi_miner_address_reuse_rejected_in_same_epoch(self):
        """A single wart_address cannot be claimed by multiple miners in the same epoch."""
        conn = sqlite3.connect(":memory:")
        wv.init_warthog_tables(conn)

        shared_addr = "wart1qsharedpublicwhaleaddr9999"
        proof_miner1 = dict(self.valid_node_proof, wart_address=shared_addr)
        proof_miner2 = dict(self.valid_node_proof, wart_address=shared_addr)

        # Miner 1 records verified proof in epoch 50
        v1, t1, r1 = wv.verify_warthog_proof(proof_miner1, "miner_1")
        self.assertTrue(v1)
        rec_v1, rec_t1, rec_r1 = wv.record_warthog_proof(
            conn, "miner_1", epoch=50, proof=proof_miner1, verified=v1, bonus_tier=t1, reason=r1
        )
        self.assertTrue(rec_v1)
        self.assertEqual(rec_t1, wv.WART_BONUS_NODE)

        # Miner 2 attempts to record same wart_address in epoch 50
        v2, t2, r2 = wv.verify_warthog_proof(proof_miner2, "miner_2")
        self.assertTrue(v2)
        rec_v2, rec_t2, rec_r2 = wv.record_warthog_proof(
            conn, "miner_2", epoch=50, proof=proof_miner2, verified=v2, bonus_tier=t2, reason=r2
        )
        self.assertFalse(rec_v2, "Duplicate address in same epoch must be rejected")
        self.assertEqual(rec_t2, wv.WART_BONUS_NONE)
        self.assertIn("wart_address_already_claimed", rec_r2)

        # Verify only miner 1 holds verified=1 for that address in epoch 50
        verified_count = conn.execute(
            "SELECT COUNT(*) FROM warthog_mining_proofs WHERE wart_address = ? AND epoch = 50 AND verified = 1",
            (shared_addr,)
        ).fetchone()[0]
        self.assertEqual(verified_count, 1)

        # Miner 1 can re-attest / update their own record without error
        rec_v1_re, rec_t1_re, _ = wv.record_warthog_proof(
            conn, "miner_1", epoch=50, proof=proof_miner1, verified=True, bonus_tier=wv.WART_BONUS_NODE, reason="re-attest"
        )
        self.assertTrue(rec_v1_re)
        self.assertEqual(rec_t1_re, wv.WART_BONUS_NODE)

        # In a new epoch (epoch 51), legitimate address rotation/reuse across epochs is permitted
        rec_v2_next_epoch, rec_t2_next_epoch, _ = wv.record_warthog_proof(
            conn, "miner_2", epoch=51, proof=proof_miner2, verified=True, bonus_tier=wv.WART_BONUS_NODE, reason="new_epoch"
        )
        self.assertTrue(rec_v2_next_epoch)
        self.assertEqual(rec_t2_next_epoch, wv.WART_BONUS_NODE)

        conn.close()


if __name__ == "__main__":
    unittest.main()
