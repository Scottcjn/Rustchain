# SPDX-License-Identifier: MIT
"""
Hall of Rust module — leaderboard, machine lookup, and badge computation.

This blueprint registers endpoints under /api/hall_of_fame/ (the canonical
API namespace) and also exposes /api/hall_of_fame itself as a compatibility
alias for the leaderboard.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import logging
import sqlite3
import time

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    request,
)

logger = logging.getLogger(__name__)

hall_bp = Blueprint("hall_of_rust", __name__, url_prefix="")


# ── helpers ────────────────────────────────────────────────────────────────


def init_hall_tables(db_path: str) -> None:
    """Create (if missing) the hall_of_rust table."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS hall_of_rust (
            fingerprint_hash       TEXT PRIMARY KEY,
            miner_id               TEXT,
            device_family          TEXT,
            device_arch            TEXT,
            device_model           TEXT,
            manufacture_year       TEXT,
            rust_score             REAL,
            total_attestations     INTEGER DEFAULT 0,
            capacitor_plague       INTEGER DEFAULT 0,
            is_deceased            INTEGER DEFAULT 0,
            nickname               TEXT,
            first_attestation      TEXT,
            last_attestation       TEXT,
            thermal_events         INTEGER DEFAULT 0,
            verification_count     INTEGER DEFAULT 0,
            trust_score            INTEGER DEFAULT 0,
            machine_health_score   REAL DEFAULT 0.0,
            verified_logic         TEXT DEFAULT ''
        )
        """
    )
    conn.commit()
    conn.close()


def _get_int_arg(name: str, default: int) -> int:
    try:
        return int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default


def _require_admin() -> Optional[Response]:
    """Reject request unless caller provides the admin key."""
    key = request.headers.get("X-Admin-Key") or request.args.get("key")
    expected = current_app.config.get("ADMIN_KEY", "")
    if not expected:
        return None  # no key configured = open access
    if key != expected:
        return jsonify({"error": "unauthorized"}), 403
    return None


_RUST_BADGES: List[Tuple[float, str]] = [
    (10_000_000, "🟣 Ancient Iron"),
    (5_000_000, "🔴 Exotic Arch"),
    (1_000_000, "🟠 Most Dedicated"),
    (500_000, "🟡 Fleet Commander"),
    (100_000, "🟢 Core Miner"),
    (10_000, "🔵 Junior Miner"),
    (1_000, "⚪ Apprentice"),
]


def get_rust_badge(score: float) -> str:
    for threshold, badge in _RUST_BADGES:
        if score >= threshold:
            return badge
    return "🧊 Rustling"


# ── argument parsing helpers ────────────────────────────────────────────────

_T = Union[str, int, float, None]


def _parse_limit_arg() -> Tuple[int, Optional[Response]]:
    """Return (limit, None) or (None, error_response)."""
    limit_raw = request.args.get("limit", "100")
    # Empty string — use default
    if limit_raw == "":
        return 100, None
    try:
        limit_val = int(limit_raw)
    except (ValueError, TypeError):
        return 0, (("limit must be an integer", 400))  # type:ignore[return-value]
    if limit_val < 0:
        return 0, (("limit must be non-negative", 400))  # type:ignore[return-value]
    if limit_val == 0:
        limit_val = 100
    return min(limit_val, 500), None


def _internal_error_response(context: str) -> Tuple[Response, int]:
    logger.exception("Hall of Rust endpoint failed: %s", context)
    return jsonify({"error": "internal_error"}), 500


# ── shared leaderboard logic ────────────────────────────────────────────────


def _build_leaderboard(limit: int, deceased_filter: Optional[str]) -> Tuple[Optional[dict], Optional[Response]]:
    """Return (data, None) or (None, error_response)."""
    try:
        db_path = current_app.config.get("DB_PATH", "/root/rustchain/rustchain_v2.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        where_clause = ""
        params: list = []
        if deceased_filter == "1":
            where_clause = "WHERE is_deceased = 1"
        elif deceased_filter == "0":
            where_clause = "WHERE is_deceased = 0 OR is_deceased IS NULL"

        c.execute(
            f"""
            SELECT fingerprint_hash, miner_id, device_family, device_arch,
                   device_model, manufacture_year, rust_score, total_attestations,
                   capacitor_plague, is_deceased, nickname,
                   first_attestation, last_attestation, thermal_events
            FROM hall_of_rust
            {where_clause}
            ORDER BY rust_score DESC
            LIMIT ?
            """,
            params + [limit],
        )
        rows = c.fetchall()
        conn.close()

        leaderboard = []
        now_year = time.gmtime().tm_year
        for idx, row in enumerate(rows, 1):
            entry = dict(row)
            entry["rank"] = idx
            entry["badge"] = get_rust_badge(float(entry.get("rust_score") or 0))
            mfg = entry.get("manufacture_year")
            entry["age_years"] = max(0, now_year - int(mfg)) if mfg else None
            leaderboard.append(entry)

        return {
            "leaderboard": leaderboard,
            "total_machines": len(leaderboard),
            "generated_at": int(time.time()),
        }, None
    except Exception:
        return None, _internal_error_response("api_hall_of_fame_leaderboard")


# ── endpoints ───────────────────────────────────────────────────────────────


@hall_bp.route("/api/hall_of_fame", methods=["GET"])
def api_hall_of_fame_root() -> Union[Response, Tuple[Response, int]]:
    """
    Public Hall of Fame root endpoint — compatibility alias.

    Returns the same JSON payload as /api/hall_of_fame/leaderboard so that
    consumers who call ``fetch('/api/hall_of_fame')`` (as deployed on the
    production hall-of-fame page) get the leaderboard data rather than a 404.
    """
    err = _require_admin()
    if err:
        return err

    limit, error_response = _parse_limit_arg()
    if error_response:
        return error_response
    deceased_filter = request.args.get("deceased")

    data, err_response = _build_leaderboard(limit, deceased_filter)
    if err_response:
        return err_response
    return jsonify(data)


@hall_bp.route("/api/hall_of_fame/leaderboard", methods=["GET"])
def api_hall_of_fame_leaderboard() -> Union[Response, Tuple[Response, int]]:
    """Public leaderboard API — for embedding in dashboards."""
    err = _require_admin()
    if err:
        return err

    limit, error_response = _parse_limit_arg()
    if error_response:
        return error_response
    deceased_filter = request.args.get("deceased")

    data, err_response = _build_leaderboard(limit, deceased_filter)
    if err_response:
        return err_response
    return jsonify(data)


@hall_bp.route("/api/hall_of_fame/machine", methods=["GET"])
def api_hall_of_fame_machine() -> Union[Response, Tuple[Response, int]]:
    """Get machine by ID — for embedding in dashboards."""
    err = _require_admin()
    if err:
        return err

    machine_id = request.args.get("id")
    if not machine_id:
        return jsonify({"error": "missing 'id' query parameter"}), 400

    try:
        db_path = current_app.config.get("DB_PATH", "/root/rustchain/rustchain_v2.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            """
            SELECT fingerprint_hash, miner_id, device_family, device_arch,
                   device_model, manufacture_year, rust_score, total_attestations,
                   capacitor_plague, is_deceased, nickname,
                   first_attestation, last_attestation, thermal_events
            FROM hall_of_rust
            WHERE fingerprint_hash = ?
            """,
            (machine_id,),
        )
        row = c.fetchone()
        conn.close()

        if not row:
            return jsonify({"error": "machine not found"}), 404

        machine = dict(row)
        machine["badge"] = get_rust_badge(float(machine.get("rust_score") or 0))
        mfg = machine.get("manufacture_year")
        machine["age_years"] = max(0, time.gmtime().tm_year - int(mfg)) if mfg else None
        return jsonify({"machine": machine})
    except Exception:
        return _internal_error_response("api_hall_of_fame_machine")


@hall_bp.route("/api/hall_of_fame/stats", methods=["GET"])
def api_hall_of_fame_stats() -> Union[Response, Tuple[Response, int]]:
    """Public stats endpoint — aggregates for dashboard widgets."""
    err = _require_admin()
    if err:
        return err

    try:
        db_path = current_app.config.get("DB_PATH", "/root/rustchain/rustchain_v2.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute(
            """
            SELECT
                COUNT(*)                                            AS total_machines,
                COALESCE(SUM(total_attestations), 0)                AS total_attestations,
                COALESCE(SUM(thermal_events), 0)                    AS total_thermal_events,
                COALESCE(AVG(rust_score), 0)                        AS avg_rust_score,
                COALESCE(SUM(CASE WHEN is_deceased = 1 THEN 1 ELSE 0 END), 0)
                                                                    AS deceased_count,
                COALESCE(SUM(CASE WHEN capacitor_plague = 1 THEN 1 ELSE 0 END), 0)
                                                                    AS plague_count
            FROM hall_of_rust
            """
        )
        row = dict(c.fetchone())
        conn.close()

        return jsonify({
            "stats": {
                "total_machines": row["total_machines"],
                "total_attestations": row["total_attestations"],
                "total_thermal_events": row["total_thermal_events"],
                "avg_rust_score": round(float(row["avg_rust_score"]), 2),
                "deceased_count": row["deceased_count"],
                "plague_count": row["plague_count"],
            },
            "generated_at": int(time.time()),
        })
    except Exception:
        return _internal_error_response("api_hall_of_fame_stats")
