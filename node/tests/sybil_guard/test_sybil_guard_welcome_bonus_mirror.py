# SPDX-License-Identifier: MIT
"""PR #8491 port: the welcome bonus must move the UTXO mirror, not only balances.

Same scenario as the upstream PR tests (founder_community fully mirrored, pay
bonuses, check mirror <= balance), run against BOTH the patched node and the
live snapshot so the test proves the fix is what closes the gap.
"""
import sqlite3
import time

import pytest

from sg_helpers import NODE_DIR, baseline_dir, load_node

SOURCE = "founder_community"
BONUS_URTC = 500_000
NRTC_PER_URTC = 100
SOURCE_START_URTC = 20_000_000


@pytest.fixture(scope="module")
def nodes(tmp_path_factory):
    d = tmp_path_factory.mktemp("mirror_load")
    out = {"patched": load_node(d / "p.db", "mirror_patched", NODE_DIR)}
    if baseline_dir() is not None:
        out["live"] = load_node(d / "l.db", "mirror_live", baseline_dir())
    return out


def _setup(node, db):
    from utxo_db import UtxoDB
    node.DB_PATH = str(db)
    node.UTXO_DUAL_WRITE = True
    UtxoDB(str(db)).init_tables()
    now = int(time.time())
    with sqlite3.connect(db) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, miner_pk TEXT,
                amount_i64 INTEGER DEFAULT 0, balance_rtc REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL,
                epoch INTEGER, miner_id TEXT NOT NULL, delta_i64 INTEGER NOT NULL, reason TEXT);
            CREATE TABLE IF NOT EXISTS account_mirror_boxes (box_id TEXT PRIMARY KEY,
                account_wallet TEXT NOT NULL, value_nrtc INTEGER NOT NULL, created_epoch INTEGER);
            """
        )
        c.execute("INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)", (SOURCE, SOURCE_START_URTC))
        c.execute("INSERT INTO utxo_transactions (tx_id, tx_type, inputs_json, outputs_json, timestamp, "
                  "block_height) VALUES ('genesistx', 'genesis', '[]', '[]', ?, 0)", (now,))
        c.execute("INSERT INTO utxo_boxes (box_id, value_nrtc, proposition, owner_address, creation_height, "
                  "transaction_id, output_index, created_at) VALUES ('genesisbox', ?, 'p', ?, 0, 'genesistx', 0, ?)",
                  (SOURCE_START_URTC * NRTC_PER_URTC, SOURCE, now))
        c.execute("INSERT INTO account_mirror_boxes VALUES ('genesisbox', ?, ?, 0)",
                  (SOURCE, SOURCE_START_URTC * NRTC_PER_URTC))
        c.commit()


def _persist(db, miner, state="trusted"):
    """Round 3: the bonus is authorised from the PERSISTED probation row."""
    import sybil_guard as sg
    with sqlite3.connect(db) as c:
        sg.init_schema(c)
        c.execute("INSERT OR REPLACE INTO miner_probation (miner, state, first_seen, last_seen, updated_at) "
                  "VALUES (?, ?, 1, 1, 1)", (miner, state))
        c.commit()


def _mirror(c, w):
    return int(c.execute("SELECT COALESCE(SUM(b.value_nrtc),0) FROM utxo_boxes b JOIN account_mirror_boxes m "
                         "ON m.box_id=b.box_id WHERE m.account_wallet=? AND b.spent_at IS NULL", (w,)).fetchone()[0])


def _balance(c, w):
    r = c.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (w,)).fetchone()
    return int(r[0]) * NRTC_PER_URTC if r and r[0] is not None else 0


def _pay(node, db, miner):
    with sqlite3.connect(db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        node._write_welcome_bonus(conn, miner, BONUS_URTC, node._table_columns(conn, "ledger"),
                                  node._table_columns(conn, "balances"))
        conn.commit()


def test_patched_bonuses_keep_mirror_in_sync(nodes, tmp_path):
    node, db = nodes["patched"], tmp_path / "p.db"
    _setup(node, db)
    for i in range(5):
        _pay(node, db, f"miner-{i}")
    with sqlite3.connect(db) as c:
        assert _mirror(c, SOURCE) - _balance(c, SOURCE) == 0
        for i in range(5):
            assert _mirror(c, f"miner-{i}") == _balance(c, f"miner-{i}") == BONUS_URTC * NRTC_PER_URTC
        assert _balance(c, SOURCE) == (SOURCE_START_URTC - 5 * BONUS_URTC) * NRTC_PER_URTC


def test_live_snapshot_drifts_by_one_bonus_per_miner(nodes, tmp_path):
    """Documents the production bug the port fixes (mirror > balance)."""
    if "live" not in nodes:
        pytest.skip("pre-patch baseline not available from git")
    node, db = nodes["live"], tmp_path / "l.db"
    _setup(node, db)
    for i in range(5):
        _pay(node, db, f"miner-{i}")
    with sqlite3.connect(db) as c:
        assert _mirror(c, SOURCE) - _balance(c, SOURCE) == 5 * BONUS_URTC * NRTC_PER_URTC


def test_graduation_bonus_path_keeps_mirror_in_sync(nodes, tmp_path):
    """The new _check_welcome_bonus (paid at probation exit) goes through the same writer."""
    node, db = nodes["patched"], tmp_path / "g.db"
    _setup(node, db)
    _persist(db, "graduate")
    assert node._check_welcome_bonus("graduate", {"state": "trusted"}) is True
    with sqlite3.connect(db) as c:
        assert _mirror(c, SOURCE) == _balance(c, SOURCE)
        assert _mirror(c, "graduate") == _balance(c, "graduate") == BONUS_URTC * NRTC_PER_URTC


def test_non_mirrored_payer_is_tolerated(nodes, tmp_path):
    node, db = nodes["patched"], tmp_path / "n.db"
    _setup(node, db)
    with sqlite3.connect(db) as c:
        c.execute("DELETE FROM account_mirror_boxes")
        c.execute("UPDATE utxo_boxes SET spent_at = 1 WHERE box_id='genesisbox'")
        c.commit()
    _pay(node, db, "m")
    with sqlite3.connect(db) as c:
        assert _balance(c, "m") == BONUS_URTC * NRTC_PER_URTC


def test_mirror_failure_rolls_back_whole_bonus_and_stays_retryable(nodes, tmp_path):
    """Round 2 (Codex/Astra/Grok): founder_community mirror > balance (the
    live node1 state) makes the reconciler raise mirror_exceeds_balance. The
    bonus must NOT be paid, nothing half-written may commit, and once the gap
    is repaired the next attempt pays exactly once."""
    node, db = nodes["patched"], tmp_path / "x.db"
    _setup(node, db)
    now = int(time.time())
    with sqlite3.connect(db) as c:   # inject a 1 RTC mirror excess on the payer
        c.execute("INSERT INTO utxo_boxes (box_id, value_nrtc, proposition, owner_address, creation_height, "
                  "transaction_id, output_index, created_at) VALUES ('excess', ?, 'p', ?, 0, 'genesistx', 1, ?)",
                  (100_000_000, SOURCE, now))
        c.execute("INSERT INTO account_mirror_boxes VALUES ('excess', ?, ?, 0)", (SOURCE, 100_000_000))
        c.commit()
        before = (_balance(c, SOURCE), c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0],
                  c.execute("SELECT COUNT(*) FROM utxo_boxes WHERE spent_at IS NULL").fetchone()[0])
    assert node._check_welcome_bonus("grad", {"state": "trusted"}) is False   # no persisted row: withheld
    _persist(db, "grad")
    assert node._check_welcome_bonus("grad", {"state": "trusted"}) is False
    with sqlite3.connect(db) as c:
        after = (_balance(c, SOURCE), c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0],
                 c.execute("SELECT COUNT(*) FROM utxo_boxes WHERE spent_at IS NULL").fetchone()[0])
        assert after == before                      # nothing committed
        assert _balance(c, "grad") == 0
        c.execute("DELETE FROM account_mirror_boxes WHERE box_id='excess'")   # operator repairs gap
        c.execute("DELETE FROM utxo_boxes WHERE box_id='excess'")
        c.commit()
    assert node._check_welcome_bonus("grad", {"state": "trusted"}) is True   # retried, paid
    assert node._check_welcome_bonus("grad", {"state": "trusted"}) is False  # exactly once
    with sqlite3.connect(db) as c:
        assert _mirror(c, SOURCE) == _balance(c, SOURCE)
        assert _balance(c, "grad") == BONUS_URTC * NRTC_PER_URTC
