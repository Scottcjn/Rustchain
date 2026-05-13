# SPDX-License-Identifier: MIT
"""
Bounty Payout Ledger — track RTC bounty payouts across all statuses.
Flat-file module using raw sqlite3, matching RustChain node patterns.
See: node/rustchain_v2_integrated_v2.2.1_rip200.py for DB conventions.

Statuses: queued → pending → confirmed | voided
"""
import os
import time
import sqlite3
import uuid
import json
import logging
from flask import request, jsonify, render_template_string, abort
from functools import wraps

logger = logging.getLogger(__name__)

ADMIN_KEY = os.environ.get("ADMIN_KEY")

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not ADMIN_KEY:
            abort(403, description="Admin key not configured")
        req_key = request.headers.get("X-Admin-Key") or request.args.get("admin_key")
        if req_key != ADMIN_KEY:
            abort(401)
        return f(*args, **kwargs)
    return decorated_function

DB_PATH = os.environ.get("RUSTCHAIN_DB", "rustchain.db")

PAYOUT_LEDGER_COLUMNS = [
    ("id", "TEXT"),
    ("bounty_id", "TEXT NOT NULL DEFAULT ''"),
    ("bounty_title", "TEXT"),
    ("contributor", "TEXT NOT NULL DEFAULT ''"),
    ("wallet_address", "TEXT"),
    ("amount_rtc", "REAL NOT NULL DEFAULT 0"),
    ("status", "TEXT NOT NULL DEFAULT 'queued'"),
    ("pr_url", "TEXT"),
    ("tx_hash", "TEXT"),
    ("notes", "TEXT"),
    ("created_at", "INTEGER NOT NULL DEFAULT 0"),
    ("updated_at", "INTEGER NOT NULL DEFAULT 0"),
]


def _get_columns():
    return [name for name, _definition in PAYOUT_LEDGER_COLUMNS]


def _select_columns_sql():
    return ", ".join(_get_columns())


def _migrate_payout_ledger_schema(conn):
    """Add missing columns for nodes with older payout_ledger tables."""
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(payout_ledger)").fetchall()
    }
    for name, definition in PAYOUT_LEDGER_COLUMNS:
        if name in existing:
            continue
        if name == "id":
            raise RuntimeError("payout_ledger table is missing required primary key column: id")
        conn.execute(f"ALTER TABLE payout_ledger ADD COLUMN {name} {definition}")
        logger.info("Added payout_ledger.%s column", name)

# ── Schema ──────────────────────────────────────────────────────
def init_payout_ledger_tables():
    """Create the payout_ledger table if it does not exist."""
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS payout_ledger (
                id              TEXT PRIMARY KEY,
                bounty_id       TEXT NOT NULL,
                bounty_title    TEXT,
                contributor     TEXT NOT NULL,
                wallet_address  TEXT,
                amount_rtc      REAL NOT NULL DEFAULT 0,
                status          TEXT NOT NULL DEFAULT 'queued',
                pr_url          TEXT,
                tx_hash         TEXT,
                notes           TEXT,
                created_at      INTEGER NOT NULL,
                updated_at      INTEGER NOT NULL
            )
        """)
        _migrate_payout_ledger_schema(c)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_ledger_status
            ON payout_ledger(status)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_ledger_contributor
            ON payout_ledger(contributor)
        """)
        c.commit()
    logger.info("payout_ledger table ready")


# ── Database helpers ────────────────────────────────────────────
def _row_to_dict(row, columns):
    """Convert a sqlite3 row tuple to a dict."""
    return dict(zip(columns, row))


def ledger_list(status=None, contributor=None, limit=100):
    """List payout records, optionally filtered."""
    with sqlite3.connect(DB_PATH) as conn:
        sql = f"SELECT {_select_columns_sql()} FROM payout_ledger WHERE 1=1"
        params = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if contributor:
            sql += " AND contributor = ?"
            params.append(contributor)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    cols = _get_columns()
    return [_row_to_dict(r, cols) for r in rows]


def ledger_get(record_id):
    """Get a single payout record by ID."""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            f"SELECT {_select_columns_sql()} FROM payout_ledger WHERE id = ?", (record_id,)
        ).fetchone()
    if row:
        return _row_to_dict(row, _get_columns())
    return None


def ledger_create(bounty_id, contributor, amount_rtc,
                  bounty_title="", wallet_address="", pr_url="", notes=""):
    """Create a new payout record (status = queued)."""
    record_id = str(uuid.uuid4())
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO payout_ledger"
            " (id, bounty_id, bounty_title, contributor, wallet_address,"
            "  amount_rtc, status, pr_url, tx_hash, notes, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (record_id, bounty_id, bounty_title, contributor, wallet_address,
             amount_rtc, "queued", pr_url, "", notes, now, now),
        )
        conn.commit()
    logger.info("Ledger record created: %s  bounty=%s  rtc=%.2f", record_id, bounty_id, amount_rtc)
    return record_id


def ledger_update_status(record_id, new_status, tx_hash="", notes=""):
    """Move a record to a new status (queued → pending → confirmed | voided)."""
    valid = {"queued", "pending", "confirmed", "voided"}
    if new_status not in valid:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {valid}")
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE payout_ledger SET status=?, tx_hash=?, notes=?, updated_at=? WHERE id=?",
            (new_status, tx_hash or "", notes or "", now, record_id),
        )
        conn.commit()
    logger.info("Ledger %s → %s", record_id, new_status)


def ledger_summary():
    """Aggregate stats by status."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*), COALESCE(SUM(amount_rtc),0)"
            " FROM payout_ledger GROUP BY status"
        ).fetchall()
    return {r[0]: {"count": r[1], "total_rtc": r[2]} for r in rows}


# ── Flask route registration ───────────────────────────────────
def register_ledger_routes(app):
    """Register /ledger/* routes on the given Flask app."""

    @app.route("/ledger")
    def ledger_page():
        init_payout_ledger_tables()
        status_filter = request.args.get("status")
        records = ledger_list(status=status_filter)
        summary = ledger_summary()
        return render_template_string(LEDGER_HTML, records=records, summary=summary, status_filter=status_filter)

    @app.route("/api/ledger", methods=["GET"])
    def api_ledger_list():
        init_payout_ledger_tables()
        status = request.args.get("status")
        contributor = request.args.get("contributor")
        records = ledger_list(status=status, contributor=contributor)
        return jsonify(records)

    @app.route("/api/ledger/<record_id>", methods=["GET"])
    def api_ledger_get(record_id):
        init_payout_ledger_tables()
        record = ledger_get(record_id)
        if not record:
            return jsonify({"error": "not found"}), 404
        return jsonify(record)

    @app.route("/api/ledger", methods=["POST"])
    @admin_required
    def api_ledger_create():
        init_payout_ledger_tables()
        data = request.get_json(force=True)
        required = ["bounty_id", "contributor", "amount_rtc"]
        for field in required:
            if field not in data:
                return jsonify({"error": f"missing {field}"}), 400
        record_id = ledger_create(
            bounty_id=data["bounty_id"],
            contributor=data["contributor"],
            amount_rtc=float(data["amount_rtc"]),
            bounty_title=data.get("bounty_title", ""),
            wallet_address=data.get("wallet_address", ""),
            pr_url=data.get("pr_url", ""),
            notes=data.get("notes", ""),
        )
        return jsonify({"id": record_id, "status": "queued"}), 201

    @app.route("/api/ledger/<record_id>/status", methods=["PATCH"])
    @admin_required
    def api_ledger_update(record_id):
        init_payout_ledger_tables()
        data = request.get_json(force=True)
        new_status = data.get("status")
        if not new_status:
            return jsonify({"error": "missing status"}), 400
        try:
            ledger_update_status(
                record_id, new_status,
                tx_hash=data.get("tx_hash", ""),
                notes=data.get("notes", ""),
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"id": record_id, "status": new_status})

    @app.route("/api/ledger/summary", methods=["GET"])
    def api_ledger_summary():
        init_payout_ledger_tables()
        return jsonify(ledger_summary())


# ── Inline HTML template (keeps flat structure) ─────────────────
LEDGER_HTML = """<!DOCTYPE html>
<html>
<head>
<title>RustChain Payout Ledger</title>
<style>
  body { font-family: monospace; background: #111; color: #eee; padding: 20px; }
  h1 { color: #f90; }
  table { border-collapse: collapse; width: 100%; margin-top: 16px; }
  th, td { border: 1px solid #333; padding: 6px 10px; text-align: left; font-size: 13px; }
  th { background: #222; color: #f90; }
  tr:hover { background: #1a1a1a; }
  .status-queued { color: #888; }
  .status-pending { color: #ff0; }
  .status-confirmed { color: #0f0; }
  .status-voided { color: #f00; text-decoration: line-through; }
  .summary { display: flex; gap: 20px; margin: 12px 0; }
  .summary-card { background: #1a1a1a; border: 1px solid #333; padding: 10px 16px; border-radius: 6px; }
  .summary-card h3 { margin: 0 0 4px 0; font-size: 13px; color: #888; text-transform: uppercase; }
  .summary-card .val { font-size: 22px; color: #f90; }
  a { color: #3ea6ff; }
  .filters { margin: 10px 0; }
  .filters a { margin-right: 12px; padding: 4px 10px; border: 1px solid #333; border-radius: 4px; text-decoration: none; }
  .filters a.active { border-color: #f90; color: #f90; }
</style>
</head>
<body>
<h1>Payout Ledger</h1>
<div class="summary">
  {% for st, info in summary.items() %}
  <div class="summary-card">
    <h3>{{ st }}</h3>
    <div class="val">{{ info.count }} &middot; {{ "%.1f"|format(info.total_rtc) }} RTC</div>
  </div>
  {% endfor %}
</div>
<div class="filters">
  <a href="/ledger" {% if not status_filter %}class="active"{% endif %}>All</a>
  <a href="/ledger?status=queued" {% if status_filter=='queued' %}class="active"{% endif %}>Queued</a>
  <a href="/ledger?status=pending" {% if status_filter=='pending' %}class="active"{% endif %}>Pending</a>
  <a href="/ledger?status=confirmed" {% if status_filter=='confirmed' %}class="active"{% endif %}>Confirmed</a>
  <a href="/ledger?status=voided" {% if status_filter=='voided' %}class="active"{% endif %}>Voided</a>
</div>
<table>
<tr><th>Bounty</th><th>Contributor</th><th>RTC</th><th>Status</th><th>PR</th><th>TX</th><th>Date</th></tr>
{% for r in records %}
<tr>
  <td>{{ r.bounty_id|e }} {{ r.bounty_title|e }}</td>
  <td>{{ r.contributor|e }}</td>
  <td>{{ "%.1f"|format(r.amount_rtc) }}</td>
  <td class="status-{{ r.status|e }}">{{ r.status|e }}</td>
  <td>{% if r.pr_url %}<a href="{{ r.pr_url|e }}" target="_blank">PR</a>{% endif %}</td>
  <td>{{ r.tx_hash[:12]|e if r.tx_hash else '' }}</td>
  <td>{{ r.created_at }}</td>
</tr>
{% endfor %}
</table>
</body>
</html>"""
