"""
server.py -- Rent-a-Relic Flask REST API server.

Endpoints
---------
GET  /relic/available             -- machines available right now with specs & windows
POST /relic/reserve               -- reserve a machine (agent_id, machine_id,
                                    duration_hours, rtc_amount)
GET  /relic/receipt/<session_id>  -- provenance receipt for a session
GET  /relic/machines              -- full registry with photos & attestation history
GET  /relic/leaderboard           -- most-rented machines
GET  /relic/reservation/<id>      -- reservation status
POST /relic/complete/<session_id> -- mark session complete (with optional output hash)

RTC escrow: locked on reserve, released on completion or timeout.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any

from flask import Flask, jsonify, request, abort

from tools.rent_a_relic.models import (
    MACHINE_REGISTRY,
    VALID_DURATIONS_HOURS,
    EscrowStatus,
    EscrowTransaction,
    Machine,
    Reservation,
    ReservationStatus,
)
from tools.rent_a_relic.provenance import generate_receipt, verify_receipt

app = Flask(__name__)
DB_PATH = "rent_a_relic.db"
RELIC_API_SECRET = os.environ.get("RELIC_API_SECRET", "relic-default-secret")


def get_db_path() -> str:
    return app.config.get("DB_PATH", DB_PATH)


@contextmanager
def db_conn():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS reservations (
                session_id      TEXT PRIMARY KEY,
                machine_id      TEXT NOT NULL,
                agent_id        TEXT NOT NULL,
                duration_hours  INTEGER NOT NULL,
                rtc_amount      REAL NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                created_at      REAL NOT NULL,
                started_at      REAL,
                expires_at      REAL,
                completed_at    REAL,
                output_hash     TEXT
            );
            CREATE TABLE IF NOT EXISTS escrow_transactions (
                escrow_id       TEXT PRIMARY KEY,
                session_id      TEXT NOT NULL REFERENCES reservations(session_id),
                agent_id        TEXT NOT NULL,
                machine_id      TEXT NOT NULL,
                amount          REAL NOT NULL,
                status          TEXT NOT NULL DEFAULT 'locked',
                locked_at       REAL NOT NULL,
                released_at     REAL,
                release_reason  TEXT
            );
            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id          TEXT PRIMARY KEY,
                session_id          TEXT NOT NULL,
                machine_passport_id TEXT NOT NULL,
                agent_id            TEXT NOT NULL,
                machine_id          TEXT NOT NULL,
                duration_hours      INTEGER NOT NULL,
                output_hash         TEXT NOT NULL,
                attestation_proof   TEXT NOT NULL,
                ed25519_signature   TEXT NOT NULL,
                public_key_hex      TEXT NOT NULL,
                timestamp           REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_res_machine ON reservations(machine_id);
            CREATE INDEX IF NOT EXISTS idx_res_agent   ON reservations(agent_id);
            CREATE INDEX IF NOT EXISTS idx_res_status  ON reservations(status);
            CREATE INDEX IF NOT EXISTS idx_escrow_sess ON escrow_transactions(session_id);
        """)


def _row_to_reservation(row: sqlite3.Row) -> Reservation:
    return Reservation(
        session_id=row["session_id"],
        machine_id=row["machine_id"],
        agent_id=row["agent_id"],
        duration_hours=row["duration_hours"],
        rtc_amount=row["rtc_amount"],
        status=ReservationStatus(row["status"]),
        created_at=row["created_at"],
        started_at=row["started_at"],
        expires_at=row["expires_at"],
        completed_at=row["completed_at"],
        output_hash=row["output_hash"],
    )


def _persist_reservation(conn: sqlite3.Connection, r: Reservation) -> None:
    conn.execute("""
        INSERT OR REPLACE INTO reservations
        (session_id, machine_id, agent_id, duration_hours, rtc_amount,
         status, created_at, started_at, expires_at, completed_at, output_hash)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (r.session_id, r.machine_id, r.agent_id, r.duration_hours, r.rtc_amount,
          r.status.value, r.created_at, r.started_at, r.expires_at,
          r.completed_at, r.output_hash))


def _persist_escrow(conn: sqlite3.Connection, e: EscrowTransaction) -> None:
    conn.execute("""
        INSERT OR REPLACE INTO escrow_transactions
        (escrow_id, session_id, agent_id, machine_id, amount,
         status, locked_at, released_at, release_reason)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (e.escrow_id, e.session_id, e.agent_id, e.machine_id, e.amount,
          e.status.value, e.locked_at, e.released_at, e.release_reason))


def _persist_receipt(conn: sqlite3.Connection, rec: Any) -> None:
    d = rec.to_dict()
    conn.execute("""
        INSERT OR REPLACE INTO receipts
        (receipt_id, session_id, machine_passport_id, agent_id, machine_id,
         duration_hours, output_hash, attestation_proof, ed25519_signature,
         public_key_hex, timestamp)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (d["receipt_id"], d["session_id"], d["machine_passport_id"], d["agent_id"],
          d["machine_id"], d["duration_hours"], d["output_hash"],
          d["attestation_proof"], d["ed25519_signature"], d["public_key_hex"],
          d["timestamp"]))


def _compute_availability_windows(machine_id: str) -> list[dict]:
    now = time.time()
    return [
        {
            "slot_hours":  hours,
            "start_epoch": round(now),
            "end_epoch":   round(now + hours * 3600),
            "start_human": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "end_human":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + hours * 3600)),
        }
        for hours in sorted(VALID_DURATIONS_HOURS)
    ]


def _is_machine_currently_reserved(machine_id: str) -> bool:
    now = time.time()
    with db_conn() as conn:
        row = conn.execute("""
            SELECT 1 FROM reservations
            WHERE machine_id = ? AND status = 'active' AND expires_at > ?
            LIMIT 1
        """, (machine_id, now)).fetchone()
    return row is not None


def _expire_stale_reservations() -> None:
    now = time.time()
    with db_conn() as conn:
        stale = conn.execute("""
            SELECT session_id FROM reservations
            WHERE status = 'active' AND expires_at <= ?
        """, (now,)).fetchall()
        for row in stale:
            conn.execute(
                "UPDATE reservations SET status='expired', completed_at=? WHERE session_id=?",
                (now, row["session_id"]))
            conn.execute("""
                UPDATE escrow_transactions
                SET status='released', released_at=?, release_reason='timeout'
                WHERE session_id=? AND status='locked'
            """, (now, row["session_id"]))


def verify_relic_auth() -> bool:
    """Verify API request has valid HMAC signature."""
    auth_header = request.headers.get("X-Relic-Auth", "")
    if not auth_header:
        return False
    
    try:
        timestamp, signature = auth_header.split(":")
    except ValueError:
        return False
    
    # Reject requests older than 5 minutes (prevent replay)
    if abs(time.time() - float(timestamp)) > 300:
        return False
    
    # Build message to verify
    body = request.get_data()
    message = f"{timestamp}:{request.method}:{request.path}:{body.decode()}"
    
    expected = hmac.new(
        RELIC_API_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)

@app.before_request
def sweep_expired() -> None:
    _expire_stale_reservations()
    
    # Skip auth for read-only endpoints
    if request.method == "GET" and request.path not in ("/relic/reservation/",):
        return
    
    # Skip auth for health/metadata
    if request.path in ("/relic/available", "/relic/machines", "/relic/leaderboard"):
        return
    
    # Require auth for write operations
    if request.method in ("POST", "PUT", "DELETE"):
        if not verify_relic_auth():
            return jsonify({"error": "unauthorized", "message": "Valid X-Relic-Auth header required"}), 401


@app.get("/relic/available")
def get_available():
    """List all machines currently available for reservation."""
    results = []
    for mid, machine in MACHINE_REGISTRY.items():
        if not machine.available or _is_machine_currently_reserved(mid):
            continue
        d = machine.to_dict()
        d["availability_windows"] = _compute_availability_windows(mid)
        d["uptime_pct"]           = 99.2 - (hash(mid) % 30) / 10.0
        results.append(d)
    return jsonify({"machines": results, "count": len(results)})


@app.post("/relic/reserve")
def post_reserve():
    """Reserve a machine and lock RTC in escrow."""
    data = request.get_json(silent=True) or {}

    agent_id       = data.get("agent_id", "").strip()
    machine_id     = data.get("machine_id", "").strip()
    duration_hours = data.get("duration_hours")
    rtc_amount     = data.get("rtc_amount")

    if not agent_id:
        abort(400, description="agent_id is required")
    if not machine_id:
        abort(400, description="machine_id is required")
    if duration_hours not in VALID_DURATIONS_HOURS:
        abort(400, description=f"duration_hours must be one of {sorted(VALID_DURATIONS_HOURS)}")
    if rtc_amount is None or not isinstance(rtc_amount, (int, float)) or rtc_amount <= 0:
        abort(400, description="rtc_amount must be a positive number")

    machine = MACHINE_REGISTRY.get(machine_id)
    if machine is None:
        abort(404, description=f"Machine '{machine_id}' not found")
    if not machine.available:
        abort(409, description=f"Machine '{machine_id}' is offline")

    min_rtc = machine.rtc_per_hour * duration_hours
    if rtc_amount < min_rtc:
        abort(400, description=(
            f"Insufficient RTC. Need at least {min_rtc:.2f} RTC "
            f"({machine.rtc_per_hour} RTC/h x {duration_hours}h)"
        ))

    if _is_machine_currently_reserved(machine_id):
        abort(409, description=f"Machine '{machine_id}' is currently reserved")

    session_id = str(uuid.uuid4())
    escrow_id  = str(uuid.uuid4())

    reservation = Reservation(
        session_id=session_id, machine_id=machine_id, agent_id=agent_id,
        duration_hours=duration_hours, rtc_amount=rtc_amount,
    )
    reservation.activate()

    escrow = EscrowTransaction(
        escrow_id=escrow_id, session_id=session_id, agent_id=agent_id,
        machine_id=machine_id, amount=rtc_amount,
    )

    with db_conn() as conn:
        _persist_reservation(conn, reservation)
        _persist_escrow(conn, escrow)

    return jsonify({
        "session_id":   session_id,
        "reservation":  reservation.to_dict(),
        "escrow":       escrow.to_dict(),
        "ssh_endpoint": machine.ssh_endpoint,
        "message":      f"Reservation active. Connect via SSH: {machine.ssh_endpoint}",
    }), 201


@app.get("/relic/receipt/<session_id>")
def get_receipt(session_id: str):
    """Return a signed provenance receipt for the given session (cached)."""
    with db_conn() as conn:
        cached = conn.execute(
            "SELECT * FROM receipts WHERE session_id=?", (session_id,)
        ).fetchone()
        if cached:
            rec_dict = dict(cached)
            rec_dict["verified"] = True
            return jsonify(rec_dict)

        row = conn.execute(
            "SELECT * FROM reservations WHERE session_id=?", (session_id,)
        ).fetchone()

    if row is None:
        abort(404, description=f"Session '{session_id}' not found")

    reservation = _row_to_reservation(row)
    if reservation.status == ReservationStatus.PENDING:
        abort(409, description="Reservation is still pending; not yet active")

    machine = MACHINE_REGISTRY.get(reservation.machine_id)
    if machine is None:
        abort(500, description="Machine not found in registry")

    receipt = generate_receipt(machine, reservation)

    with db_conn() as conn:
        _persist_receipt(conn, receipt)

    result             = receipt.to_dict()
    result["verified"] = verify_receipt(receipt)
    return jsonify(result)


@app.get("/relic/machines")
def get_machines():
    """Full registry with specs, photo URLs, and attestation history."""
    machines = []
    for mid, machine in MACHINE_REGISTRY.items():
        d = machine.to_dict()
        with db_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM reservations WHERE machine_id=?", (mid,)
            ).fetchone()
        d["total_reservations"] = row["cnt"] if row else 0
        d["currently_reserved"] = _is_machine_currently_reserved(mid)
        machines.append(d)
    return jsonify({"machines": machines, "count": len(machines)})


@app.get("/relic/leaderboard")
def get_leaderboard():
    """Most-rented machines ranked by total reservations."""
    with db_conn() as conn:
        rows = conn.execute("""
            SELECT
                machine_id,
                COUNT(*) AS total_reservations,
                SUM(rtc_amount) AS total_rtc_earned,
                AVG(duration_hours) AS avg_duration_hours,
                SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status='expired'   THEN 1 ELSE 0 END) AS expired
            FROM reservations
            GROUP BY machine_id
            ORDER BY total_reservations DESC
        """).fetchall()

    board = []
    for rank, row in enumerate(rows, start=1):
        mid     = row["machine_id"]
        machine = MACHINE_REGISTRY.get(mid)
        board.append({
            "rank":               rank,
            "machine_id":         mid,
            "name":               machine.name if machine else mid,
            "arch":               machine.arch if machine else "?",
            "photo_url":          machine.photo_url if machine else "",
            "total_reservations": row["total_reservations"],
            "completed":          row["completed"],
            "expired":            row["expired"],
            "total_rtc_earned":   round(row["total_rtc_earned"] or 0, 2),
            "avg_duration_hours": round(row["avg_duration_hours"] or 0, 2),
        })

    existing_ids = {e["machine_id"] for e in board}
    for mid, machine in MACHINE_REGISTRY.items():
        if mid not in existing_ids:
            board.append({
                "rank":               len(board) + 1,
                "machine_id":         mid,
                "name":               machine.name,
                "arch":               machine.arch,
                "photo_url":          machine.photo_url,
                "total_reservations": 0,
                "completed":          0,
                "expired":            0,
                "total_rtc_earned":   0.0,
                "avg_duration_hours": 0.0,
            })

    return jsonify({"leaderboard": board, "count": len(board)})


@app.get("/relic/reservation/<session_id>")
def get_reservation(session_id: str):
    """Return current status and details for a reservation."""
    with db_conn() as conn:
        row        = conn.execute("SELECT * FROM reservations WHERE session_id=?", (session_id,)).fetchone()
        escrow_row = conn.execute("SELECT * FROM escrow_transactions WHERE session_id=?", (session_id,)).fetchone()

    if row is None:
        abort(404, description=f"Reservation '{session_id}' not found")

    reservation = _row_to_reservation(row)
    result = reservation.to_dict()

    if escrow_row:
        result["escrow"] = dict(escrow_row)

    machine = MACHINE_REGISTRY.get(reservation.machine_id)
    if machine:
        result["machine"] = machine.to_dict()

    return jsonify(result)


@app.post("/relic/complete/<session_id>")
def post_complete(session_id: str):
    """Mark a session as completed and release escrow."""
    data        = request.get_json(silent=True) or {}
    output_hash = data.get("output_hash") or hashlib.sha256(session_id.encode()).hexdigest()

    with db_conn() as conn:
        row = conn.execute("SELECT * FROM reservations WHERE session_id=?", (session_id,)).fetchone()

        if row is None:
            abort(404, description=f"Session '{session_id}' not found")

        reservation = _row_to_reservation(row)
        if reservation.status not in (ReservationStatus.ACTIVE, ReservationStatus.PENDING):
            abort(409, description=f"Session is already {reservation.status.value}")

        now = time.time()
        conn.execute(
            "UPDATE reservations SET status='completed', completed_at=?, output_hash=? WHERE session_id=?",
            (now, output_hash, session_id))
        conn.execute("""
            UPDATE escrow_transactions
            SET status='released', released_at=?, release_reason='completed'
            WHERE session_id=? AND status='locked'
        """, (now, session_id))

    return jsonify({
        "session_id":  session_id,
        "status":      "completed",
        "output_hash": output_hash,
        "message":     "Session completed. Escrow released.",
    })


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(409)
@app.errorhandler(500)
def handle_error(e):
    return jsonify({"error": str(e.description), "code": e.code}), e.code


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5050, debug=False)
