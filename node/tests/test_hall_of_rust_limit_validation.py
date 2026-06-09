from flask import Flask
import pytest

from node.hall_of_rust import hall_bp, init_hall_tables

ADMIN_KEY = "hall-admin-secret"
ADMIN_HEADERS = {"X-Admin-Key": ADMIN_KEY}


@pytest.fixture(autouse=True)
def _admin_key(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN_KEY)


def _app_with_hall_db(tmp_path):
    db_path = tmp_path / "hall.db"
    init_hall_tables(str(db_path))

    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path)
    app.register_blueprint(hall_bp)
    return app


def test_leaderboard_rejects_non_integer_limit(tmp_path):
    app = _app_with_hall_db(tmp_path)

    with app.test_client() as client:
        client.application.config["TESTING"] = True
        response = client.get(
            "/api/hall_of_fame/leaderboard?limit=abc",
            headers=ADMIN_HEADERS,
        )

    assert response.status_code == 400
    assert response.get_data(as_text=True) == "limit must be an integer"


def test_legacy_leaderboard_rejects_non_integer_limit(tmp_path):
    app = _app_with_hall_db(tmp_path)

    response = app.test_client().get(
        "/hall/leaderboard?limit=abc",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 400
    assert response.get_data(as_text=True) == "limit must be an integer"


def test_leaderboard_rejects_negative_limit(tmp_path):
    app = _app_with_hall_db(tmp_path)

    response = app.test_client().get(
        "/api/hall_of_fame/leaderboard?limit=-1",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 400
    assert response.get_data(as_text=True) == "limit must be non-negative"


def test_legacy_leaderboard_rejects_negative_limit(tmp_path):
    app = _app_with_hall_db(tmp_path)

    response = app.test_client().get(
        "/hall/leaderboard?limit=-1",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 400
    assert response.get_data(as_text=True) == "limit must be non-negative"


def test_leaderboard_uses_default_for_empty_limit(tmp_path):
    app = _app_with_hall_db(tmp_path)

    response = app.test_client().get(
        "/api/hall_of_fame/leaderboard?limit=",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    assert response.get_json()["leaderboard"] == []
    assert response.get_json()["total_machines"] == 0


def test_legacy_leaderboard_uses_default_for_empty_limit(tmp_path):
    app = _app_with_hall_db(tmp_path)

    response = app.test_client().get(
        "/hall/leaderboard?limit=",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    assert response.get_json()["leaderboard"] == []
    assert response.get_json()["total_machines"] == 0
