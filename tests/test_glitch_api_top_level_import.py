# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
GLITCH_SRC = REPO_ROOT / "issue2288" / "glitch_system" / "src"


def load_top_level_api(monkeypatch):
    monkeypatch.syspath_prepend(str(GLITCH_SRC))
    module_path = GLITCH_SRC / "api.py"
    spec = importlib.util.spec_from_file_location("glitch_api_top_level_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_register_agent_works_when_api_is_loaded_as_top_level_module(monkeypatch):
    api = load_top_level_api(monkeypatch)
    app = Flask(__name__)
    app.register_blueprint(api.glitch_bp)

    response = app.test_client().post(
        "/api/glitch/agents/agent-1/register",
        json={"template": "sophia_elya"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["agent_id"] == "agent-1"
    assert data["persona"]["profile"]["profile_id"] == "sophia_elya"
