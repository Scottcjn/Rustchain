# SPDX-License-Identifier: MIT
import tempfile

import pytest
from flask import Flask

import bottube_mood_engine as mood


@pytest.fixture
def client():
    app = Flask(__name__)
    db_file = tempfile.NamedTemporaryFile(delete=True)
    db_file.close()
    app.config["DB_PATH"] = db_file.name
    app.register_blueprint(mood.mood_bp)
    return app.test_client()


@pytest.mark.parametrize(
    ("weight", "error"),
    (
        (["bad"], "weight must be a number"),
        ("bad", "weight must be a number"),
        (True, "weight must be a number"),
    ),
)
def test_mood_signal_rejects_non_numeric_weight(client, weight, error):
    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        json={
            "signal_type": "video_views",
            "value": {"views": 1},
            "weight": weight,
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": error}


def test_mood_signal_accepts_numeric_weight(client):
    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        json={
            "signal_type": "video_views",
            "value": {"views": 1},
            "weight": 0.5,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["agent_id"] == "bot"
