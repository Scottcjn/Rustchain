# SPDX-License-Identifier: MIT
"""
Regression test for Hall of Rust re-attestation Rust Score refresh.

Bug: POST /hall/induct on an already-inducted machine incremented
total_attestations but never recomputed rust_score. calculate_rust_score()
rewards attestation loyalty (RUST_WEIGHTS['attestation_count']), so a machine's
leaderboard score stayed frozen at its induction-time value regardless of how
many times it re-attested.
"""

import importlib.util
import sqlite3
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "explorer" / "hall_of_rust.py"


def load_explorer_hall():
    spec = importlib.util.spec_from_file_location(
        "explorer_hall_of_rust_reattest_under_test", MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def app_for(module, db_path):
    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path)
    app.register_blueprint(module.hall_bp)
    module.init_hall_tables(str(db_path))
    return app


def _stored_score(db_path, fingerprint):
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT rust_score, total_attestations FROM hall_of_rust "
            "WHERE fingerprint_hash = ?",
            (fingerprint,),
        ).fetchone()
    finally:
        conn.close()
    return row


def test_reattestation_refreshes_rust_score(tmp_path):
    hall = load_explorer_hall()
    db_path = tmp_path / "hall.db"
    client = app_for(hall, db_path).test_client()

    machine = {
        "device_model": "Generic",
        "device_arch": "modern",
        "cpu_serial": "reattest-serial-1",
        "miner_id": "loyal-miner",
    }

    resp = client.post("/hall/induct", json=machine)
    assert resp.status_code == 200
    fingerprint = resp.get_json()["fingerprint"]

    initial_score, initial_att = _stored_score(db_path, fingerprint)
    assert initial_att == 1

    # Re-attest several times; each adds RUST_WEIGHTS['attestation_count'].
    for _ in range(10):
        resp = client.post("/hall/induct", json=machine)
        assert resp.status_code == 200
        assert resp.get_json()["inducted"] is False

    final_score, final_att = _stored_score(db_path, fingerprint)
    assert final_att == 11

    expected_delta = 10 * hall.RUST_WEIGHTS["attestation_count"]
    # Fails on main: final_score == initial_score (frozen at induction value).
    assert final_score > initial_score
    assert round(final_score - initial_score, 6) == round(expected_delta, 6)


def test_reattestation_response_reports_current_score(tmp_path):
    hall = load_explorer_hall()
    db_path = tmp_path / "hall.db"
    client = app_for(hall, db_path).test_client()

    machine = {
        "device_model": "PowerMac3,4",
        "device_arch": "G4",
        "cpu_serial": "reattest-serial-2",
        "miner_id": "loyal-miner-2",
    }

    first = client.post("/hall/induct", json=machine).get_json()
    fingerprint = first["fingerprint"]

    second = client.post("/hall/induct", json=machine)
    assert second.status_code == 200
    body = second.get_json()

    stored_score, _ = _stored_score(db_path, fingerprint)
    assert body["rust_score"] == stored_score
    assert round(body["rust_score"] - first["rust_score"], 6) == round(
        hall.RUST_WEIGHTS["attestation_count"], 6
    )
