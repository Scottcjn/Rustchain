# SPDX-License-Identifier: MIT
import importlib.util
import math
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "prometheus_exporter.py"


def load_exporter(monkeypatch, *, auth=None, host=None):
    if auth is None:
        monkeypatch.delenv("RUSTCHAIN_AUTH", raising=False)
    else:
        monkeypatch.setenv("RUSTCHAIN_AUTH", auth)

    if host is None:
        monkeypatch.delenv("PROMETHEUS_EXPORTER_HOST", raising=False)
    else:
        monkeypatch.setenv("PROMETHEUS_EXPORTER_HOST", host)

    module_name = "prometheus_exporter_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_metrics_update_ignores_private_key_payload(monkeypatch):
    exporter = load_exporter(monkeypatch)

    exporter.update_metrics_from_source(
        {
            "current_epoch": 42,
            "node_private_key": "0xsupersecret",
            "private_key": "also-secret",
            "difficulty": "not-a-number",
            "network_hashrate": math.inf,
        }
    )

    response = exporter.app.test_client().get("/metrics")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "rustchain_current_epoch 42" in body
    assert "node_private_key" not in body
    assert "0xsupersecret" not in body
    assert "also-secret" not in body
    assert "rustchain_difficulty 0.0" in body
    assert "rustchain_network_hashrate 0.0" in body


def test_exporter_binds_localhost_without_auth_by_default(monkeypatch):
    exporter = load_exporter(monkeypatch)

    assert exporter.EXPORTER_HOST == "127.0.0.1"


def test_exporter_host_can_be_explicitly_configured(monkeypatch):
    exporter = load_exporter(monkeypatch, host="0.0.0.0")

    assert exporter.EXPORTER_HOST == "0.0.0.0"
