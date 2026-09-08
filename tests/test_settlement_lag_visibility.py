#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""An advancing epoch number is not evidence that anyone is being paid.

RustChain never settled epochs 91-174 — 2026-03-03 to 2026-05-27, 84
consecutive days. `epoch_state` has no row for any of them: not `settled = 0`,
absent. `finalize_epoch` returned early on an empty miner set without writing
a row or logging, so the outage left no trace anywhere.

Nothing noticed, because nothing was looking at settlement:

  * the epoch number is derived from wall-clock, so it kept counting up;
  * blocks kept being produced, so `tip_age_slots` stayed 0;
  * `/health` therefore reported `ok: true` for the entire 84 days;
  * the node health monitor read only `epoch` and `miners`, both healthy.

183 miners enrolled across those epochs and were paid nothing. 83% of them
never attested again. 126 RTC was never emitted.

These tests pin the two halves of the fix: the node must expose the lag, and
the monitor must alert on it. The nastiest case has its own test — the stale
epoch numbering that makes an unbounded query report a *negative* lag, i.e.
perfect health, during exactly the stall being looked for.
"""

import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "node_health_monitor", os.path.join(ROOT, "tools", "node_health_monitor.py")
)
MON = importlib.util.module_from_spec(_spec)
sys.modules["node_health_monitor"] = MON
_spec.loader.exec_module(MON)


# ── monitor side ──────────────────────────────────────────────────────────────

class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _probe(payload: dict):
    mon = MON.NodeHealthMonitor(nodes=["http://example.invalid"])
    with mock.patch.object(MON.urllib.request, "urlopen",
                           return_value=_Resp(json.dumps(payload).encode())):
        return mon.check_node("http://example.invalid")


class MonitorSeesTheStallTest(unittest.TestCase):

    def test_healthy_lag_raises_nothing(self):
        st = _probe({"epoch": 254, "enrolled_miners": 16,
                     "settlement_lag_epochs": 1})
        self.assertEqual(st.status, "online")
        self.assertEqual(st.settlement_lag_epochs, 1)
        self.assertIsNone(st.error)

    def test_the_outage_shape_is_reported(self):
        """Epoch advancing, miners enrolling, nothing settled for 84 epochs."""
        st = _probe({"epoch": 174, "enrolled_miners": 21,
                     "settlement_lag_epochs": 84})
        self.assertEqual(st.settlement_lag_epochs, 84)
        self.assertIsNotNone(st.error, "an 84-epoch stall must not be silent")
        self.assertIn("settlement stalled", st.error)

    def test_a_stalled_node_is_still_online(self):
        """It is answering, and miners must keep enrolling so the stalled
        epochs stay reconstructible from epoch_enroll."""
        st = _probe({"epoch": 174, "miners": 21, "settlement_lag_epochs": 84})
        self.assertEqual(st.status, "online")

    def test_an_older_node_that_omits_the_field_is_not_accused(self):
        st = _probe({"epoch": 254, "miners": 16})
        self.assertIsNone(st.settlement_lag_epochs)
        self.assertIsNone(st.error)

    def test_a_malformed_lag_does_not_kill_the_probe(self):
        st = _probe({"epoch": 254, "miners": 16,
                     "settlement_lag_epochs": "ages"})
        self.assertEqual(st.status, "online")
        self.assertIsNone(st.settlement_lag_epochs)


class NetworkAlertTest(unittest.TestCase):

    def _status(self, lag):
        return MON.NodeStatus(url="http://n", status="online",
                              response_time_ms=10.0, epoch=254, miners=16,
                              error=None, settlement_lag_epochs=lag)

    def test_network_health_flags_the_stall(self):
        mon = MON.NodeHealthMonitor(nodes=["http://n"])
        health = mon.get_network_health([self._status(84)])
        self.assertTrue(health.settlement_stalled)
        self.assertTrue(any("SETTLEMENT STALLED" in a for a in health.alerts))

    def test_consensus_can_be_perfect_while_settlement_is_dead(self):
        """The exact 2026 blind spot: every node agreeing on an epoch number
        was read as health. Agreement says nothing about payment."""
        mon = MON.NodeHealthMonitor(nodes=["http://a", "http://b"])
        health = mon.get_network_health([self._status(84), self._status(84)])
        self.assertTrue(health.consensus_ok)
        self.assertFalse(health.split_brain)
        self.assertTrue(health.settlement_stalled,
                        "consensus_ok must not mask a settlement stall")

    def test_healthy_network_is_not_flagged(self):
        mon = MON.NodeHealthMonitor(nodes=["http://n"])
        health = mon.get_network_health([self._status(1)])
        self.assertFalse(health.settlement_stalled)


# ── node side: the bounding rule ──────────────────────────────────────────────

class LegacyEpochNumberingTest(unittest.TestCase):
    """`epoch_state` still holds rows from the pre-2025-12 numbering scheme.

    An unbounded `MAX(epoch) WHERE settled = 1` returns 424 (settled Dec 2025)
    or a 20000-series row, so the lag computes negative and the node reports
    flawless health during the stall. The query must be bounded by the current
    epoch. This is the trap the fix exists to avoid, so it is pinned directly
    against SQLite rather than mocked.
    """

    SQL_BOUNDED = ("SELECT MAX(epoch) FROM epoch_state "
                   "WHERE settled = 1 AND epoch <= ?")
    SQL_UNBOUNDED = "SELECT MAX(epoch) FROM epoch_state WHERE settled = 1"

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, "
                        "settled INTEGER DEFAULT 0, settled_ts INTEGER)")
        # production shape: legacy rows, then the modern series stalled at 90
        self.db.executemany(
            "INSERT INTO epoch_state (epoch, settled) VALUES (?, 1)",
            [(90,), (424,), (20424,)]
        )

    def tearDown(self):
        self.db.close()

    def test_unbounded_query_hides_the_outage(self):
        """Documents why the naive version is wrong — it must NOT be used."""
        last = self.db.execute(self.SQL_UNBOUNDED).fetchone()[0]
        self.assertEqual(last, 20424)
        self.assertLess(174 - last, 0,
                        "the naive query yields a negative lag = 'all is well'")

    def test_bounded_query_finds_the_real_stall(self):
        last = self.db.execute(self.SQL_BOUNDED, (174,)).fetchone()[0]
        self.assertEqual(last, 90)
        self.assertEqual(174 - last, 84, "the actual outage length")

    def test_no_settled_epoch_at_all_is_unknown_not_zero(self):
        empty = sqlite3.connect(":memory:")
        empty.execute("CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, "
                      "settled INTEGER DEFAULT 0)")
        last = empty.execute(self.SQL_BOUNDED, (254,)).fetchone()[0]
        self.assertIsNone(last, "absent state must read as unknown, not lag 0")
        empty.close()


class NodeHelperTest(unittest.TestCase):
    """Exercise the node's real `_settlement_lag_epochs`, not a copy of its SQL.

    The class above documents the bounding principle against raw SQLite; this
    one guards the actual shipped function, which is what regresses.
    """

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("RC_ADMIN_KEY", "t" * 64)
        node_dir = os.path.join(ROOT, "node")
        sys.path.insert(0, node_dir)
        spec = importlib.util.spec_from_file_location(
            "rc_node_settle",
            os.path.join(node_dir, "rustchain_v2_integrated_v2.2.1_rip200.py"))
        cls.NODE = importlib.util.module_from_spec(spec)
        sys.modules["rc_node_settle"] = cls.NODE
        spec.loader.exec_module(cls.NODE)

    def _db(self, settled_epochs):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, "
                   "settled INTEGER DEFAULT 0, settled_ts INTEGER)")
        db.executemany("INSERT INTO epoch_state (epoch, settled) VALUES (?, 1)",
                       [(e,) for e in settled_epochs])
        return db

    def test_legacy_rows_do_not_mask_the_stall(self):
        """90 settled, legacy 424 and 20424 present, current epoch 174."""
        db = self._db([90, 424, 20424])
        lag, last = self.NODE._settlement_lag_epochs(conn=db, now_epoch=174)
        db.close()
        self.assertEqual(last, 90, "must ignore the pre-2025-12 numbering")
        self.assertEqual(lag, 84, "the real outage length")

    def test_steady_state_is_lag_one(self):
        db = self._db([253])
        lag, last = self.NODE._settlement_lag_epochs(conn=db, now_epoch=254)
        db.close()
        self.assertEqual((lag, last), (1, 253))

    def test_unknown_when_nothing_is_settled(self):
        db = self._db([])
        lag, last = self.NODE._settlement_lag_epochs(conn=db, now_epoch=254)
        db.close()
        self.assertEqual((lag, last), (None, None))

    def test_unsettled_rows_do_not_count_as_settled(self):
        db = self._db([90])
        db.execute("INSERT INTO epoch_state (epoch, settled) VALUES (150, 0)")
        lag, last = self.NODE._settlement_lag_epochs(conn=db, now_epoch=174)
        db.close()
        self.assertEqual(last, 90,
                         "a recorded-but-unsettled epoch is not a settlement")

    def test_a_broken_table_reports_unknown_and_does_not_raise(self):
        db = sqlite3.connect(":memory:")
        lag, last = self.NODE._settlement_lag_epochs(conn=db, now_epoch=254)
        db.close()
        self.assertEqual((lag, last), (None, None))


class UnsettledEpochLeavesATraceTest(unittest.TestCase):
    """A no-payout epoch must be recorded, not silently skipped.

    Writing `settled = 0` is safe: the authoritative replay guard inserts the
    same row then atomically claims `0 -> 1`, so an existing unsettled row does
    not block a later real settlement.
    """

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, "
                        "settled INTEGER DEFAULT 0, settled_ts INTEGER)")

    def tearDown(self):
        self.db.close()

    def _record(self, epoch):
        self.db.execute("INSERT INTO epoch_state (epoch, settled) VALUES (?, 0) "
                        "ON CONFLICT(epoch) DO NOTHING", (epoch,))

    def test_the_epoch_becomes_visible_instead_of_absent(self):
        self._record(91)
        row = self.db.execute(
            "SELECT settled FROM epoch_state WHERE epoch = 91").fetchone()
        self.assertIsNotNone(row, "epochs 91-174 had no row at all")
        self.assertEqual(row[0], 0)

    def test_a_later_real_settlement_can_still_claim_it(self):
        self._record(91)
        claim = self.db.execute(
            "UPDATE epoch_state SET settled = 1, settled_ts = 1 "
            "WHERE epoch = ? AND settled = 0", (91,))
        self.assertEqual(claim.rowcount, 1,
                         "recording must not block recovery of the epoch")

    def test_it_cannot_overwrite_an_already_settled_epoch(self):
        self.db.execute("INSERT INTO epoch_state (epoch, settled, settled_ts) "
                        "VALUES (91, 1, 12345)")
        self._record(91)
        settled, ts = self.db.execute(
            "SELECT settled, settled_ts FROM epoch_state WHERE epoch = 91"
        ).fetchone()
        self.assertEqual((settled, ts), (1, 12345),
                         "must never demote a settled epoch")


if __name__ == "__main__":
    unittest.main(verbosity=2)
