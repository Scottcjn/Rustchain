#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""RIP-202 PREREQ-A governance_params + get_param — unit tests."""
import os
import sqlite3
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
for _d in (os.path.dirname(_HERE), _HERE):
    if os.path.exists(os.path.join(_d, "rip0202_governance_params.py")):
        sys.path.insert(0, _d)
        break
import rip0202_governance_params as gp  # noqa: E402


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    gp.ensure_governance_params_schema(c)
    yield c
    c.close()


def test_schema_idempotent(conn):
    gp.ensure_governance_params_schema(conn)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(governance_params)")]
    assert cols == ["name", "set_at_epoch", "value", "proposal_id"]


def test_unset_returns_builtin_default(conn):
    assert gp.get_param(conn, "rip0202_activation_epoch") is None        # not activated
    assert gp.get_param(conn, "rip0202_eligibility_threshold_units") == 1


def test_get_param_default_when_table_missing():
    """A registered param resolves to its default even before the table exists
    (bootstrap-safe, fleet-uniform)."""
    bare = sqlite3.connect(":memory:")
    try:
        assert gp.get_param(bare, "rip0202_activation_epoch") is None
        assert gp.get_param(bare, "rip0202_eligibility_threshold_units") == 1
    finally:
        bare.close()


def test_set_then_get_typed(conn):
    gp.set_param(conn, "rip0202_activation_epoch", 5000, set_at_epoch=180, proposal_id=42)
    v = gp.get_param(conn, "rip0202_activation_epoch")
    assert v == 5000 and isinstance(v, int)


def test_stored_value_coerced_to_declared_type(conn):
    # even if a raw string slipped into storage, read coerces to int
    conn.execute("INSERT OR REPLACE INTO governance_params (name, set_at_epoch, value, proposal_id) "
                 "VALUES (?,?,?,?)", ("rip0202_eligibility_threshold_units", 10, "7", None))
    assert gp.get_param(conn, "rip0202_eligibility_threshold_units") == 7


def test_unknown_name_fails_closed(conn):
    with pytest.raises(gp.GovernanceParamError):
        gp.get_param(conn, "totally_made_up_param")
    with pytest.raises(gp.GovernanceParamError):
        gp.set_param(conn, "totally_made_up_param", 1, set_at_epoch=0)


def test_set_param_type_enforced(conn):
    with pytest.raises(gp.GovernanceParamError):
        gp.set_param(conn, "rip0202_activation_epoch", "soon", set_at_epoch=0)  # not int
    with pytest.raises(gp.GovernanceParamError):
        gp.set_param(conn, "rip0202_activation_epoch", True, set_at_epoch=0)    # bool != int
    with pytest.raises(gp.GovernanceParamError):
        gp.set_param(conn, "rip0202_activation_epoch", None, set_at_epoch=0)    # None invalid


def test_set_param_bad_epoch(conn):
    for bad in (-1, True, "0", 1.0):
        with pytest.raises(gp.GovernanceParamError):
            gp.set_param(conn, "rip0202_activation_epoch", 1, set_at_epoch=bad)


def test_history_keyed_get_param_latest(conn):
    """Distinct set_at_epoch APPENDS history; get_param returns the latest."""
    gp.set_param(conn, "rip0202_activation_epoch", 100, set_at_epoch=1)
    gp.set_param(conn, "rip0202_activation_epoch", 200, set_at_epoch=2)
    assert gp.get_param(conn, "rip0202_activation_epoch") == 200
    assert conn.execute("SELECT COUNT(*) FROM governance_params").fetchone()[0] == 2  # history retained


def test_same_epoch_reseed_replaces(conn):
    gp.set_param(conn, "rip0202_activation_epoch", 100, set_at_epoch=5)
    gp.set_param(conn, "rip0202_activation_epoch", 150, set_at_epoch=5)  # same epoch -> replace
    assert gp.get_param(conn, "rip0202_activation_epoch") == 150
    assert conn.execute("SELECT COUNT(*) FROM governance_params").fetchone()[0] == 1


def test_get_param_as_of_recovers_prior_epoch_value(conn):
    """Replay/reorg-safe: value EFFECTIVE AT a prior epoch is recoverable."""
    gp.set_param(conn, "rip0202_activation_epoch", 100, set_at_epoch=10)
    gp.set_param(conn, "rip0202_activation_epoch", 200, set_at_epoch=20)
    assert gp.get_param_as_of(conn, "rip0202_activation_epoch", 5) is None    # before first set -> default
    assert gp.get_param_as_of(conn, "rip0202_activation_epoch", 10) == 100    # at first set
    assert gp.get_param_as_of(conn, "rip0202_activation_epoch", 15) == 100    # between
    assert gp.get_param_as_of(conn, "rip0202_activation_epoch", 25) == 200    # after second
    for bad in (-1, True, "5", 1.0):
        with pytest.raises(gp.GovernanceParamError):
            gp.get_param_as_of(conn, "rip0202_activation_epoch", bad)


def test_registered_params_introspection():
    reg = gp.registered_params()
    assert "rip0202_activation_epoch" in reg
    reg["rip0202_activation_epoch"]["default"] = "mutated"  # copy, not the live spec
    assert gp.get_param.__module__  # sanity
    assert gp.registered_params()["rip0202_activation_epoch"]["default"] is None


# ---- tri-brain fixes: value bounds + narrowed OperationalError ----
def test_set_param_enforces_min(conn):
    with pytest.raises(gp.GovernanceParamError):
        gp.set_param(conn, "rip0202_eligibility_threshold_units", 0, set_at_epoch=1)   # < min 1
    with pytest.raises(gp.GovernanceParamError):
        gp.set_param(conn, "rip0202_eligibility_threshold_units", -3, set_at_epoch=1)
    with pytest.raises(gp.GovernanceParamError):
        gp.set_param(conn, "rip0202_activation_epoch", -1, set_at_epoch=1)             # < min 0


def test_get_param_rejects_out_of_bounds_stored_value(conn):
    conn.execute("INSERT OR REPLACE INTO governance_params (name, set_at_epoch, value, proposal_id) "
                 "VALUES (?,?,?,?)", ("rip0202_eligibility_threshold_units", 1, "0", None))  # corrupt: below min
    with pytest.raises(gp.GovernanceParamError):
        gp.get_param(conn, "rip0202_eligibility_threshold_units")


def test_get_param_reraises_non_missing_table_error():
    class _LockedConn:
        def execute(self, *a, **k):
            raise sqlite3.OperationalError("database is locked")
    with pytest.raises(sqlite3.OperationalError):
        gp.get_param(_LockedConn(), "rip0202_activation_epoch")


def test_ensure_schema_rejects_in_transaction():
    c = sqlite3.connect(":memory:")
    try:
        c.execute("CREATE TABLE t(x)")
        c.execute("INSERT INTO t VALUES (1)")  # opens a transaction
        assert c.in_transaction
        with pytest.raises(RuntimeError):
            gp.ensure_governance_params_schema(c)
    finally:
        c.close()
