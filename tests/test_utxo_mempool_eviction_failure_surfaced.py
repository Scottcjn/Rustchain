# SPDX-License-Identifier: MIT
"""Stale-mempool eviction after a spend must not fail silently (#2819).

Reported by @expertedgevault-rgb: apply_transaction() swallowed every error
from _evict_stale_data_input_txs() (and the helper itself swallowed its own
errors and returned 0), so a committed spend could report success while
mempool txs depending on the spent boxes silently stayed in the pool.

Contract pinned here:
  * normal cleanup removes every dependent (input claim or data_input),
    on both the own-connection and caller-connection paths;
  * a cleanup failure never rolls back / corrupts the spend, but is logged
    at ERROR (with tx_id + spent box ids) and counted;
  * on a caller's connection a failed eviction is all-or-nothing (no
    orphaned claim rows riding along on the caller's COMMIT);
  * if SQLite aborts the caller's whole transaction during eviction,
    apply_transaction() raises instead of returning a false True.

Failures are injected with real SQLite triggers where possible, so the
real error paths run rather than mocks.
"""
import logging
import sqlite3

import pytest

from node import utxo_db as utxo_mod
from node.utxo_db import UtxoDB


@pytest.fixture
def db(tmp_path):
    instance = UtxoDB(str(tmp_path / "utxo.db"))
    instance.init_tables()
    return instance


def _mint(db, address, value, height):
    assert db.apply_transaction({
        "tx_type": "mining_reward",
        "inputs": [],
        "outputs": [{"address": address, "value_nrtc": value}],
        "fee_nrtc": 0,
        "data_inputs": [],
        "_allow_minting": True,
    }, block_height=height)
    conn = db._conn()
    try:
        return conn.execute(
            "SELECT box_id FROM utxo_boxes WHERE owner_address=? AND spent_at IS NULL",
            (address,),
        ).fetchone()["box_id"]
    finally:
        conn.close()


def _setup(db):
    """spend_box gets spent; dep_input spends it in mempool; dep_data reads it."""
    spend_box = _mint(db, "addr_spend", 10_000, 1)
    other_box = _mint(db, "addr_other", 20_000, 2)
    third_box = _mint(db, "addr_third", 30_000, 3)
    # Dependent via data_input only (its own claim is on other_box).
    assert db.mempool_add({
        "tx_id": "dep_data",
        "tx_type": "transfer",
        "inputs": [{"box_id": other_box, "spending_proof": "p"}],
        "data_inputs": [spend_box],
        "outputs": [{"address": "addr_x", "value_nrtc": 19_900}],
        "fee_nrtc": 100,
    })
    # Unrelated mempool tx that must survive.
    assert db.mempool_add({
        "tx_id": "unrelated",
        "tx_type": "transfer",
        "inputs": [{"box_id": third_box, "spending_proof": "p"}],
        "outputs": [{"address": "addr_y", "value_nrtc": 29_900}],
        "fee_nrtc": 100,
    })
    spend_tx = {
        "tx_type": "transfer",
        "inputs": [{"box_id": spend_box, "spending_proof": "p"}],
        "outputs": [{"address": "addr_to", "value_nrtc": 9_900}],
        "fee_nrtc": 100,
        "data_inputs": [],
        "timestamp": 1_700_000_000,
    }
    return spend_box, other_box, spend_tx


def _state(db, spend_box, other_box):
    conn = db._conn()
    try:
        return {
            "spent_at": conn.execute(
                "SELECT spent_at FROM utxo_boxes WHERE box_id=?", (spend_box,)
            ).fetchone()["spent_at"],
            "confirmed_txs": conn.execute(
                "SELECT COUNT(*) AS n FROM utxo_transactions WHERE tx_type='transfer'"
            ).fetchone()["n"],
            "mempool": {r["tx_id"] for r in conn.execute("SELECT tx_id FROM utxo_mempool")},
            "other_claim": conn.execute(
                "SELECT tx_id FROM utxo_mempool_inputs WHERE box_id=?", (other_box,)
            ).fetchone(),
        }
    finally:
        conn.close()


def _add_trigger(db, action):
    conn = db._conn()
    try:
        conn.execute(
            "CREATE TRIGGER fail_mempool_delete BEFORE DELETE ON utxo_mempool "
            f"BEGIN SELECT RAISE({action}, 'injected eviction failure'); END"
        )
        conn.commit()
    finally:
        conn.close()


SQLITE_SAVEPOINT = getattr(sqlite3, "SQLITE_SAVEPOINT", 32)
EVICT_SAVEPOINT = "utxo_evict_stale_mempool"


def _deny_savepoint_op(op):
    """Authorizer denying one savepoint operation ('RELEASE' / 'ROLLBACK')
    on the eviction savepoint only; everything else (incl. the caller's
    BEGIN/COMMIT) is allowed."""
    def auth(action, arg1, arg2, _db, _src):
        if (action == SQLITE_SAVEPOINT and arg1 == op
                and arg2 == EVICT_SAVEPOINT):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    return auth


def _apply_on_caller_conn(db, tx, authorizer=None):
    """Mimic utxo_endpoints: caller holds the write txn and commits."""
    conn = db._conn()
    try:
        if authorizer is not None:
            conn.set_authorizer(authorizer)
        conn.execute("BEGIN IMMEDIATE")
        ok = db.apply_transaction(tx, block_height=10, conn=conn)
        if ok and conn.in_transaction:
            conn.commit()
        return ok
    finally:
        conn.close()


# -- normal cleanup ----------------------------------------------------------

@pytest.mark.parametrize("caller_conn", [False, True])
def test_cleanup_removes_every_dependent_and_keeps_unrelated(db, caller_conn):
    spend_box, other_box, tx = _setup(db)
    before = utxo_mod.mempool_eviction_failure_count()

    ok = (_apply_on_caller_conn(db, tx) if caller_conn
          else db.apply_transaction(tx, block_height=10))

    assert ok is True
    st = _state(db, spend_box, other_box)
    assert st["spent_at"] is not None
    assert st["mempool"] == {"unrelated"}
    assert st["other_claim"] is None, "evicted tx's claim rows must go too"
    assert utxo_mod.mempool_eviction_failure_count() == before


def test_cleanup_evicts_row_whose_claim_rows_are_missing(db):
    """Defense in depth: a mempool row spending the box is evicted even if
    its utxo_mempool_inputs claim is missing (found via tx_data_json)."""
    spend_box, other_box, tx = _setup(db)
    conn = db._conn()
    try:
        conn.execute(
            "INSERT INTO utxo_mempool (tx_id, tx_data_json, fee_nrtc, expires_at, submitted_at) "
            "VALUES ('orphan', ?, 1, 9999999999, 0)",
            ('{"inputs": [{"box_id": "%s"}], "data_inputs": []}' % spend_box,),
        )
        conn.commit()
    finally:
        conn.close()

    assert db.apply_transaction(tx, block_height=10) is True
    assert _state(db, spend_box, other_box)["mempool"] == {"unrelated"}


# -- injected failures: spend stands, failure is surfaced --------------------

@pytest.mark.parametrize("caller_conn", [False, True])
def test_helper_exception_is_logged_counted_and_spend_stands(db, caplog, monkeypatch, caller_conn):
    spend_box, other_box, tx = _setup(db)

    def boom(*_a, **_k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(UtxoDB, "_evict_stale_data_input_txs", boom)
    before = utxo_mod.mempool_eviction_failure_count()

    with caplog.at_level(logging.ERROR, logger="node.utxo_db"):
        ok = (_apply_on_caller_conn(db, tx) if caller_conn
              else db.apply_transaction(tx, block_height=10))

    assert ok is True, "a durable spend must not be reported as failed"
    st = _state(db, spend_box, other_box)
    assert st["spent_at"] is not None, "spend must not be rolled back"
    assert st["confirmed_txs"] == 1
    # Surfaced, not swallowed:
    assert utxo_mod.mempool_eviction_failure_count() == before + 1
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    msg = errors[0].getMessage()
    assert tx["tx_id"] in msg and spend_box in msg and "database is locked" in msg
    # The stale dependent is (knowingly) still there -- that is what we log.
    assert "dep_data" in st["mempool"]


@pytest.mark.parametrize("caller_conn", [False, True])
def test_real_sqlite_failure_mid_eviction_is_atomic(db, caplog, caller_conn):
    """Trigger aborts the 2nd DELETE after the claim-row DELETE succeeded.
    The eviction must roll back as a unit (no orphaned mempool row without
    its claims) while the spend itself commits."""
    spend_box, other_box, tx = _setup(db)
    _add_trigger(db, "ABORT")
    before = utxo_mod.mempool_eviction_failure_count()

    with caplog.at_level(logging.ERROR, logger="node.utxo_db"):
        ok = (_apply_on_caller_conn(db, tx) if caller_conn
              else db.apply_transaction(tx, block_height=10))

    assert ok is True
    st = _state(db, spend_box, other_box)
    assert st["spent_at"] is not None and st["confirmed_txs"] == 1
    assert st["mempool"] == {"dep_data", "unrelated"}
    assert st["other_claim"] is not None and st["other_claim"]["tx_id"] == "dep_data", \
        "partial eviction leaked: claim rows deleted but mempool row kept"
    assert utxo_mod.mempool_eviction_failure_count() == before + 1
    assert any("injected eviction failure" in r.getMessage()
               for r in caplog.records if r.levelno == logging.ERROR)


def test_caller_txn_aborted_during_eviction_fails_closed(db):
    """RAISE(ROLLBACK) kills the caller's whole transaction, spend included.
    apply_transaction must raise, not return True for a spend that is gone."""
    spend_box, other_box, tx = _setup(db)
    _add_trigger(db, "ROLLBACK")
    before = utxo_mod.mempool_eviction_failure_count()

    with pytest.raises(sqlite3.Error):
        _apply_on_caller_conn(db, tx)

    st = _state(db, spend_box, other_box)
    assert st["spent_at"] is None, "nothing was committed"
    assert st["confirmed_txs"] == 0
    assert st["mempool"] == {"dep_data", "unrelated"}
    assert utxo_mod.mempool_eviction_failure_count() == before


def test_own_conn_rollback_trigger_does_not_touch_committed_spend(db, caplog):
    """Own-connection path: eviction runs after COMMIT on a fresh connection,
    so even a transaction-killing failure there cannot undo the spend."""
    spend_box, other_box, tx = _setup(db)
    _add_trigger(db, "ROLLBACK")
    before = utxo_mod.mempool_eviction_failure_count()

    with caplog.at_level(logging.ERROR, logger="node.utxo_db"):
        assert db.apply_transaction(tx, block_height=10) is True

    st = _state(db, spend_box, other_box)
    assert st["spent_at"] is not None and st["confirmed_txs"] == 1
    assert st["other_claim"] is not None
    assert utxo_mod.mempool_eviction_failure_count() == before + 1


def test_helper_raises_instead_of_returning_zero(db):
    """The helper no longer masks errors as 'nothing evicted'."""
    _setup(db)
    _add_trigger(db, "ABORT")
    conn = db._conn()
    try:
        box = conn.execute(
            "SELECT box_id FROM utxo_boxes WHERE owner_address='addr_spend'"
        ).fetchone()["box_id"]
    finally:
        conn.close()
    with pytest.raises(sqlite3.IntegrityError):
        db._evict_stale_data_input_txs([box])


# -- savepoint edge cases (review follow-up) ----------------------------------

def test_release_failure_after_successful_rollback_keeps_spend(db, caplog):
    """Eviction fails, ROLLBACK TO succeeds, RELEASE is denied. The caller's
    writes are intact, so the spend must be kept and the caller's COMMIT
    must still succeed (COMMIT closes the leftover savepoint)."""
    spend_box, other_box, tx = _setup(db)
    _add_trigger(db, "ABORT")
    before = utxo_mod.mempool_eviction_failure_count()

    with caplog.at_level(logging.ERROR, logger="node.utxo_db"):
        ok = _apply_on_caller_conn(db, tx, authorizer=_deny_savepoint_op("RELEASE"))

    assert ok is True
    st = _state(db, spend_box, other_box)  # fresh connection: proves COMMIT landed
    assert st["spent_at"] is not None and st["confirmed_txs"] == 1
    assert st["mempool"] == {"dep_data", "unrelated"}
    assert st["other_claim"] is not None and st["other_claim"]["tx_id"] == "dep_data"
    assert utxo_mod.mempool_eviction_failure_count() == before + 1
    msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("RELEASE SAVEPOINT" in m for m in msgs)
    assert any("injected eviction failure" in m for m in msgs)


def test_release_failure_after_successful_eviction_keeps_spend_and_eviction(db, caplog):
    """No eviction error, only the final RELEASE is denied: the eviction is
    complete and must commit with the spend; it is not counted as a failed
    eviction, but the RELEASE problem is logged."""
    spend_box, other_box, tx = _setup(db)
    before = utxo_mod.mempool_eviction_failure_count()

    with caplog.at_level(logging.ERROR, logger="node.utxo_db"):
        ok = _apply_on_caller_conn(db, tx, authorizer=_deny_savepoint_op("RELEASE"))

    assert ok is True
    st = _state(db, spend_box, other_box)
    assert st["spent_at"] is not None and st["confirmed_txs"] == 1
    assert st["mempool"] == {"unrelated"}
    assert st["other_claim"] is None
    assert utxo_mod.mempool_eviction_failure_count() == before
    assert any("RELEASE SAVEPOINT" in r.getMessage()
               for r in caplog.records if r.levelno == logging.ERROR)


def test_failed_savepoint_rollback_fails_closed(db):
    """Eviction fails and ROLLBACK TO is denied: the partial DELETE cannot
    be undone, so apply_transaction must raise _EvictionRollbackFailed rather
    than let the partial eviction ride along on the caller's COMMIT."""
    spend_box, other_box, tx = _setup(db)
    _add_trigger(db, "ABORT")
    before = utxo_mod.mempool_eviction_failure_count()

    with pytest.raises(utxo_mod._EvictionRollbackFailed):
        _apply_on_caller_conn(db, tx, authorizer=_deny_savepoint_op("ROLLBACK"))

    st = _state(db, spend_box, other_box)
    assert st["spent_at"] is None, "caller never committed"
    assert st["confirmed_txs"] == 0
    assert st["mempool"] == {"dep_data", "unrelated"}
    assert st["other_claim"] is not None
    assert utxo_mod.mempool_eviction_failure_count() == before


# -- strategy coverage (review follow-up) --------------------------------------

def test_claim_row_strategy_evicts_even_without_inputs_in_json(db):
    """Strategy 1 (utxo_mempool_inputs lookup) on its own: the row's
    tx_data_json names no inputs, only its claim row ties it to the box."""
    spend_box, other_box, _tx = _setup(db)
    conn = db._conn()
    try:
        conn.execute(
            "INSERT INTO utxo_mempool (tx_id, tx_data_json, fee_nrtc, expires_at, submitted_at) "
            "VALUES ('claim_only', '{\"tx_id\": \"claim_only\"}', 1, 9999999999, 0)"
        )
        conn.execute(
            "INSERT INTO utxo_mempool_inputs (box_id, tx_id) VALUES (?, 'claim_only')",
            (spend_box,),
        )
        conn.commit()
    finally:
        conn.close()

    # dep_data (data_input) + claim_only (claim row) are the two dependents.
    assert db._evict_stale_data_input_txs([spend_box]) == 2
    st = _state(db, spend_box, other_box)
    assert st["mempool"] == {"unrelated"}
    conn = db._conn()
    try:
        assert conn.execute(
            "SELECT 1 FROM utxo_mempool_inputs WHERE tx_id='claim_only'"
        ).fetchone() is None
    finally:
        conn.close()


@pytest.mark.parametrize("caller_conn", [False, True])
def test_apply_evicts_mempool_tx_spending_same_box_via_claim(db, caller_conn):
    """End-to-end Strategy 1: the confirmed tx's own mempool entry holds a
    claim on spend_box and must be evicted (with its claim rows)."""
    spend_box, other_box, tx = _setup(db)
    tx = dict(tx, tx_id="self_tx")
    tx.pop("timestamp")
    assert db.mempool_add(dict(tx))
    conn = db._conn()
    try:
        assert conn.execute(
            "SELECT tx_id FROM utxo_mempool_inputs WHERE box_id=?", (spend_box,)
        ).fetchone()["tx_id"] == "self_tx"
    finally:
        conn.close()

    ok = (_apply_on_caller_conn(db, tx) if caller_conn
          else db.apply_transaction(tx, block_height=10))

    assert ok is True
    st = _state(db, spend_box, other_box)
    assert st["mempool"] == {"unrelated"}
    conn = db._conn()
    try:
        assert conn.execute(
            "SELECT 1 FROM utxo_mempool_inputs WHERE box_id=?", (spend_box,)
        ).fetchone() is None
    finally:
        conn.close()


def test_malformed_rows_do_not_abort_the_scan(db):
    """Non-dict / non-JSON / odd-shaped rows are skipped, not fatal: real
    dependents are still evicted and the malformed rows are left alone."""
    spend_box, other_box, tx = _setup(db)
    garbage = {
        "g_list": "[1, 2, 3]",
        "g_str": '"just a string"',
        "g_null": "null",
        "g_badjson": "{not json",
        "g_shapes": '{"data_inputs": [["x"], {"a": 1}], "inputs": ["str", [1]]}',
    }
    conn = db._conn()
    try:
        for tx_id, body in garbage.items():
            conn.execute(
                "INSERT INTO utxo_mempool (tx_id, tx_data_json, fee_nrtc, expires_at, submitted_at) "
                "VALUES (?, ?, 1, 9999999999, 0)",
                (tx_id, body),
            )
        conn.commit()
    finally:
        conn.close()
    before = utxo_mod.mempool_eviction_failure_count()

    assert db.apply_transaction(tx, block_height=10) is True

    st = _state(db, spend_box, other_box)
    assert st["mempool"] == {"unrelated"} | set(garbage)
    assert st["other_claim"] is None
    assert utxo_mod.mempool_eviction_failure_count() == before
