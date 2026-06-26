# SPDX-License-Identifier: MIT
import importlib.util
import sys
import types
from pathlib import Path

from flask import Flask


MODULE_PATH = Path(__file__).resolve().parents[1] / "docker-entrypoint.py"


def load_entrypoint(monkeypatch):
    dashboard = types.ModuleType("rustchain_dashboard")
    dashboard.app = Flask("rustchain_dashboard_test")
    monkeypatch.setitem(sys.modules, "rustchain_dashboard", dashboard)

    module_name = "docker_entrypoint_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_malformed_port_env_uses_default(monkeypatch):
    monkeypatch.setenv("PORT", "not-a-port")
    module = load_entrypoint(monkeypatch)

    assert module._safe_int_env("PORT", 8099) == 8099


def test_numeric_port_env_is_preserved(monkeypatch):
    monkeypatch.setenv("PORT", "8100")
    module = load_entrypoint(monkeypatch)

    assert module._safe_int_env("PORT", 8099) == 8100


def test_health_route_registers_with_stub_dashboard(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    module = load_entrypoint(monkeypatch)

    response = module.app.test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "healthy"
