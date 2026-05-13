# SPDX-License-Identifier: MIT
"""
RustChain Machine Passport — Web Viewer & API
Bounty #2309: 70 RTC

Web interface for viewing and managing Machine Passports.
Deployable at rustchain.org/passport/<machine_id>
"""

import json
import os
from datetime import datetime
from typing import Any, Dict

from flask import Flask, render_template, jsonify, request, Response
from passport_ledger import MachinePassport, PassportLedger, RepairEntry, BenchmarkSignature

app = Flask(__name__, template_folder="templates", static_folder="static")
ledger = PassportLedger(data_dir=os.environ.get("PASSPORT_DATA_DIR", "/tmp/passport-ledger"))


def get_json_object() -> Dict[str, Any]:
    """Return the request JSON body when it is an object."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("JSON object required")
    return data


# ── Web Routes ────────────────────────────────────────────────────

@app.route("/")
def index():
    """List all machine passports."""
    return render_template("passport_index.html")


@app.route("/passport/<machine_id>")
def view_passport(machine_id):
    """View a single machine's passport."""
    return render_template("passport_view.html", machine_id=machine_id)


# ── API Routes ────────────────────────────────────────────────────

@app.route("/api/passports", methods=["GET"])
def api_list():
    """List all passports with summary data."""
    passports = []
    for mid in ledger.list_all():
        p = ledger.get(mid)
        if p:
            passports.append({
                "machine_id": p.machine_id,
                "name": p.name,
                "architecture": p.architecture,
                "manufacture_year": p.manufacture_year,
                "tier": p.tier(),
                "total_rtc": p.attestation_history.total_rtc_earned,
                "total_epochs": p.attestation_history.total_epochs,
            })
    return jsonify(passports)


@app.route("/api/passport/<machine_id>", methods=["GET"])
def api_get(machine_id):
    """Get full passport data."""
    p = ledger.get(machine_id)
    if not p:
        return jsonify({"error": "Passport not found"}), 404
    data = p.to_dict()
    data["passport_hash"] = p.compute_passport_hash()
    data["tier"] = p.tier()
    data["hardware_age"] = p.hardware_age()
    return jsonify(data)


@app.route("/api/passport", methods=["POST"])
def api_create():
    """Create or update a machine passport."""
    try:
        data = get_json_object()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if "machine_id" not in data:
        return jsonify({"error": "machine_id required"}), 400

    # Check if exists (update) or new (create)
    existing = ledger.get(data["machine_id"])
    if existing:
        # Update fields
        for field in ["name", "photo_hash", "provenance", "notes", "owner_address"]:
            if field in data:
                setattr(existing, field, data[field])
        existing.updated_at = datetime.utcnow().isoformat() + "Z"
        passport_hash = ledger.save(existing)
    else:
        passport = MachinePassport(**{
            k: v for k, v in data.items()
            if k in MachinePassport.__dataclass_fields__
            and k not in ("repair_log", "attestation_history", "benchmark_signatures")
        })
        passport_hash = ledger.save(passport)

    return jsonify({"passport_hash": passport_hash, "machine_id": data["machine_id"]}), 201


@app.route("/api/passport/<machine_id>/repair", methods=["POST"])
def api_add_repair(machine_id):
    """Add a repair log entry."""
    p = ledger.get(machine_id)
    if not p:
        return jsonify({"error": "Passport not found"}), 404

    try:
        data = get_json_object()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if "date" not in data or "description" not in data:
        return jsonify({"error": "date and description required"}), 400

    p.add_repair(**{k: v for k, v in data.items() if k in RepairEntry.__dataclass_fields__})
    ledger.save(p)
    return jsonify({"ok": True, "repairs": len(p.repair_log)})


@app.route("/api/passport/<machine_id>/benchmark", methods=["POST"])
def api_add_benchmark(machine_id):
    """Add a benchmark signature."""
    p = ledger.get(machine_id)
    if not p:
        return jsonify({"error": "Passport not found"}), 404

    try:
        data = get_json_object()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    sig = BenchmarkSignature(**{k: v for k, v in data.items() if k in BenchmarkSignature.__dataclass_fields__})
    p.add_benchmark(sig)
    ledger.save(p)
    return jsonify({"ok": True, "benchmarks": len(p.benchmark_signatures)})


@app.route("/api/search", methods=["GET"])
def api_search():
    """Search passports by architecture or name."""
    arch = request.args.get("architecture", "")
    name = request.args.get("name", "")
    results = ledger.search(architecture=arch, name=name)
    return jsonify([{
        "machine_id": p.machine_id,
        "name": p.name,
        "architecture": p.architecture,
        "tier": p.tier(),
    } for p in results])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8070, debug=False)
