# SPDX-License-Identifier: MIT

import importlib.util
import sqlite3
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "explorer" / "hall_of_rust.py"


def load_explorer_hall():
    spec = importlib.util.spec_from_file_location("explorer_hall_of_rust_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def client_for(module, db_path):
    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path)
    app.register_blueprint(module.hall_bp)
    return app.test_client()


def test_explorer_rust_score_uses_current_year_for_age_bonus(monkeypatch):
    hall = load_explorer_hall()
    monkeypatch.setattr(hall, "current_utc_year", lambda: 2026)

    score = hall.calculate_rust_score(
        {
            "manufacture_year": 2001,
            "device_arch": "modern",
            "device_model": "Generic",
            "total_attestations": 0,
            "id": 999,
        }
    )

    assert score == 250


def test_explorer_rust_score_clamps_future_manufacture_year(monkeypatch):
    hall = load_explorer_hall()
    monkeypatch.setattr(hall, "current_utc_year", lambda: 2026)

    score = hall.calculate_rust_score(
        {
            "manufacture_year": 2027,
            "device_arch": "modern",
            "device_model": "Generic",
            "total_attestations": 0,
            "id": 999,
        }
    )

    assert score == 0


def test_explorer_machine_of_the_day_uses_current_year_for_age(tmp_path, monkeypatch):
    hall = load_explorer_hall()
    monkeypatch.setattr(hall, "current_utc_year", lambda: 2026)
    db_path = tmp_path / "hall.db"
    hall.init_hall_tables(str(db_path))
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO hall_of_rust (
            fingerprint_hash, miner_id, device_arch, device_model,
            manufacture_year, first_attestation, last_attestation,
            rust_score, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("fp-1", "miner-1", "G4", "PowerMac3,6", 2003, 1, 1, 101, 1),
    )
    conn.commit()
    conn.close()
    client = client_for(hall, db_path)

    response = client.get("/hall/machine_of_the_day")

    assert response.status_code == 200
    assert response.get_json()["age_years"] == 23
