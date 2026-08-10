"""Per-epoch reconciliation snapshots for bridge state.

Implements Layer 2 of the federation arc per:
  https://github.com/Scottcjn/rustchain-claim-portal/blob/main/FEDERATION_BRIDGED_SUPPLY_SPEC.md

Each snapshot is one row in `bridge_reconciliation_snapshots` recording:

  - The aggregate bridge state at the snapshot moment (locked_in /
    completed_in / voided_in / bridged_supply_committed)
  - A deterministic `state_hash` over the canonical-JSON serialization of
    the `by_status` + `by_direction` breakdowns + the totals
  - `relayer_signatures` placeholder column (NULL on operator-only side;
    Layer 3 fills with relayer-set signatures when federation goes live)
  - `epoch` (unique constraint) + `computed_at` (epoch seconds)

These rows are append-only by design: each snapshot is a permanent
attestation that anyone can verify against the chain's then-current
state.

Operator-side value (independent of federation):
  - Historical state proof per epoch — answers "what did the bridge
    look like at the end of epoch N?"
  - Drift detection groundwork — Layer 3 adds the cross-side checker
    that compares our snapshot to MergeWork's; this module is the
    snapshot-producer half of that protocol.

Public routes added in this module:
  - GET /bridge/reconciliation/latest
  - GET /bridge/reconciliation/by_epoch/<int:epoch>
  - GET /bridge/reconciliation/recent?limit=<n>

All routes are public read-only, same shape/policy as the Layer 1
federation routes in `bridge_federation_routes.py`.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from flask import jsonify, request

# Re-use the aggregate computation from Layer 1 — the snapshot IS the
# Layer 1 aggregate with a stable hash + epoch annotation.
try:  # pragma: no cover - import guards for split test contexts
    from bridge_federation_routes import _aggregate_bridge_state
except ImportError:
    _aggregate_bridge_state = None  # type: ignore[assignment]


SNAPSHOTS_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS bridge_reconciliation_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    epoch INTEGER NOT NULL UNIQUE,
    computed_at INTEGER NOT NULL,
    locked_in_rtc REAL NOT NULL,
    completed_in_rtc REAL NOT NULL,
    voided_in_rtc REAL NOT NULL,
    bridged_supply_committed REAL NOT NULL,
    state_hash TEXT NOT NULL,
    relayer_signatures TEXT
);
"""

SNAPSHOTS_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_bridge_reconciliation_epoch
ON bridge_reconciliation_snapshots(epoch DESC);
"""


DEFAULT_RECENT_LIMIT = 20
MAX_RECENT_LIMIT = 200


def _get_db_path() -> str:
    """Resolve the DB path exactly as the node does.

    The node reads `RUSTCHAIN_DB_PATH` first (rustchain_v2_integrated: DB_PATH
    = RUSTCHAIN_DB_PATH or DB_PATH or "./rustchain_v2.db"), and that is the
    variable the operator docs tell you to set (NODE_OPERATOR_GUIDE.md,
    DEVNET.md). Honouring only DB_PATH here made these read routes open a
    different file than the one `record_reconciliation_snapshot` writes to.
    """
    return (
        os.environ.get("RUSTCHAIN_DB_PATH")
        or os.environ.get("DB_PATH")
        or "rustchain_v2.db"
    )


def init_reconciliation_schema(cursor: sqlite3.Cursor) -> None:
    """Create the snapshot table + index if not present."""
    cursor.execute(SNAPSHOTS_SCHEMA_DDL)
    cursor.execute(SNAPSHOTS_INDEX_DDL)


def _canonical_state_payload(state: Dict[str, Any]) -> str:
    """Produce a deterministic JSON serialization of the aggregate state.

    Excludes `computed_at` (changes every call by design) so the same
    underlying bridge state always hashes to the same `state_hash`.
    """
    stable = {k: v for k, v in state.items() if k != "computed_at"}
    return json.dumps(stable, sort_keys=True, separators=(",", ":"))


def compute_state_hash(state: Dict[str, Any]) -> str:
    """SHA-256 over the canonical-JSON serialization of the aggregate."""
    payload = _canonical_state_payload(state)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _bridged_supply_committed(state: Dict[str, Any]) -> float:
    """Per FEDERATION_BRIDGED_SUPPLY_SPEC.md section 3:
        bridged_supply_committed = locked_in + completed_in - voided_in
    """
    return (
        float(state.get("locked_in_rtc", 0.0))
        + float(state.get("completed_in_rtc", 0.0))
        - float(state.get("voided_in_rtc", 0.0))
    )


def record_reconciliation_snapshot(
    conn: sqlite3.Connection,
    epoch: int,
    *,
    aggregate_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute and insert a snapshot row for `epoch`.

    Idempotent on the `epoch` UNIQUE constraint: if a snapshot already
    exists for this epoch, it is returned unchanged (no second row,
    no clobber). This makes the function safe to call repeatedly from
    epoch-settler hooks.

    Args:
        conn: open sqlite connection (must include bridge_transfers
              + bridge_reconciliation_snapshots tables).
        epoch: epoch number to snapshot.
        aggregate_state: optional pre-computed state from
              `_aggregate_bridge_state`. If None, computed here.

    Returns:
        dict with the snapshot row fields, plus a `created` boolean
        indicating whether this call inserted a new row.
    """
    if aggregate_state is None:
        if _aggregate_bridge_state is None:  # pragma: no cover
            raise RuntimeError(
                "bridge_federation_routes._aggregate_bridge_state unavailable"
            )
        aggregate_state = _aggregate_bridge_state(conn)

    locked_in = float(aggregate_state.get("locked_in_rtc", 0.0))
    completed_in = float(aggregate_state.get("completed_in_rtc", 0.0))
    voided_in = float(aggregate_state.get("voided_in_rtc", 0.0))
    bridged_committed = _bridged_supply_committed(aggregate_state)
    state_hash = compute_state_hash(aggregate_state)
    now = int(time.time())

    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, computed_at, locked_in_rtc, completed_in_rtc, "
        "voided_in_rtc, bridged_supply_committed, state_hash, relayer_signatures "
        "FROM bridge_reconciliation_snapshots WHERE epoch = ?",
        (int(epoch),),
    )
    existing = cursor.fetchone()  # fetchall-ok: pragma-result (unique key)
    if existing is not None:
        return {
            "id": int(existing[0]),
            "epoch": int(epoch),
            "computed_at": int(existing[1]),
            "locked_in_rtc": float(existing[2]),
            "completed_in_rtc": float(existing[3]),
            "voided_in_rtc": float(existing[4]),
            "bridged_supply_committed": float(existing[5]),
            "state_hash": existing[6],
            "relayer_signatures": existing[7],
            "created": False,
        }

    cursor.execute(
        """
        INSERT INTO bridge_reconciliation_snapshots (
            epoch, computed_at,
            locked_in_rtc, completed_in_rtc, voided_in_rtc,
            bridged_supply_committed, state_hash, relayer_signatures
        ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            int(epoch),
            now,
            locked_in,
            completed_in,
            voided_in,
            bridged_committed,
            state_hash,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    return {
        "id": int(new_id) if new_id is not None else 0,
        "epoch": int(epoch),
        "computed_at": now,
        "locked_in_rtc": locked_in,
        "completed_in_rtc": completed_in,
        "voided_in_rtc": voided_in,
        "bridged_supply_committed": bridged_committed,
        "state_hash": state_hash,
        "relayer_signatures": None,
        "created": True,
    }


def get_latest_snapshot(conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, epoch, computed_at,
               locked_in_rtc, completed_in_rtc, voided_in_rtc,
               bridged_supply_committed, state_hash, relayer_signatures
        FROM bridge_reconciliation_snapshots
        ORDER BY epoch DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()  # fetchall-ok: already-paginated (LIMIT 1)
    if row is None:
        return None
    return _row_to_dict(row)


def get_snapshot_by_epoch(
    conn: sqlite3.Connection, epoch: int
) -> Optional[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, epoch, computed_at,
               locked_in_rtc, completed_in_rtc, voided_in_rtc,
               bridged_supply_committed, state_hash, relayer_signatures
        FROM bridge_reconciliation_snapshots
        WHERE epoch = ?
        """,
        (int(epoch),),
    )
    row = cursor.fetchone()  # fetchall-ok: pragma-result (unique key)
    if row is None:
        return None
    return _row_to_dict(row)


def list_recent_snapshots(
    conn: sqlite3.Connection, limit: int
) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, epoch, computed_at,
               locked_in_rtc, completed_in_rtc, voided_in_rtc,
               bridged_supply_committed, state_hash, relayer_signatures
        FROM bridge_reconciliation_snapshots
        ORDER BY epoch DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    rows = cursor.fetchall()  # fetchall-ok: already-paginated (LIMIT ?)
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": int(row[0]),
        "epoch": int(row[1]),
        "computed_at": int(row[2]),
        "locked_in_rtc": float(row[3]),
        "completed_in_rtc": float(row[4]),
        "voided_in_rtc": float(row[5]),
        "bridged_supply_committed": float(row[6]),
        "state_hash": row[7],
        "relayer_signatures": row[8],
    }


def register_reconciliation_routes(app):
    """Register public read-only reconciliation routes on a Flask app."""

    @app.route("/bridge/reconciliation/latest", methods=["GET"])
    def reconciliation_latest():
        try:
            with sqlite3.connect(_get_db_path()) as conn:
                snap = get_latest_snapshot(conn)
        except sqlite3.Error as exc:
            return jsonify(
                {"ok": False, "error": f"db_error: {exc.__class__.__name__}"}
            ), 503
        if snap is None:
            return jsonify({"ok": True, "snapshot": None})
        return jsonify({"ok": True, "snapshot": snap})

    @app.route("/bridge/reconciliation/by_epoch/<int:epoch>", methods=["GET"])
    def reconciliation_by_epoch(epoch: int):
        if epoch < 0:
            return jsonify({"ok": False, "error": "epoch must be >= 0"}), 400
        try:
            with sqlite3.connect(_get_db_path()) as conn:
                snap = get_snapshot_by_epoch(conn, epoch)
        except sqlite3.Error as exc:
            return jsonify(
                {"ok": False, "error": f"db_error: {exc.__class__.__name__}"}
            ), 503
        if snap is None:
            return jsonify({"ok": True, "snapshot": None})
        return jsonify({"ok": True, "snapshot": snap})

    @app.route("/bridge/reconciliation/recent", methods=["GET"])
    def reconciliation_recent():
        raw = request.args.get("limit")
        try:
            limit = int(raw) if raw not in (None, "") else DEFAULT_RECENT_LIMIT
        except (ValueError, TypeError):
            limit = DEFAULT_RECENT_LIMIT
        limit = max(1, min(limit, MAX_RECENT_LIMIT))

        try:
            with sqlite3.connect(_get_db_path()) as conn:
                snaps = list_recent_snapshots(conn, limit=limit)
        except sqlite3.Error as exc:
            return jsonify(
                {"ok": False, "error": f"db_error: {exc.__class__.__name__}"}
            ), 503
        return jsonify({
            "ok": True,
            "count": len(snaps),
            "limit": limit,
            "snapshots": snaps,
        })


__all__ = [
    "init_reconciliation_schema",
    "record_reconciliation_snapshot",
    "compute_state_hash",
    "get_latest_snapshot",
    "get_snapshot_by_epoch",
    "list_recent_snapshots",
    "register_reconciliation_routes",
    "DEFAULT_RECENT_LIMIT",
    "MAX_RECENT_LIMIT",
    "SNAPSHOTS_SCHEMA_DDL",
]
