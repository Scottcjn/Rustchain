# SPDX-License-Identifier: MIT

import importlib.util
import sqlite3
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _client_for(module, db_path):
    app = Flask(module.__name__)
    app.config["DB_PATH"] = str(db_path)
    app.register_blueprint(module.hall_bp)
    return app.test_client()


def _insert_hall_machine(module, db_path, manufacture_year):
    module.init_hall_tables(str(db_path))
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO hall_of_rust (
            fingerprint_hash, miner_id, device_arch, device_model,
            manufacture_year, first_attestation, rust_score, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("fp", "miner", "G5", "PowerMac7,2", manufacture_year, 1, 150, 1),
    )
    conn.commit()
    conn.close()


def test_node_hall_calculate_rust_score_uses_current_year(monkeypatch):
    module = _load_module("node_hall_of_rust_age", "node/hall_of_rust.py")
    monkeypatch.setattr(module, "_current_year", lambda: 2026)

    score = module.calculate_rust_score({
        "manufacture_year": 2001,
        "device_arch": "modern",
        "device_model": "Generic",
        "total_attestations": 0,
        "id": 999,
    })

    assert score == 250


def test_node_hall_machine_of_the_day_uses_current_year_for_age(tmp_path, monkeypatch):
    module = _load_module("node_hall_of_rust_route_age", "node/hall_of_rust.py")
    monkeypatch.setattr(module, "_current_year", lambda: 2026)
    db_path = tmp_path / "node_hall.db"
    _insert_hall_machine(module, db_path, 2003)
    client = _client_for(module, db_path)

    response = client.get("/hall/machine_of_the_day")

    assert response.status_code == 200
    assert response.get_json()["age_years"] == 23


def test_node_hall_machine_of_the_day_preserves_default_age(tmp_path, monkeypatch):
    module = _load_module("node_hall_of_rust_route_default_age", "node/hall_of_rust.py")
    monkeypatch.setattr(module, "_current_year", lambda: 2026)
    db_path = tmp_path / "node_hall_default.db"
    _insert_hall_machine(module, db_path, None)
    client = _client_for(module, db_path)

    response = client.get("/hall/machine_of_the_day")

    assert response.status_code == 200
    assert response.get_json()["age_years"] == 6


def test_node_hall_api_routes_treat_zero_year_as_known(tmp_path, monkeypatch):
    module = _load_module("node_hall_of_rust_api_zero_age", "node/hall_of_rust.py")
    monkeypatch.setattr(module, "_current_year", lambda: 2026)
    db_path = tmp_path / "node_hall_zero.db"
    _insert_hall_machine(module, db_path, 0)
    client = _client_for(module, db_path)

    leaderboard = client.get("/api/hall_of_fame/leaderboard")
    machine = client.get("/api/hall_of_fame/machine?id=fp")

    assert leaderboard.status_code == 200
    assert leaderboard.get_json()["leaderboard"][0]["age_years"] == 2026
    assert machine.status_code == 200
    assert machine.get_json()["machine"]["age_years"] == 2026


def test_explorer_hall_calculate_rust_score_uses_current_year(monkeypatch):
    module = _load_module("explorer_hall_of_rust_age", "explorer/hall_of_rust.py")
    monkeypatch.setattr(module, "_current_year", lambda: 2026)

    score = module.calculate_rust_score({
        "manufacture_year": 2001,
        "device_arch": "modern",
        "device_model": "Generic",
        "total_attestations": 0,
        "id": 999,
    })

    assert score == 250


def test_explorer_hall_machine_of_the_day_uses_current_year_for_age(tmp_path, monkeypatch):
    module = _load_module("explorer_hall_of_rust_route_age", "explorer/hall_of_rust.py")
    monkeypatch.setattr(module, "_current_year", lambda: 2026)
    db_path = tmp_path / "explorer_hall.db"
    _insert_hall_machine(module, db_path, 2003)
    client = _client_for(module, db_path)

    response = client.get("/hall/machine_of_the_day")

    assert response.status_code == 200
    assert response.get_json()["age_years"] == 23


def test_explorer_hall_machine_of_the_day_preserves_default_age(tmp_path, monkeypatch):
    module = _load_module(
        "explorer_hall_of_rust_route_default_age",
        "explorer/hall_of_rust.py",
    )
    monkeypatch.setattr(module, "_current_year", lambda: 2026)
    db_path = tmp_path / "explorer_hall_default.db"
    _insert_hall_machine(module, db_path, None)
    client = _client_for(module, db_path)

    response = client.get("/hall/machine_of_the_day")

    assert response.status_code == 200
    assert response.get_json()["age_years"] == 6


def test_explorer_hall_machine_route_treats_zero_year_as_known(tmp_path, monkeypatch):
    module = _load_module("explorer_hall_of_rust_machine_zero_age", "explorer/hall_of_rust.py")
    monkeypatch.setattr(module, "_current_year", lambda: 2026)
    db_path = tmp_path / "explorer_hall_zero.db"
    _insert_hall_machine(module, db_path, 0)
    client = _client_for(module, db_path)

    response = client.get("/api/hall_of_fame/machine?id=fp")

    assert response.status_code == 200
    assert response.get_json()["machine"]["age_years"] == 2026
