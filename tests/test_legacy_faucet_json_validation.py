import pytest

import faucet


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(faucet, "DATABASE", str(tmp_path / "faucet.db"))
    faucet.init_db()
    faucet.app.config.update(TESTING=True)
    return faucet.app.test_client()


def test_legacy_faucet_rejects_malformed_json(client):
    response = client.post(
        "/faucet/drip",
        data="{",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid JSON body"}


def test_legacy_faucet_rejects_non_object_json(client):
    response = client.post("/faucet/drip", json=["wallet"])

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid JSON body"}


def test_legacy_faucet_rejects_non_string_wallet(client):
    response = client.post("/faucet/drip", json={"wallet": ["0x123456789"]})

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid wallet address"}


def test_legacy_faucet_rejects_unknown_wallet_prefix(client):
    response = client.post(
        "/faucet/drip",
        json={"wallet": "BAD9d7caca3039130d3b26d41f7343d8f4ef4592360"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid wallet address"}


def test_legacy_faucet_rejects_malformed_native_rtc_wallet(client):
    response = client.post("/faucet/drip", json={"wallet": "RTCzzzzzzzzzz"})

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid wallet address"}


def test_legacy_faucet_accepts_native_rtc_wallet(client):
    wallet = "RTC9d7caca3039130d3b26d41f7343d8f4ef4592360"

    response = client.post("/faucet/drip", json={"wallet": wallet})

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["wallet"] == wallet
