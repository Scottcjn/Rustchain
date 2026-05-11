import importlib.util
from pathlib import Path

import pytest
from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]


class EventStub:
    glitch_id = "glitch-1"

    def to_dict(self):
        return {"glitch_id": self.glitch_id}


class EngineStub:
    def __init__(self):
        self.history_limit = None
        self.history_agent_id = None
        self.config = {"enabled": True, "base_probability": 0.1}

    def process_message(self, agent_id, message, context=None):
        return f"processed:{message}", None

    def get_glitch_history(self, agent_id=None, limit=50):
        self.history_agent_id = agent_id
        self.history_limit = limit
        return [EventStub() for _ in range(limit)]

    def export_config(self):
        return self.config

    def enable(self):
        self.config["enabled"] = True

    def disable(self):
        self.config["enabled"] = False

    def set_probability(self, value):
        self.config["base_probability"] = value

    def get_persona(self, agent_id):
        return True

    def register_agent(self, agent_id):
        return None


@pytest.fixture
def api_module(monkeypatch):
    module_dir = REPO_ROOT / "issue2288" / "glitch_system" / "src"
    monkeypatch.syspath_prepend(str(module_dir))
    spec = importlib.util.spec_from_file_location("glitch_api_under_test", module_dir / "api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._engine = EngineStub()
    return module


@pytest.fixture
def client(api_module):
    app = Flask(__name__)
    app.register_blueprint(api_module.glitch_bp)
    return app.test_client()


@pytest.mark.parametrize(
    "method,path",
    (
        ("post", "/api/glitch/process"),
        ("post", "/api/glitch/agents/test-agent/register"),
        ("put", "/api/glitch/config"),
        ("post", "/api/glitch/trigger"),
    ),
)
def test_json_routes_reject_non_object_bodies(client, method, path):
    response = getattr(client, method)(path, json=["not", "object"])

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}


@pytest.mark.parametrize(
    "query, expected_error",
    (
        ("limit=abc", "limit_must_be_integer"),
        ("limit=0", "limit_must_be_positive"),
        ("limit=-1", "limit_must_be_positive"),
    ),
)
def test_history_rejects_invalid_limit(client, query, expected_error):
    response = client.get(f"/api/glitch/history?{query}")

    assert response.status_code == 400
    assert response.get_json() == {"error": expected_error}


def test_history_caps_oversized_limit(client, api_module):
    response = client.get("/api/glitch/history?agent_id=bot&limit=500")

    assert response.status_code == 200
    assert api_module._engine.history_agent_id == "bot"
    assert api_module._engine.history_limit == 200
    assert response.get_json()["total"] == 200


def test_process_accepts_valid_json_body(client):
    response = client.post(
        "/api/glitch/process",
        json={"agent_id": "bot", "message": "hello", "context": {"room": "test"}},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "original": "hello",
        "processed": "processed:hello",
        "glitch_occurred": False,
    }
