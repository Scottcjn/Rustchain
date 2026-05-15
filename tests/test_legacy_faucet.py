# SPDX-License-Identifier: MIT
import os
import sys


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import faucet


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(faucet, "DATABASE", str(tmp_path / "faucet.db"))
    faucet.app.config["TESTING"] = True
    faucet.init_db()
    return faucet.app.test_client()


def test_drip_rejects_non_object_json(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/faucet/drip", data='["wallet"]', content_type="application/json")

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid JSON body"}


def test_drip_rejects_malformed_json(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/faucet/drip", data="{", content_type="application/json")

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid JSON body"}


def test_drip_preserves_valid_request(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/faucet/drip", json={"wallet": "0x1234567890"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["wallet"] == "0x1234567890"
