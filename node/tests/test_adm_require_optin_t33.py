"""T3.3 regression: opt-in fail-closed anti-double-mining (RC_REQUIRE_ADM).

settle_epoch_rip200 historically falls back to the standard (non-grouping) reward path
whenever ADM is unavailable or raises — silently dropping the one-machine-one-reward
guard. RC_REQUIRE_ADM (default OFF) makes ADM mandatory for this admin/operator path:
on unavailable-or-failure it FAILS CLOSED (epoch left unsettled) instead of degrading.

Scope check: this gate lives ONLY in settle_epoch_rip200. finalize_epoch (the auto
block path) is intentionally NOT gated (it doesn't group by hardware; gating it would
break the live fleet).
"""
import importlib
import os
import sqlite3
import sys
import tempfile
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

import rewards_implementation_rip200 as rmod


def _minimal_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, settled INTEGER DEFAULT 0, settled_ts INTEGER)")
    c.execute("CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight INTEGER DEFAULT 100)")
    c.execute("CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, device_arch TEXT, ts_ok INTEGER, "
              "fingerprint_passed INTEGER DEFAULT 1, entropy_score REAL, fingerprint_checks_json TEXT)")
    c.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, epoch INTEGER, "
              "miner_id TEXT, delta_i64 INTEGER, reason TEXT)")
    c.execute("CREATE TABLE epoch_rewards (epoch INTEGER, miner_id TEXT, share_i64 INTEGER)")
    c.commit()
    c.close()
    return path

def _settled(path, epoch):
    with sqlite3.connect(path) as c:
        row = c.execute("SELECT settled FROM epoch_state WHERE epoch=?", (epoch,)).fetchone()
    return bool(row and row[0] == 1)


class AdmRequireOptInTest(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("RC_REQUIRE_ADM")
        self._prev_avail = rmod.ANTI_DOUBLE_MINING_AVAILABLE
        self._prev_fn = getattr(rmod, "settle_epoch_with_anti_double_mining", None)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("RC_REQUIRE_ADM", None)
        else:
            os.environ["RC_REQUIRE_ADM"] = self._prev
        rmod.ANTI_DOUBLE_MINING_AVAILABLE = self._prev_avail
        if self._prev_fn is not None:
            rmod.settle_epoch_with_anti_double_mining = self._prev_fn

    # --- fail-closed (RC_REQUIRE_ADM=1) -----------------------------------
    def test_required_but_unavailable_fails_closed(self):
        """ADM disabled-for-call (or module absent) + RC_REQUIRE_ADM=1 → no settlement."""
        db = _minimal_db()
        os.environ["RC_REQUIRE_ADM"] = "1"
        res = rmod.settle_epoch_rip200(db, epoch=1, enable_anti_double_mining=False)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "adm_required_unavailable")
        self.assertFalse(_settled(db, 1), "epoch must NOT be settled when ADM is required but unavailable")
        os.unlink(db)

    def test_required_but_adm_raises_fails_closed(self):
        """ADM available but raises + RC_REQUIRE_ADM=1 → adm_required_failed, NOT a
        silent fall-through to the non-grouping standard path."""
        db = _minimal_db()
        rmod.ANTI_DOUBLE_MINING_AVAILABLE = True

        def _boom(*a, **k):
            raise RuntimeError("ADM kaboom")

        rmod.settle_epoch_with_anti_double_mining = _boom
        os.environ["RC_REQUIRE_ADM"] = "1"
        res = rmod.settle_epoch_rip200(db, epoch=1, enable_anti_double_mining=True)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "adm_required_failed")
        self.assertFalse(_settled(db, 1), "epoch must NOT be settled (no standard fall-through under RC_REQUIRE_ADM)")
        os.unlink(db)

    # --- default OFF: backward compatible ---------------------------------
    def test_default_off_unavailable_falls_through_to_standard(self):
        """Default (flag unset): ADM unavailable → standard path runs (no adm_* error).
        With no enrolled miners it returns no_eligible_miners — proving the gate is
        opt-in and did NOT short-circuit."""
        db = _minimal_db()
        os.environ.pop("RC_REQUIRE_ADM", None)
        res = rmod.settle_epoch_rip200(db, epoch=1, enable_anti_double_mining=False)
        self.assertNotEqual(res.get("error"), "adm_required_unavailable")
        self.assertEqual(res.get("error"), "no_eligible_miners")
        os.unlink(db)

    def test_default_off_adm_raises_falls_through_to_standard(self):
        """Default: ADM raises → falls through to standard path (reaches no_eligible_miners),
        not adm_required_failed."""
        db = _minimal_db()
        rmod.ANTI_DOUBLE_MINING_AVAILABLE = True
        rmod.settle_epoch_with_anti_double_mining = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        os.environ.pop("RC_REQUIRE_ADM", None)
        res = rmod.settle_epoch_rip200(db, epoch=1, enable_anti_double_mining=True)
        self.assertNotEqual(res.get("error"), "adm_required_failed")
        self.assertEqual(res.get("error"), "no_eligible_miners")
        os.unlink(db)


if __name__ == "__main__":
    unittest.main()
