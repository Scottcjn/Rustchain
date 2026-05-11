# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tools import testnet_faucet as faucet


@pytest.fixture
def app(tmp_path, monkeypatch):
    db_path = tmp_path / "faucet.db"
    monkeypatch.setattr(faucet, "github_account_age_days", lambda *_args, **_kwargs: 30)
    app = faucet.create_app({"DB_PATH": str(db_path), "DRY_RUN": True})
    app.config.update(TESTING=True)
    return app


def test_faucet_page(app):
    c = app.test_client()
    r = c.get("/faucet")
    assert r.status_code == 200
    assert b"RustChain Testnet Faucet" in r.data


def test_github_user_drip_success(app):
    c = app.test_client()
    r = c.post("/faucet/drip", json={"wallet": "rtc_wallet_1", "github_username": "alice"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["amount"] == 1.0


@pytest.mark.parametrize("body", ["[]", '"wallet"', "42"])
def test_drip_rejects_non_object_json(app, body):
    c = app.test_client()
    r = c.post("/faucet/drip", data=body, content_type="application/json")
    assert r.status_code == 400
    assert r.get_json() == {"ok": False, "error": "json_object_required"}


def test_drip_accepts_form_payload(app):
    c = app.test_client()
    r = c.post("/faucet/drip", data={"wallet": "form_wallet"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_ip_only_limit(app):
    c = app.test_client()
    h = {"X-Forwarded-For": "1.2.3.4"}
    r1 = c.post("/faucet/drip", json={"wallet": "w1"}, headers=h)
    assert r1.status_code == 200

    r2 = c.post("/faucet/drip", json={"wallet": "w2"}, headers=h)
    assert r2.status_code == 429
    assert r2.get_json()["error"] == "rate_limited"


def test_github_old_account_gets_2rtc_limit(tmp_path, monkeypatch):
    db_path = tmp_path / "faucet.db"
    monkeypatch.setattr(faucet, "github_account_age_days", lambda *_args, **_kwargs: 500)
    app = faucet.create_app({"DB_PATH": str(db_path), "DRY_RUN": True})
    app.config.update(TESTING=True)
    c = app.test_client()

    r1 = c.post("/faucet/drip", json={"wallet": "w1", "github_username": "old_user"})
    r2 = c.post("/faucet/drip", json={"wallet": "w2", "github_username": "old_user"})
    r3 = c.post("/faucet/drip", json={"wallet": "w3", "github_username": "old_user"})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
