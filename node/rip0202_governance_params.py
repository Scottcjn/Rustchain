#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RIP-202 PREREQ-A (first slice) — deterministic governance parameters substrate.

Today there is NO governance_params table, NO param execution, and NO get_param:
a "passed" proposal changes nothing programmatic, and there is nowhere to read a
fleet-wide consensus tunable from. RIP-202 step A needs to read the activation
height as chain-replicated state, not a binary constant (INV-4).

This module is the READ-ONLY / DORMANT first slice: the table + a typed
``get_param`` over a built-in DEFAULT registry. It does NOT yet wire vote-driven
execution (A1/A2) — values are only seedable via ``set_param`` (admin migration).
That keeps it purely additive (no consensus change) while giving step A a real
substrate to wire ``get_param("rip0202_activation_epoch")`` against.

Determinism contract:
  * The DEFAULT registry ships in the binary -> identical on every node, so an
    UNSET param resolves to one fleet-wide value (never node-local divergence).
  * Only registered names are addressable (unknown name -> error, fail closed) —
    no arbitrary/typo'd params can enter consensus reads.
  * Stored values are canonical strings, coerced to the declared type on read.
  * (Full determinism of *stored* values arrives with vote-driven execution
    from committed blocks — A1/A2. Until then operators must seed identically.)
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional

GOVERNANCE_PARAMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS governance_params (
    name         TEXT NOT NULL,
    set_at_epoch INTEGER NOT NULL,
    value        TEXT NOT NULL,
    proposal_id  INTEGER,
    PRIMARY KEY (name, set_at_epoch)
)
"""

# Registered consensus tunables. name -> {"type": <int|str>, "default": <value>}.
# `default` is the fleet-wide value when the param is unset (in the binary, so
# identical everywhere). `None` default == "unset / inactive".
_PARAM_SPEC: Dict[str, Dict[str, Any]] = {
    # RIP-202 step A: activation epoch for the fail-closed producer gate.
    # None => not activated (pre-activation behaviour, byte-identical to today).
    "rip0202_activation_epoch": {"type": int, "default": None, "min": 0},
    # RIP-202 B1/D5: eligibility threshold in B1 weight units (>=1). A stored
    # value < 1 would defeat INV-2 (admit 0-weight VMs) — enforced on set AND read.
    "rip0202_eligibility_threshold_units": {"type": int, "default": 1, "min": 1},
}


class GovernanceParamError(ValueError):
    """Raised for unknown param names or values that violate the declared type."""


def ensure_governance_params_schema(conn: sqlite3.Connection) -> None:
    """Create the governance_params table if absent. Call once at DB init (DDL
    implicit-commits — not inside a consensus transaction)."""
    if conn.in_transaction:
        raise RuntimeError(
            "ensure_governance_params_schema must not run inside a transaction "
            "(DDL implicit-commits and would break the caller's tx atomicity)"
        )
    conn.execute(GOVERNANCE_PARAMS_SCHEMA)


def _spec(name: str) -> Dict[str, Any]:
    if name not in _PARAM_SPEC:
        raise GovernanceParamError(f"unknown governance param: {name!r}")
    return _PARAM_SPEC[name]


def _coerce(name: str, raw: str) -> Any:
    typ = _spec(name)["type"]
    try:
        if typ is int:
            value = int(raw)
        elif typ is str:
            value = str(raw)
        else:
            raise GovernanceParamError(f"param {name!r} has unsupported type {typ!r}")
    except (TypeError, ValueError):
        raise GovernanceParamError(f"param {name!r} value {raw!r} is not a valid {typ.__name__}")
    return _enforce_bounds(name, value)


def _enforce_bounds(name: str, value: Any) -> Any:
    """Fail closed on a registered value that violates its declared `min`.

    Applied on BOTH set and read: a corrupt/out-of-bounds stored value raises
    (loud) rather than silently admitting e.g. a 0 eligibility threshold.
    """
    spec = _spec(name)
    lo = spec.get("min")
    if lo is not None and isinstance(value, int) and value < lo:
        raise GovernanceParamError(f"param {name!r} value {value} < min {lo}")
    return value


def _read_value(conn: sqlite3.Connection, name: str, suffix: str, params: tuple) -> Any:
    """Shared reader: latest matching row's value (coerced+bounded) or default.

    Unknown name -> GovernanceParamError (via _spec, fail closed). ONLY a
    genuinely-absent table (bootstrap) returns the default; a lock / disk / schema
    error re-raises (silently defaulting could disable activation on one node and
    fork consensus).
    """
    spec = _spec(name)
    try:
        row = conn.execute(
            "SELECT value FROM governance_params WHERE name = ? " + suffix,
            (name, *params),
        ).fetchone()
    except sqlite3.OperationalError as e:
        if "no such table" in str(e).lower():
            return spec["default"]
        raise
    if row is None:
        return spec["default"]
    return _coerce(name, row[0])


def get_param(conn: sqlite3.Connection, name: str) -> Any:
    """Latest value of a registered param (greatest set_at_epoch), or its default.

    For replay/reorg-correct reads keyed to a specific chain height, use
    ``get_param_as_of`` — this returns the most recently set value regardless of
    epoch (suitable for "current" reads in the dormant/admin path).
    """
    return _read_value(conn, name, "ORDER BY set_at_epoch DESC LIMIT 1", ())


def get_param_as_of(conn: sqlite3.Connection, name: str, epoch: int) -> Any:
    """Value of a registered param EFFECTIVE AT ``epoch`` — the row with the
    greatest ``set_at_epoch <= epoch``, else the binary default.

    This is the replay/reorg-safe read (tri-brain loop-4): a node validating
    history recovers the exact value in force at a prior epoch, and a future-dated
    change does not apply until its epoch. Deterministic function of chain height.
    """
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise GovernanceParamError("epoch must be a non-negative int")
    return _read_value(
        conn, name, "AND set_at_epoch <= ? ORDER BY set_at_epoch DESC LIMIT 1", (epoch,)
    )


def set_param(
    conn: sqlite3.Connection,
    name: str,
    value: Any,
    set_at_epoch: int,
    proposal_id: Optional[int] = None,
) -> None:
    """Append a registered param value EFFECTIVE AT ``set_at_epoch`` (history-keyed).

    History-keyed (PK name,set_at_epoch): a new set_at_epoch APPENDS a row (prior
    values are retained for replay); re-setting the same (name,set_at_epoch)
    replaces it (idempotent re-seed). Validates name + declared type + bounds
    (fail closed). ``set_at_epoch`` is the chain-derived epoch the value takes
    effect — provenance for determinism, never wall-clock.
    """
    typ = _spec(name)["type"]
    if value is None:
        raise GovernanceParamError(f"param {name!r} value must not be None")
    if typ is int and (isinstance(value, bool) or not isinstance(value, int)):
        raise GovernanceParamError(f"param {name!r} requires int, got {type(value).__name__}")
    if typ is str and not isinstance(value, str):
        raise GovernanceParamError(f"param {name!r} requires str, got {type(value).__name__}")
    _enforce_bounds(name, value)  # reject e.g. threshold 0/negative, activation epoch < 0
    if isinstance(set_at_epoch, bool) or not isinstance(set_at_epoch, int) or set_at_epoch < 0:
        raise GovernanceParamError("set_at_epoch must be a non-negative int")
    conn.execute(
        "INSERT OR REPLACE INTO governance_params (name, value, set_at_epoch, proposal_id) "
        "VALUES (?,?,?,?)",
        (name, str(value), set_at_epoch, proposal_id),
    )


def registered_params() -> Dict[str, Dict[str, Any]]:
    """Shallow copy of the param registry (for introspection / tests)."""
    return {k: dict(v) for k, v in _PARAM_SPEC.items()}
