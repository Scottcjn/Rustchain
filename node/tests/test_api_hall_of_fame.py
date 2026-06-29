from flask import Flask
import sqlite3
import time

from node.hall_of_rust import hall_bp, init_hall_tables


def _app_with_hall_db(tmp_path):
    db_path = tmp_path / "hall.db"
    init_hall_tables(str(db_path))

    # Seed the db with a sample machine
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("""
        INSERT INTO hall_of_rust (
            fingerprint_hash, miner_id, device_family, device_arch,
            device_model, manufacture_year, rust_score, total_attestations,
            capacitor_plague, is_deceased, nickname, first_attestation, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("hash123", "miner123", "family123", "ppc", "model123", 2002, 120.5, 50, 1, 0, "nick123", 1000, 1000))
    conn.commit()
    conn.close()

    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path)
    app.register_blueprint(hall_bp)
    return app


def test_api_hall_of_fame_summary(tmp_path):
    app = _app_with_hall_db(tmp_path)
    client = app.test_client()

    response = client.get("/api/hall_of_fame")
    assert response.status_code == 200
    data = response.get_json()

    assert "stats" in data
    assert "categories" in data
    assert data["stats"]["total_machines"] == 1
    assert data["stats"]["highest_rust_score"] == 120.5
    assert data["stats"]["oldest_year"] == 2002

    assert "ancient_iron" in data["categories"]
    assert len(data["categories"]["ancient_iron"]) == 1
    assert data["categories"]["ancient_iron"][0]["miner_id"] == "miner123"

    assert "exotic_arch" in data["categories"]
    assert len(data["categories"]["exotic_arch"]) == 1
    assert data["categories"]["exotic_arch"][0]["device_arch"] == "ppc"


def test_api_hall_of_fame_stats(tmp_path):
    app = _app_with_hall_db(tmp_path)
    client = app.test_client()

    response = client.get("/api/hall_of_fame/stats")
    assert response.status_code == 200
    data = response.get_json()

    assert data["total_machines"] == 1
    assert data["total_attestations"] == 50
    assert data["highest_rust_score"] == 120.5
    assert data["capacitor_plague_survivors"] == 1
