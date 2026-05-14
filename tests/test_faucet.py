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


@pytest.mark.parametrize(
    ("github_username", "account_age_days", "expected_limit"),
    [
        (None, None, 0.5),
        ("", None, 0.5),
        ("alice", None, 1.0),
        ("alice", 364, 1.0),
        ("alice", 365, 2.0),
    ],
)
def test_limit_for_identity_tiers(github_username, account_age_days, expected_limit):
    assert faucet._limit_for_identity(github_username, account_age_days) == expected_limit


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
