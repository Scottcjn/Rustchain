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
    name         TEXT PRIMARY KEY,
    value        TEXT NOT NULL,
    set_at_epoch INTEGER NOT NULL,
    proposal_id  INTEGER
)
"""

# Registered consensus tunables. name -> {"type": <int|str>, "default": <value>}.
# `default` is the fleet-wide value when the param is unset (in the binary, so
# identical everywhere). `None` default == "unset / inactive".
_PARAM_SPEC: Dict[str, Dict[str, Any]] = {
    # RIP-202 step A: activation epoch for the fail-closed producer gate.
    # None => not activated (pre-activation behaviour, byte-identical to today).
    "rip0202_activation_epoch": {"type": int, "default": None},
    # RIP-202 B1/D5: eligibility threshold in B1 weight units (>=1).
    "rip0202_eligibility_threshold_units": {"type": int, "default": 1},
}


class GovernanceParamError(ValueError):
    """Raised for unknown param names or values that violate the declared type."""


def ensure_governance_params_schema(conn: sqlite3.Connection) -> None:
    """Create the governance_params table if absent. Call once at DB init (DDL
    implicit-commits — not inside a consensus transaction)."""
    conn.execute(GOVERNANCE_PARAMS_SCHEMA)


def _spec(name: str) -> Dict[str, Any]:
    if name not in _PARAM_SPEC:
        raise GovernanceParamError(f"unknown governance param: {name!r}")
    return _PARAM_SPEC[name]


def _coerce(name: str, raw: str) -> Any:
    typ = _spec(name)["type"]
    try:
        if typ is int:
            return int(raw)
        if typ is str:
            return str(raw)
    except (TypeError, ValueError):
        raise GovernanceParamError(f"param {name!r} value {raw!r} is not a valid {typ.__name__}")
    raise GovernanceParamError(f"param {name!r} has unsupported type {typ!r}")


def get_param(conn: sqlite3.Connection, name: str) -> Any:
    """Return the typed value of a registered param, or its built-in default.

    Unknown name -> GovernanceParamError (fail closed). Missing table/row ->
    the binary default (bootstrap-safe, fleet-uniform). Never raises into a
    consensus read for a *registered* name on a missing table.
    """
    spec = _spec(name)
    try:
        row = conn.execute(
            "SELECT value FROM governance_params WHERE name = ?", (name,)
        ).fetchone()
    except sqlite3.OperationalError:
        return spec["default"]  # table not created yet -> default
    if row is None:
        return spec["default"]
    return _coerce(name, row[0])


def set_param(
    conn: sqlite3.Connection,
    name: str,
    value: Any,
    set_at_epoch: int,
    proposal_id: Optional[int] = None,
) -> None:
    """Seed/update a registered param (admin migration; later: vote execution).

    Validates the name is registered and the value matches the declared type
    (fail closed). ``set_at_epoch`` is the chain-derived epoch the value takes
    effect — provenance for determinism, not wall-clock.
    """
    typ = _spec(name)["type"]
    if value is None:
        raise GovernanceParamError(f"param {name!r} value must not be None")
    if typ is int and (isinstance(value, bool) or not isinstance(value, int)):
        raise GovernanceParamError(f"param {name!r} requires int, got {type(value).__name__}")
    if typ is str and not isinstance(value, str):
        raise GovernanceParamError(f"param {name!r} requires str, got {type(value).__name__}")
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
