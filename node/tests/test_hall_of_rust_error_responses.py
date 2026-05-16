from pathlib import Path
import sqlite3
import sys

from flask import Flask


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "node"))

import hall_of_rust  # noqa: E402


def _client_for(db_path):
    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path)
    app.register_blueprint(hall_of_rust.hall_bp)
    return app.test_client()


def test_hall_stats_hides_sqlite_error_details(tmp_path):
    db_path = tmp_path / "missing_schema.db"
    sqlite3.connect(db_path).close()
    client = _client_for(db_path)

    response = client.get("/hall/stats")

    assert response.status_code == 500
    assert response.get_json() == {"error": "internal_error"}
    body = response.get_data(as_text=True)
    assert "no such table" not in body
    assert "hall_of_rust" not in body


def test_hall_stats_still_returns_valid_empty_stats(tmp_path):
    db_path = tmp_path / "hall.db"
    hall_of_rust.init_hall_tables(str(db_path))
    client = _client_for(db_path)

    response = client.get("/hall/stats")

    assert response.status_code == 200
    body = response.get_json()
    assert body["total_machines"] == 0
    assert body["total_attestations"] == 0
    assert body["average_rust_score"] == 0


def test_calculate_rust_score_uses_current_year_for_age_weight():
    score = hall_of_rust.calculate_rust_score(
        {
            "manufacture_year": 2001,
            "device_arch": "modern",
            "device_model": "Generic",
            "total_attestations": 0,
            "id": 999,
        },
        current_year=2026,
    )

    assert score == 250


def test_machine_of_the_day_uses_current_year_for_age(tmp_path, monkeypatch):
    db_path = tmp_path / "hall.db"
    hall_of_rust.init_hall_tables(str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO hall_of_rust
            (fingerprint_hash, miner_id, device_arch, device_model, manufacture_year,
             first_attestation, total_attestations, rust_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("fp-1", "miner-1", "modern", "Generic", 2003, 1, 1, 150, 1),
        )
        conn.commit()
    monkeypatch.setattr(hall_of_rust, "_current_utc_year", lambda: 2026)
    client = _client_for(db_path)

    response = client.get("/hall/machine_of_the_day")

    assert response.status_code == 200
    assert response.get_json()["age_years"] == 23
