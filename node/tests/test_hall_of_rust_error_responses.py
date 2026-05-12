from pathlib import Path
import importlib.util
import sqlite3
import sys

from flask import Flask
import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "node"))

import hall_of_rust  # noqa: E402

EXPLORER_HALL_SPEC = importlib.util.spec_from_file_location(
    "explorer_hall_of_rust",
    ROOT / "explorer" / "hall_of_rust.py",
)
explorer_hall_of_rust = importlib.util.module_from_spec(EXPLORER_HALL_SPEC)
EXPLORER_HALL_SPEC.loader.exec_module(explorer_hall_of_rust)

FINGERPRINT = "f" * 32


def _client_for(db_path, module=hall_of_rust):
    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path)
    app.register_blueprint(module.hall_bp)
    return app.test_client()


def _seed_machine(module, db_path):
    module.init_hall_tables(str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO hall_of_rust (
                fingerprint_hash, miner_id, first_attestation, created_at,
                nickname, eulogy, is_deceased
            )
            VALUES (?, 'miner-original', 1, 1, 'original', 'still alive', 0)
            """,
            (FINGERPRINT,),
        )


def _memorial_row(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return dict(conn.execute(
            """
            SELECT nickname, eulogy, is_deceased, deceased_at
            FROM hall_of_rust WHERE fingerprint_hash = ?
            """,
            (FINGERPRINT,),
        ).fetchone())


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


@pytest.mark.parametrize("module", (hall_of_rust, explorer_hall_of_rust))
def test_hall_eulogy_fails_closed_when_admin_key_unconfigured(tmp_path, monkeypatch, module):
    db_path = tmp_path / f"{module.__name__}.db"
    _seed_machine(module, db_path)
    client = _client_for(db_path, module)
    monkeypatch.delenv("RC_ADMIN_KEY", raising=False)

    response = client.post(
        f"/hall/eulogy/{FINGERPRINT}",
        json={"nickname": "owned", "eulogy": "changed", "is_deceased": True},
    )

    assert response.status_code == 503
    assert response.get_json()["error"] == "RC_ADMIN_KEY not configured"
    assert _memorial_row(db_path) == {
        "nickname": "original",
        "eulogy": "still alive",
        "is_deceased": 0,
        "deceased_at": None,
    }


@pytest.mark.parametrize("module", (hall_of_rust, explorer_hall_of_rust))
@pytest.mark.parametrize("headers", ({}, {"X-Admin-Key": "wrong"}))
def test_hall_eulogy_requires_admin_key_before_mutation(tmp_path, monkeypatch, module, headers):
    db_path = tmp_path / f"{module.__name__}.db"
    _seed_machine(module, db_path)
    client = _client_for(db_path, module)
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-secret")

    response = client.post(
        f"/hall/eulogy/{FINGERPRINT}",
        json={"nickname": "owned", "eulogy": "changed", "is_deceased": True},
        headers=headers,
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"
    assert _memorial_row(db_path) == {
        "nickname": "original",
        "eulogy": "still alive",
        "is_deceased": 0,
        "deceased_at": None,
    }


@pytest.mark.parametrize("module", (hall_of_rust, explorer_hall_of_rust))
def test_hall_eulogy_accepts_valid_admin_key(tmp_path, monkeypatch, module):
    db_path = tmp_path / f"{module.__name__}.db"
    _seed_machine(module, db_path)
    client = _client_for(db_path, module)
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-secret")

    response = client.post(
        f"/hall/eulogy/{FINGERPRINT}",
        json={"nickname": "restored", "eulogy": "kept online", "is_deceased": True},
        headers={"X-Admin-Key": "expected-secret"},
    )

    assert response.status_code == 200
    row = _memorial_row(db_path)
    assert row["nickname"] == "restored"
    assert row["eulogy"] == "kept online"
    assert row["is_deceased"] == 1
    assert row["deceased_at"] is not None


@pytest.mark.parametrize("module", (hall_of_rust, explorer_hall_of_rust))
def test_hall_eulogy_rejects_non_ascii_admin_key_without_500(tmp_path, monkeypatch, module):
    db_path = tmp_path / f"{module.__name__}.db"
    _seed_machine(module, db_path)
    client = _client_for(db_path, module)
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-secret")

    response = client.post(
        f"/hall/eulogy/{FINGERPRINT}",
        json={"nickname": "owned", "eulogy": "changed", "is_deceased": True},
        headers={"X-Admin-Key": "é"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"
    assert _memorial_row(db_path) == {
        "nickname": "original",
        "eulogy": "still alive",
        "is_deceased": 0,
        "deceased_at": None,
    }
