"""
reservation_server — Flask API server for the Rent-a-Relic Market.
Implements:
  POST /relic/reserve       — Reserve time on a machine
  GET  /relic/available     — List available machines
  GET  /relic/receipt/<id>  — Get provenance receipt for a session
  GET  /relic/machines      — Full machine details
  POST /relic/complete      — Complete a rental and generate receipt
  GET  /relic/rentals       — List rentals for an address
  GET  /relic/escrow/summary — Escrow state
"""
import json
import time
import uuid
import sqlite3
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
from flask import Flask, jsonify, request

from .machine_registry import MachineRegistry, Machine
from .escrow import EscrowManager, EscrowState
from .provenance_receipt import ProvenanceReceiptManager

app = Flask(__name__)

# ─── Database Setup ──────────────────────────────────────────────────────────

RESERVATIONS_DB = Path(__file__).parent / "reservations.db"


def _init_reservation_db():
    with sqlite3.connect(RESERVATIONS_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                rental_id TEXT PRIMARY KEY,
                machine_token_id INTEGER,
                renter TEXT,
                slot_hours INTEGER,
                start_time REAL,
                end_time REAL,
                rtc_locked REAL,
                escrow_id TEXT,
                state TEXT DEFAULT 'pending',
                created_at REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_renter ON reservations(renter)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_machine ON reservations(machine_token_id)")
        conn.commit()


_init_reservation_db()

# ─── Managers ────────────────────────────────────────────────────────────────

registry = MachineRegistry()
escrow_mgr = EscrowManager()
receipt_mgr = ProvenanceReceiptManager()


# ─── Helpers ────────────────────────────────────────────────────────────────

@dataclass
class Reservation:
    rental_id: str
    machine_token_id: int
    renter: str
    slot_hours: int
    start_time: float
    end_time: float
    rtc_locked: float
    escrow_id: str
    state: str
    created_at: float

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row) -> "Reservation":
        return cls(*row)


def _get_active_reservations(machine_token_id: int) -> List[Reservation]:
    """Return all active (non-completed, non-cancelled) reservations for a machine."""
    with sqlite3.connect(RESERVATIONS_DB) as conn:
        rows = conn.execute(
            "SELECT * FROM reservations WHERE machine_token_id = ? AND state NOT IN ('completed','cancelled')",
            (machine_token_id,)
        ).fetchall()
    return [Reservation.from_row(r) for r in rows]


def _is_slot_available(machine_token_id: int, start_time: float, end_time: float) -> bool:
    """Check if a time slot conflicts with any existing active reservation."""
    active = _get_active_reservations(machine_token_id)
    for r in active:
        # Conflict if: existing starts before new ends AND existing ends after new starts
        if r.start_time < end_time and r.end_time > start_time:
            return False
    return True


def _compute_available_slots(machine_token_id: int, slot_hours: int) -> List[Dict]:
    """
    Compute available 1-hour slots for the next 7 days.
    Returns list of {start, end} for each available slot.
    """
    now = time.time()
    slots = []
    day_seconds = 24 * 3600
    slot_seconds = slot_hours * 3600

    for day_offset in range(7):
        day_start = now + day_offset * day_seconds
        # Align to next hour boundary
        aligned = int((day_start + 3599) / 3600) * 3600
        for hour_offset in range(24 // slot_hours):
            start = aligned + hour_offset * slot_seconds
            end = start + slot_seconds
            if start >= now and _is_slot_available(machine_token_id, start, end):
                slots.append({
                    "start": start,
                    "end": end,
                    "start_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start)),
                    "end_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(end)),
                })
    return slots


# ─── Routes ─────────────────────────────────────────────────────────────────

@app.route("/relic/available", methods=["GET"])
def get_available():
    """
    GET /relic/available
    Query params: slot_hours (int, default 1), machine_token_id (optional filter)
    Returns available machines with their upcoming slots.
    """
    slot_hours = int(request.args.get("slot_hours", 1))
    filter_token = request.args.get("machine_token_id")

    machines = registry.list_machines(active_only=True)
    result = []

    for m in machines:
        if filter_token is not None and str(m.token_id) != str(filter_token):
            continue
        slots = _compute_available_slots(m.token_id, slot_hours)
        # Show only next 10 slots to keep response lean
        result.append({
            "token_id": m.token_id,
            "name": m.name,
            "model": m.model,
            "specs": m.specs,
            "photo_url": m.photo_url,
            "hourly_rate_rtc": m.hourly_rate_rtc,
            "total_uptime": m.uptime_formatted,
            "total_rentals": m.total_rentals,
            "next_available_slots": slots[:10],
        })

    return jsonify({"machines": result, "query_slot_hours": slot_hours})


@app.route("/relic/machines", methods=["GET"])
def get_machines():
    """GET /relic/machines — Full machine registry."""
    machines = registry.list_machines(active_only=False)
    return jsonify({
        "machines": [m.to_dict() for m in machines],
        "total": len(machines),
    })


@app.route("/relic/reserve", methods=["POST"])
def reserve():
    """
    POST /relic/reserve
    Body: { machine_token_id, slot_hours, start_time (unix ts), renter }
    Returns: { rental_id, escrow_id, rtc_locked, receipt_pending }
    """
    body = request.get_json()
    if not body:
        return jsonify({"error": "Missing JSON body"}), 400

    machine_token_id = int(body.get("machine_token_id", 0))
    slot_hours = int(body.get("slot_hours", 1))
    start_time = float(body.get("start_time", time.time()))
    renter = str(body.get("renter", ""))

    if not renter:
        return jsonify({"error": "renter address required"}), 400
    if slot_hours not in (1, 4, 24):
        return jsonify({"error": "slot_hours must be 1, 4, or 24"}), 400
    if start_time < time.time():
        return jsonify({"error": "start_time must be in the future"}), 400

    machine = registry.get_machine(machine_token_id)
    if not machine:
        return jsonify({"error": "Machine not found"}), 404
    if not machine.is_active:
        return jsonify({"error": "Machine not active"}), 400

    end_time = start_time + slot_hours * 3600
    if not _is_slot_available(machine_token_id, start_time, end_time):
        return jsonify({"error": "Time slot not available"}), 409

    rtc_locked = machine.hourly_rate_rtc * slot_hours
    rental_id = f"rental_{uuid.uuid4().hex[:16]}"
    escrow_entry = escrow_mgr.lock(rental_id, machine_token_id, renter, rtc_locked)

    with sqlite3.connect(RESERVATIONS_DB) as conn:
        conn.execute("""
            INSERT INTO reservations
            (rental_id, machine_token_id, renter, slot_hours, start_time, end_time,
             rtc_locked, escrow_id, state, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (rental_id, machine_token_id, renter, slot_hours, start_time,
              end_time, rtc_locked, escrow_entry.escrow_id, "pending", time.time()))
        conn.commit()

    return jsonify({
        "rental_id": rental_id,
        "escrow_id": escrow_entry.escrow_id,
        "machine_token_id": machine_token_id,
        "machine_name": machine.name,
        "slot_hours": slot_hours,
        "start_time": start_time,
        "start_time_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_time)),
        "end_time_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(end_time)),
        "rtc_locked": rtc_locked,
        "state": "pending",
        "access_provisioned": False,  # Would integrate with SSH/API provisioning here
        "message": "Reservation created. Access will be provisioned at start_time.",
    }), 201


@app.route("/relic/complete", methods=["POST"])
def complete_rental():
    """
    POST /relic/complete
    Body: { rental_id, output_hash, attestation_proof }
    Generates provenance receipt and releases escrow.
    """
    body = request.get_json()
    if not body:
        return jsonify({"error": "Missing JSON body"}), 400

    rental_id = body.get("rental_id", "")
    output_hash = str(body.get("output_hash", ""))
    attestation_proof = str(body.get("attestation_proof", ""))

    with sqlite3.connect(RESERVATIONS_DB) as conn:
        row = conn.execute(
            "SELECT * FROM reservations WHERE rental_id = ?", (rental_id,)
        ).fetchone()
    if not row:
        return jsonify({"error": "Rental not found"}), 404

    res = Reservation.from_row(row)
    machine = registry.get_machine(res.machine_token_id)
    if not machine:
        return jsonify({"error": "Machine not found"}), 500

    # Update machine uptime
    actual_duration = res.end_time - res.start_time
    registry.update_uptime(res.machine_token_id, int(actual_duration))

    # Generate provenance receipt
    receipt = receipt_mgr.create_receipt(
        machine_passport_id=machine.name,
        machine_model=machine.model,
        session_id=res.rental_id,
        renter=res.renter,
        slot_hours=res.slot_hours,
        start_time=res.start_time,
        end_time=res.end_time,
        output_hash=output_hash or "demo_output_hash",
        attestation_proof=attestation_proof or "hardware_attestation_v1",
    )

    # Release escrow
    escrow_mgr.release(res.escrow_id, f"simulated_tx_{rental_id}")

    # Update reservation state
    with sqlite3.connect(RESERVATIONS_DB) as conn:
        conn.execute(
            "UPDATE reservations SET state = ? WHERE rental_id = ?",
            ("completed", rental_id)
        )
        conn.commit()

    return jsonify({
        "rental_id": rental_id,
        "state": "completed",
        "receipt": receipt.to_dict(),
        "receipt_url": f"/relic/receipt/{receipt.receipt_id}",
    })


@app.route("/relic/receipt/<receipt_id>", methods=["GET"])
def get_receipt(receipt_id):
    """GET /relic/receipt/<receipt_id> — Fetch and verify a provenance receipt."""
    receipt = receipt_mgr.get_receipt(receipt_id)
    if not receipt:
        return jsonify({"error": "Receipt not found"}), 404

    result = receipt.to_dict()
    result["verified"] = receipt.verify()
    return jsonify(result)


@app.route("/relic/rentals", methods=["GET"])
def list_rentals():
    """GET /relic/rentals?renter=<address> — List rentals for an address."""
    renter = request.args.get("renter")
    if not renter:
        return jsonify({"error": "renter address required"}), 400

    with sqlite3.connect(RESERVATIONS_DB) as conn:
        rows = conn.execute(
            "SELECT * FROM reservations WHERE renter = ? ORDER BY created_at DESC",
            (renter,)
        ).fetchall()

    rentals = []
    for row in rows:
        r = Reservation.from_row(row)
        machine = registry.get_machine(r.machine_token_id)
        rentals.append({
            **r.to_dict(),
            "machine_name": machine.name if machine else "Unknown",
            "machine_model": machine.model if machine else "Unknown",
        })
    return jsonify({"rentals": rentals, "total": len(rentals)})


@app.route("/relic/escrow/summary", methods=["GET"])
def escrow_summary():
    """GET /relic/escrow/summary — Escrow state overview."""
    return jsonify(escrow_mgr.summary())


@app.route("/relic/cancel", methods=["POST"])
def cancel_reservation():
    """POST /relic/cancel — Cancel a pending reservation and refund."""
    body = request.get_json()
    rental_id = body.get("rental_id", "") if body else ""
    renter = body.get("renter", "") if body else ""

    with sqlite3.connect(RESERVATIONS_DB) as conn:
        row = conn.execute(
            "SELECT * FROM reservations WHERE rental_id = ? AND renter = ?",
            (rental_id, renter)
        ).fetchone()
    if not row:
        return jsonify({"error": "Reservation not found or not yours"}), 404

    res = Reservation.from_row(row)
    if res.state != "pending":
        return jsonify({"error": f"Cannot cancel: state is {res.state}"}), 400

    refunded = escrow_mgr.refund(res.escrow_id)
    with sqlite3.connect(RESERVATIONS_DB) as conn:
        conn.execute(
            "UPDATE reservations SET state = ? WHERE rental_id = ?",
            ("cancelled", rental_id)
        )
        conn.commit()

    return jsonify({
        "rental_id": rental_id,
        "state": "cancelled",
        "refunded": refunded,
        "rtc_refunded": res.rtc_locked,
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": time.time()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
