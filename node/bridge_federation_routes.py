"""Public read-only federation routes for bridge state + events.

Separate from the admin-keyed routes in `bridge_api.py` (which handle
mutation: initiate, void, update-external-confirmation). These routes are:

- **Public** (no admin key required) — the federation design note proposes
  reconciliation surfaces that anyone can audit without privileged access.
- **Read-only** — never write to `bridge_transfers` or `lock_ledger`.
- **Aggregate-friendly** — `bridge.state.get` returns the bridged-supply
  counter shape (per design note §3.2), not per-transfer detail.
- **Future-cross-side** — the data shape is designed so a future MergeWork
  bridge MCP can mirror it field-for-field for reconciliation comparison.

See:
  - https://github.com/Scottcjn/rustchain-claim-portal/blob/main/FEDERATION_DESIGN_NOTE.md
    §6.4 (Reconciliation as MCP read-only surface)
    §3.2 (The invariant: locked-on-one-side == mirrored-on-other-side)

Closes Layer 1 of the federation design work; Layers 2 (bridged-supply
snapshot mechanic), 3 (RFC iteration), 4 (MCP tool sketches) are tracked
separately.
"""

from __future__ import annotations

import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from flask import jsonify, request


# Status values surfaced as public state (per existing bridge_api schema).
PUBLIC_STATUS_VALUES = ("pending", "locked", "confirming", "completed", "voided", "failed")

# Bounded defaults for public endpoints.
DEFAULT_EVENTS_LIMIT = 50
MAX_EVENTS_LIMIT = 200

DEFAULT_TRANSFERS_LIMIT = 50
MAX_TRANSFERS_LIMIT = 200

# Default time window for events: 24 hours.
DEFAULT_EVENTS_WINDOW_SECONDS = 24 * 3600
MAX_EVENTS_WINDOW_SECONDS = 30 * 24 * 3600


def _get_db_path() -> str:
    """Resolve DB_PATH the same way bridge_api.py does."""
    return os.environ.get("DB_PATH", "rustchain_v2.db")


def _parse_int_arg(value: Optional[str], default: int, min_value: int, max_value: int) -> int:
    """Parse + clamp an integer query parameter."""
    if value in (None, ""):
        return default
    try:
        n = int(value)
    except (ValueError, TypeError):
        return default
    return max(min_value, min(n, max_value))


def _aggregate_bridge_state(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Compute the aggregate bridged-supply state.

    Returns a dict matching the shape described in FEDERATION_DESIGN_NOTE §3.2:

        {
            "locked_in_rtc": <total RTC sitting in locked/confirming on this side>,
            "completed_in_rtc": <total RTC ever moved to other side>,
            "voided_in_rtc": <total RTC ever voided>,
            "by_status": {<status>: {"count": N, "total_rtc": X}, ...},
            "by_direction": {"deposit": {...}, "withdraw": {...}},
            "last_event_at": <epoch seconds of most recent state change>,
            "computed_at": <epoch seconds when this aggregate was produced>,
        }

    No sensitive per-transfer details exposed.
    """
    cursor = conn.cursor()

    # by_status
    cursor.execute(
        "SELECT status, COUNT(*), COALESCE(SUM(amount_rtc), 0.0) "
        "FROM bridge_transfers GROUP BY status"
    )
    by_status: Dict[str, Dict[str, Any]] = {}
    for status, n, total in cursor.fetchall():  # fetchall-ok: bounded-by-schema
        by_status[status] = {"count": int(n), "total_rtc": float(total)}

    # by_direction (deposit / withdraw)
    cursor.execute(
        "SELECT direction, COUNT(*), COALESCE(SUM(amount_rtc), 0.0) "
        "FROM bridge_transfers GROUP BY direction"
    )
    by_direction: Dict[str, Dict[str, Any]] = {}
    for direction, n, total in cursor.fetchall():  # fetchall-ok: bounded-by-schema
        by_direction[direction] = {"count": int(n), "total_rtc": float(total)}

    # "Locked in" = pending + locked + confirming (RTC committed but not yet
    # mirrored on the other side AND not yet voided).
    locked_in = sum(
        by_status.get(s, {}).get("total_rtc", 0.0)
        for s in ("pending", "locked", "confirming")
    )
    completed_in = by_status.get("completed", {}).get("total_rtc", 0.0)
    voided_in = by_status.get("voided", {}).get("total_rtc", 0.0)

    # last_event_at: most recent created_at across all transfers
    last_event = cursor.execute(
        "SELECT COALESCE(MAX(created_at), 0) FROM bridge_transfers"
    ).fetchone()  # fetchall-ok: pragma-result (single MAX)
    last_event_at = int(last_event[0]) if last_event else 0

    return {
        "locked_in_rtc": float(locked_in),
        "completed_in_rtc": float(completed_in),
        "voided_in_rtc": float(voided_in),
        "by_status": by_status,
        "by_direction": by_direction,
        "last_event_at": last_event_at,
        "computed_at": int(time.time()),
    }


def _recent_events(conn: sqlite3.Connection, limit: int, window_seconds: int) -> List[Dict[str, Any]]:
    """List recent bridge state-change events, public-safe fields only.

    Returns a list of dicts of the form:

        {
            "tx_hash": <bridge tx_hash>,
            "direction": "deposit" | "withdraw",
            "source_chain": ...,
            "dest_chain": ...,
            "amount_rtc": ...,
            "status": ...,
            "external_confirmations": ...,
            "required_confirmations": ...,
            "created_at": ...,
        }

    Sensitive fields explicitly NOT exposed:
        - source_address / dest_address (privacy)
        - external_tx_hash (could leak external chain identifiers)
        - bridge_fee_i64 (operator-internal)
        - lock_epoch (operator-internal)
        - id (internal row id)
    """
    cutoff = int(time.time()) - max(0, window_seconds)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tx_hash, direction, source_chain, dest_chain,
               amount_rtc, status, external_confirmations,
               required_confirmations, created_at
        FROM bridge_transfers
        WHERE created_at >= ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (cutoff, limit),
    )
    rows = cursor.fetchall()  # fetchall-ok: already-paginated (LIMIT ?)
    return [
        {
            "tx_hash": r[0],
            "direction": r[1],
            "source_chain": r[2],
            "dest_chain": r[3],
            "amount_rtc": float(r[4]),
            "status": r[5],
            "external_confirmations": int(r[6]) if r[6] is not None else 0,
            "required_confirmations": int(r[7]) if r[7] is not None else 0,
            "created_at": int(r[8]),
        }
        for r in rows
    ]


def _recent_transfers_public(
    conn: sqlite3.Connection,
    status_filter: Optional[str],
    direction_filter: Optional[str],
    limit: int,
    offset: int,
) -> Dict[str, Any]:
    """List recent transfers (paginated), public-safe fields only.

    Same field set as _recent_events but with optional status/direction filter
    + pagination. Returns:

        {
            "transfers": [...],
            "total": <total count matching filters>,
            "limit": ...,
            "offset": ...,
        }
    """
    cursor = conn.cursor()

    where = ["1=1"]
    params: List[Any] = []
    if status_filter in PUBLIC_STATUS_VALUES:
        where.append("status = ?")
        params.append(status_filter)
    if direction_filter in ("deposit", "withdraw"):
        where.append("direction = ?")
        params.append(direction_filter)
    where_sql = " AND ".join(where)

    # Total count (bounded by schema cardinality).
    total = cursor.execute(
        f"SELECT COUNT(*) FROM bridge_transfers WHERE {where_sql}",
        tuple(params),
    ).fetchone()[0]  # fetchall-ok: pragma-result (single COUNT)

    cursor.execute(
        f"""
        SELECT tx_hash, direction, source_chain, dest_chain,
               amount_rtc, status, external_confirmations,
               required_confirmations, created_at
        FROM bridge_transfers
        WHERE {where_sql}
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params) + (limit, offset),
    )
    rows = cursor.fetchall()  # fetchall-ok: already-paginated (LIMIT ?)
    transfers = [
        {
            "tx_hash": r[0],
            "direction": r[1],
            "source_chain": r[2],
            "dest_chain": r[3],
            "amount_rtc": float(r[4]),
            "status": r[5],
            "external_confirmations": int(r[6]) if r[6] is not None else 0,
            "required_confirmations": int(r[7]) if r[7] is not None else 0,
            "created_at": int(r[8]),
        }
        for r in rows
    ]

    return {
        "transfers": transfers,
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


def register_federation_routes(app):
    """Register public read-only federation routes on a Flask app.

    Call AFTER `register_bridge_routes(app)` so the mutation routes are
    already in place — these read routes don't depend on the mutation
    routes, but the order keeps blueprint registration deterministic.
    """

    @app.route("/bridge/state", methods=["GET"])
    def bridge_state():
        """Aggregate bridged-supply state. Public, no auth required.

        Returns the shape described in FEDERATION_DESIGN_NOTE §3.2.
        """
        db_path = _get_db_path()
        try:
            with sqlite3.connect(db_path) as conn:
                state = _aggregate_bridge_state(conn)
        except sqlite3.Error as exc:
            return jsonify({"ok": False, "error": f"db_error: {exc.__class__.__name__}"}), 503
        return jsonify({"ok": True, "state": state})

    @app.route("/bridge/events", methods=["GET"])
    def bridge_events():
        """Recent bridge state-change events, public-safe fields only.

        Query params:
            limit:  1..MAX_EVENTS_LIMIT (default 50)
            window_seconds: 0..MAX_EVENTS_WINDOW_SECONDS (default 24h)
        """
        limit = _parse_int_arg(
            request.args.get("limit"),
            default=DEFAULT_EVENTS_LIMIT,
            min_value=1,
            max_value=MAX_EVENTS_LIMIT,
        )
        window = _parse_int_arg(
            request.args.get("window_seconds"),
            default=DEFAULT_EVENTS_WINDOW_SECONDS,
            min_value=0,
            max_value=MAX_EVENTS_WINDOW_SECONDS,
        )
        db_path = _get_db_path()
        try:
            with sqlite3.connect(db_path) as conn:
                events = _recent_events(conn, limit=limit, window_seconds=window)
        except sqlite3.Error as exc:
            return jsonify({"ok": False, "error": f"db_error: {exc.__class__.__name__}"}), 503
        return jsonify({
            "ok": True,
            "count": len(events),
            "limit": limit,
            "window_seconds": window,
            "events": events,
        })

    @app.route("/bridge/transfers/recent", methods=["GET"])
    def bridge_transfers_recent():
        """Paginated public list of bridge transfers.

        Query params:
            limit:  1..MAX_TRANSFERS_LIMIT (default 50)
            offset: >= 0
            status: pending|locked|confirming|completed|voided|failed (optional)
            direction: deposit|withdraw (optional)

        Sensitive fields (addresses, external_tx_hash, internal id) are
        intentionally omitted.
        """
        limit = _parse_int_arg(
            request.args.get("limit"),
            default=DEFAULT_TRANSFERS_LIMIT,
            min_value=1,
            max_value=MAX_TRANSFERS_LIMIT,
        )
        try:
            offset = max(0, int(request.args.get("offset", 0)))
        except (ValueError, TypeError):
            offset = 0
        status_filter = request.args.get("status")
        direction_filter = request.args.get("direction")

        db_path = _get_db_path()
        try:
            with sqlite3.connect(db_path) as conn:
                payload = _recent_transfers_public(
                    conn,
                    status_filter=status_filter,
                    direction_filter=direction_filter,
                    limit=limit,
                    offset=offset,
                )
        except sqlite3.Error as exc:
            return jsonify({"ok": False, "error": f"db_error: {exc.__class__.__name__}"}), 503
        return jsonify({"ok": True, **payload})


__all__ = [
    "register_federation_routes",
    "_aggregate_bridge_state",
    "_recent_events",
    "_recent_transfers_public",
    "PUBLIC_STATUS_VALUES",
    "DEFAULT_EVENTS_LIMIT",
    "MAX_EVENTS_LIMIT",
    "DEFAULT_EVENTS_WINDOW_SECONDS",
    "MAX_EVENTS_WINDOW_SECONDS",
    "DEFAULT_TRANSFERS_LIMIT",
    "MAX_TRANSFERS_LIMIT",
]
