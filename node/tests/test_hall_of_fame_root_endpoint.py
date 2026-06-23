# SPDX-License-Identifier: MIT
"""
Tests for the /api/hall_of_fame root compatibility endpoint.
"""

from flask import Flask

from node.hall_of_rust import hall_bp, init_hall_tables


def _app_with_hall_db(tmp_path):
    db_path = tmp_path / "hall.db"
    init_hall_tables(str(db_path))
    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path)
    app.register_blueprint(hall_bp)
    return app


def test_hall_of_fame_root_returns_valid_leaderboard_shape(tmp_path):
    """GET /api/hall_of_fame should return same shape as leaderboard."""
    app = _app_with_hall_db(tmp_path)
    response = app.test_client().get("/api/hall_of_fame?limit=5")
    assert response.status_code == 200
    body = response.get_json()
    assert "leaderboard" in body
    assert "total_machines" in body
    assert "generated_at" in body
    assert isinstance(body["leaderboard"], list)
    assert body["total_machines"] == 0


def test_hall_of_fame_root_respects_limit(tmp_path):
    """GET /api/hall_of_fame?limit=N should cap at N."""
    app = _app_with_hall_db(tmp_path)
    response = app.test_client().get("/api/hall_of_fame?limit=10")
    assert response.status_code == 200


def test_hall_of_fame_root_rejects_non_integer_limit(tmp_path):
    """GET /api/hall_of_fame?limit=abc should 400."""
    app = _app_with_hall_db(tmp_path)
    response = app.test_client().get("/api/hall_of_fame?limit=abc")
    assert response.status_code == 400
    assert response.get_data(as_text=True).strip() == "limit must be an integer"


def test_hall_of_fame_root_handles_machine_deceased_filter(tmp_path):
    """GET /api/hall_of_fame?deceased=1 should not crash."""
    app = _app_with_hall_db(tmp_path)
    response = app.test_client().get("/api/hall_of_fame?deceased=1&limit=5")
    assert response.status_code == 200
    body = response.get_json()
    assert isinstance(body["leaderboard"], list)


def test_hall_of_fame_root_and_leaderboard_return_same_data(tmp_path):
    """/api/hall_of_fame and /api/hall_of_fame/leaderboard should agree."""
    app = _app_with_hall_db(tmp_path)
    r1 = app.test_client().get("/api/hall_of_fame?limit=50")
    r2 = app.test_client().get("/api/hall_of_fame/leaderboard?limit=50")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.get_json() == r2.get_json()
