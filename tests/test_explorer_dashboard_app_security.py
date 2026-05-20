# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "explorer" / "dashboard" / "app.py"


def _source() -> str:
    return APP_PATH.read_text(encoding="utf-8")


def _load_module():
    spec = importlib.util.spec_from_file_location("explorer_dashboard_app_under_test", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module


def test_dashboard_table_rows_escape_api_fields_before_inner_html():
    source = _source()

    assert "function escapeHtml(value)" in source
    assert "function displayValue(value)" in source
    assert "${displayValue(m.miner_id||m.wallet)}" in source
    assert "${displayValue(m.score||m.attestation_score)}" in source
    assert "${displayValue(m.multiplier||m.antiquity_multiplier)}" in source
    assert "${escapeHtml(fmtTs(t.timestamp||t.created_at||t.time))}" in source
    assert "${displayValue(t.from||t.sender)}" in source
    assert "${displayValue(t.to||t.recipient)}" in source
    assert "${displayValue(t.amount||t.value)}" in source

    assert "${m.miner_id||m.wallet||'-'}" not in source
    assert "${t.from||t.sender||'-'}" not in source
    assert "${t.to||t.recipient||'-'}" not in source


def test_dashboard_api_normalizes_paginated_rows(monkeypatch):
    module = _load_module()

    def fake_fetch(path):
        responses = {
            "/health": {"status": "ok"},
            "/api/miners": {"miners": [{"miner_id": "miner-1"}], "pagination": {"total": 1}},
            "/epoch": {"epoch": 42},
            "/api/transactions": {
                "transactions": [{"from": "alice", "to": "bob"}],
                "pagination": {"total": 1},
            },
        }
        return responses[path]

    monkeypatch.setattr(module, "fetch_json", fake_fetch)

    response = module.app.test_client().get("/api/dashboard")

    assert response.status_code == 200
    data = response.get_json()
    assert data["miners"] == [{"miner_id": "miner-1"}]
    assert data["transactions"] == [{"from": "alice", "to": "bob"}]
