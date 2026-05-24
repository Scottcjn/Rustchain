# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("api.py")


def load_api_module():
    spec = importlib.util.spec_from_file_location("explorer_api_mempool_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    module._cache.clear()
    return module


def test_mempool_summary_returns_transactions_and_metrics(monkeypatch):
    module = load_api_module()

    def fake_get(path, params=None, timeout=None):
        if path == "/utxo/mempool":
            return {
                "count": 2,
                "transactions": [
                    {
                        "tx_id": "tx-a",
                        "tx_type": "transfer",
                        "inputs": [{"box_id": "box-1"}],
                        "outputs": [{"address": "bob", "value_nrtc": 1000}],
                        "fee_nrtc": 25,
                        "timestamp": 100,
                        "expires_at": 4000,
                    },
                    {
                        "tx_id": "tx-b",
                        "tx_type": "transfer",
                        "inputs": [],
                        "outputs": [],
                        "fee_nrtc": 75,
                    },
                ],
            }
        if path == "/utxo/stats":
            return {
                "mempool_size": 2,
                "unspent_boxes": 8,
                "spent_boxes": 3,
                "total_transactions": 11,
                "state_root": "abc123",
            }
        return None

    monkeypatch.setattr(module, "_get", fake_get)
    monkeypatch.setattr(module.time, "time", lambda: 1000)

    response = module.app.test_client().get("/api/mempool?limit=10")
    assert response.status_code == 200
    body = response.get_json()

    assert body["ok"] is True
    assert body["node_available"] is True
    assert body["metrics"]["mempool_size"] == 2
    assert body["metrics"]["visible_transactions"] == 2
    assert body["metrics"]["total_fee_nrtc"] == 100
    assert body["metrics"]["average_fee_nrtc"] == 50
    assert body["metrics"]["max_fee_nrtc"] == 75
    assert body["metrics"]["state_root"] == "abc123"
    assert body["transactions"][0]["tx_id"] == "tx-a"
    assert body["transactions"][0]["input_count"] == 1
    assert body["transactions"][0]["output_count"] == 1
    assert body["transactions"][0]["age_seconds"] == 900
    assert body["transactions"][0]["expires_in_seconds"] == 3000


def test_mempool_summary_rejects_invalid_limit():
    module = load_api_module()

    response = module.app.test_client().get("/api/mempool?limit=bad")
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "limit_must_be_integer"}
