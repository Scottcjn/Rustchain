"""Tests for the async OTC settlement state machine + reconcile_settlements().

These exercise the v3 confirm-before-finalize / durable-recovery logic in
isolation by mocking the two external touch-points (the node payout-status
lookup and the escrow refund), so no live node is required.
"""
import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

_fd, _TEST_DB = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["OTC_DB_PATH"] = _TEST_DB
os.environ["OTC_RECONCILE_INTERVAL_SECONDS"] = "0"  # no background timer in tests
os.environ["OTC_RECONCILE_DISABLED"] = "1"          # never auto-reconcile on import/request

import otc_bridge
from otc_bridge import init_db, reconcile_settlements


def _seed_order(db_path, order_id, status, *, side="sell", escrow="job-1",
                expires_in=3600, settlement_tx="quote-tx", matched_age=10_000):
    now = int(time.time())
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO orders
           (order_id, side, pair, maker_wallet, amount_micro_rtc,
            price_per_rtc_nano_quote, total_quote_nano, status, escrow_job_id,
            htlc_hash, htlc_secret, taker_wallet, settlement_tx,
            created_at, matched_at, expires_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (order_id, side, "RTC/USDC", "rtc_maker", 10_000_000, 1_000_000_000,
         10_000_000_000, status, escrow, "h", "secret", "rtc_taker",
         settlement_tx, now - matched_age, now - matched_age, now + expires_in),
    )
    conn.commit()
    conn.close()


class ReconcileSettlementsTest(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        otc_bridge.DB_PATH = self.db
        init_db()

    def tearDown(self):
        try:
            os.unlink(self.db)
        except OSError:
            pass

    def _status(self, order_id):
        conn = sqlite3.connect(self.db)
        row = conn.execute("SELECT status FROM orders WHERE order_id=?", (order_id,)).fetchone()
        conn.close()
        return row[0] if row else None

    def _trade_count(self, order_id):
        conn = sqlite3.connect(self.db)
        n = conn.execute("SELECT COUNT(*) FROM trades WHERE order_id=?", (order_id,)).fetchone()[0]
        conn.close()
        return n

    # --- payout_pending ----------------------------------------------------
    @patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="confirmed")
    def test_payout_pending_confirmed_completes_and_records_trade(self, _m):
        _seed_order(self.db, "o1", "payout_pending")
        s = reconcile_settlements()
        self.assertEqual(self._status("o1"), "completed")
        self.assertEqual(self._trade_count("o1"), 1)
        self.assertEqual(s["promoted"], 1)

    @patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="voided")
    def test_payout_pending_voided_routes_to_recovery_no_trade(self, _m):
        _seed_order(self.db, "o2", "payout_pending")
        s = reconcile_settlements()
        self.assertEqual(self._status("o2"), "settlement_recovery")
        self.assertEqual(self._trade_count("o2"), 0)
        self.assertEqual(s["recovered"], 1)

    @patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="pending")
    def test_payout_pending_still_pending_is_left_untouched(self, _m):
        _seed_order(self.db, "o3", "payout_pending")
        reconcile_settlements()
        self.assertEqual(self._status("o3"), "payout_pending")  # secret stays withheld
        self.assertEqual(self._trade_count("o3"), 0)

    # --- settling (crash recovery) -----------------------------------------
    @patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="missing")
    def test_settling_with_missing_payout_goes_to_recovery_not_matched(self, _m):
        # The v2/v3 safety fix: 'missing' is ambiguous, so a released 'settling'
        # must NOT become a retryable 'matched' (double-pay) — it goes to recovery.
        _seed_order(self.db, "o4", "settling")
        s = reconcile_settlements()
        self.assertEqual(self._status("o4"), "settlement_recovery")
        self.assertEqual(s["recovered"], 1)

    @patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="confirmed")
    def test_settling_confirmed_completes(self, _m):
        _seed_order(self.db, "o5", "settling")
        reconcile_settlements()
        self.assertEqual(self._status("o5"), "completed")
        self.assertEqual(self._trade_count("o5"), 1)

    @patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="missing")
    def test_freshly_settling_is_left_in_grace_window(self, _lk):
        # An order created long ago on the open book (created_at old) but matched
        # only seconds ago is 'settling' with its confirm handler still in-flight.
        # The grace window must keep it untouched: matched_at is the recency signal
        # for when settling began; created_at predates the match and must not gate
        # the window (else a healthy settlement is force-routed to recovery and a
        # critical alert fires, racing the live handler).
        now = int(time.time())
        conn = sqlite3.connect(self.db)
        conn.execute(
            """INSERT INTO orders
               (order_id, side, pair, maker_wallet, amount_micro_rtc,
                price_per_rtc_nano_quote, total_quote_nano, status, escrow_job_id,
                htlc_hash, htlc_secret, taker_wallet, settlement_tx,
                created_at, matched_at, expires_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("o_fresh", "sell", "RTC/USDC", "rtc_maker", 10_000_000, 1_000_000_000,
             10_000_000_000, "settling", "job-1", "h", "secret", "rtc_taker",
             "quote-tx", now - 10_000, now - 5, now + 3600),
        )
        conn.commit()
        conn.close()
        s = reconcile_settlements()
        self.assertEqual(self._status("o_fresh"), "settling")  # untouched, no recovery
        self.assertEqual(s["left"], 1)
        self.assertEqual(_lk.call_count, 0)  # not even probed inside the grace window

    # --- settlement_recovery rescue (no silent trade loss) -----------------
    @patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="confirmed")
    def test_settlement_recovery_confirmed_is_rescued_with_trade(self, _m):
        _seed_order(self.db, "o6", "settlement_recovery")
        reconcile_settlements()
        self.assertEqual(self._status("o6"), "completed")
        self.assertEqual(self._trade_count("o6"), 1)  # the lost trade is recorded

    # --- refund_pending ----------------------------------------------------
    @patch.object(otc_bridge, "safe_refund_escrow", return_value=True)
    @patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="missing")
    def test_refund_pending_cancel_origin_terminal_cancelled(self, _lk, _rf):
        # Not yet expired -> cancel origin -> terminal 'cancelled'.
        _seed_order(self.db, "o7", "refund_pending", expires_in=3600)
        s = reconcile_settlements()
        self.assertEqual(self._status("o7"), "cancelled")
        self.assertEqual(s["refunded"], 1)

    @patch.object(otc_bridge, "safe_refund_escrow", return_value=True)
    @patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="missing")
    def test_refund_pending_expired_origin_terminal_expired(self, _lk, _rf):
        # Past expires_at -> expiry origin -> terminal 'expired'.
        _seed_order(self.db, "o8", "refund_pending", expires_in=-100)
        reconcile_settlements()
        self.assertEqual(self._status("o8"), "expired")

    @patch.object(otc_bridge, "safe_refund_escrow", return_value=False)
    @patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="missing")
    def test_refund_pending_failed_refund_stays_pending(self, _lk, _rf):
        _seed_order(self.db, "o9", "refund_pending")
        reconcile_settlements()
        self.assertEqual(self._status("o9"), "refund_pending")  # retried next pass

    # --- v3.1 fixes: refund recipient + promotion guard --------------------
    @patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="missing")
    def test_refund_pending_refunds_to_maker_not_taker(self, _lk):
        # A buy-side order cancelled while OPEN has no taker; the refund must go to
        # the MAKER (escrow poster), never a NULL/derived taker.
        _seed_order(self.db, "o11", "refund_pending", side="buy")
        # null out taker to model an open-order cancel/expiry
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE orders SET taker_wallet=NULL WHERE order_id='o11'")
        conn.commit(); conn.close()
        seen = {}
        def _fake_refund(job_id, poster, *a, **k):
            seen["poster"] = poster
            return True
        with patch.object(otc_bridge, "safe_refund_escrow", _fake_refund):
            reconcile_settlements()
        self.assertEqual(seen["poster"], "rtc_maker")  # maker, not taker/NULL

    @patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="confirmed")
    def test_confirmed_payout_missing_settlement_fields_not_promoted(self, _lk):
        # A stale settlement_recovery row lacking taker/settlement_tx must NOT
        # auto-complete (would expose the secret with no verified quote leg).
        _seed_order(self.db, "o12", "settlement_recovery", settlement_tx=None)
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE orders SET taker_wallet=NULL WHERE order_id='o12'")
        conn.commit(); conn.close()
        s = reconcile_settlements()
        self.assertEqual(self._status("o12"), "settlement_recovery")  # left for ops
        self.assertEqual(self._trade_count("o12"), 0)
        self.assertEqual(s["left"], 1)

    # --- leader lock -------------------------------------------------------
    def test_leader_lock_makes_second_pass_skip(self):
        _seed_order(self.db, "o10", "payout_pending")
        held = sqlite3.connect(self.db)
        self.assertTrue(otc_bridge._acquire_reconcile_lock(held))  # hold the lock
        try:
            with patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="confirmed"):
                s = reconcile_settlements()  # cannot acquire -> skips
            self.assertEqual(s.get("skipped_locked"), 1)
            self.assertEqual(self._status("o10"), "payout_pending")  # untouched
        finally:
            otc_bridge._release_reconcile_lock(held)
            held.close()
        # After release, a fresh pass proceeds.
        with patch.object(otc_bridge, "_lookup_worker_payout_status", return_value="confirmed"):
            reconcile_settlements()
        self.assertEqual(self._status("o10"), "completed")


if __name__ == "__main__":
    unittest.main()
