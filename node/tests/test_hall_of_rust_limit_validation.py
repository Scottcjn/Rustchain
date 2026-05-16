from flask import Flask

from node.hall_of_rust import hall_bp, init_hall_tables


def _app_with_hall_db(tmp_path):
    db_path = tmp_path / "hall.db"
    init_hall_tables(str(db_path))

    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path)
    app.register_blueprint(hall_bp)
    return app


def test_leaderboard_rejects_non_integer_limit(tmp_path):
    app = _app_with_hall_db(tmp_path)

    response = app.test_client().get("/api/hall_of_fame/leaderboard?limit=abc")

    assert response.status_code == 400
    assert response.get_data(as_text=True) == "limit must be an integer"


def test_leaderboard_rejects_negative_limit(tmp_path):
    app = _app_with_hall_db(tmp_path)

    response = app.test_client().get("/api/hall_of_fame/leaderboard?limit=-1")

    assert response.status_code == 400
    assert response.get_data(as_text=True) == "limit must be non-negative"


def test_leaderboard_uses_default_for_empty_limit(tmp_path):
    app = _app_with_hall_db(tmp_path)

    response = app.test_client().get("/api/hall_of_fame/leaderboard?limit=")

    assert response.status_code == 200
    assert response.get_json()["leaderboard"] == []
    assert response.get_json()["total_machines"] == 0
