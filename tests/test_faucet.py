# SPDX-License-Identifier: MIT

from __future__ import annotations

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
        ("alice", None, 0.5),
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


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ({"wallet": ["rtc_wallet_1"]}, "wallet_must_be_string"),
        ({"wallet": 123}, "wallet_must_be_string"),
        ({"wallet": "rtc_wallet_1", "github_username": ["alice"]}, "github_username_must_be_string"),
        ({"wallet": "rtc_wallet_1", "github_username": 123}, "github_username_must_be_string"),
    ],
)
def test_drip_rejects_non_string_fields(app, payload, error):
    c = app.test_client()
    r = c.post("/faucet/drip", json=payload)
    assert r.status_code == 400
    assert r.get_json() == {"ok": False, "error": error}


def test_ip_only_limit_uses_remote_addr_by_default(app):
    c = app.test_client()
    r1 = c.post(
        "/faucet/drip",
        json={"wallet": "w1"},
        headers={"X-Forwarded-For": "1.2.3.4"},
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
    )
    assert r1.status_code == 200

    r2 = c.post(
        "/faucet/drip",
        json={"wallet": "w2"},
        headers={"X-Forwarded-For": "5.6.7.8"},
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
    )
    assert r2.status_code == 429
    assert r2.get_json()["error"] == "rate_limited"


def test_ip_only_limit_can_trust_proxy_when_configured(tmp_path, monkeypatch):
    db_path = tmp_path / "faucet.db"
    monkeypatch.setattr(faucet, "github_account_age_days", lambda *_args, **_kwargs: 30)
    app = faucet.create_app({"DB_PATH": str(db_path), "DRY_RUN": True, "TRUST_PROXY": True})
    app.config.update(TESTING=True)
    c = app.test_client()
    remote = {"REMOTE_ADDR": "10.0.0.5"}

    r1 = c.post(
        "/faucet/drip",
        json={"wallet": "w1"},
        headers={"X-Forwarded-For": "1.2.3.4"},
        environ_base=remote,
    )
    r2 = c.post(
        "/faucet/drip",
        json={"wallet": "w2"},
        headers={"X-Forwarded-For": "5.6.7.8"},
        environ_base=remote,
    )

    assert r1.status_code == 200
    assert r2.status_code == 200


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


def test_transfer_failure_does_not_expose_upstream_body(tmp_path, monkeypatch):
    db_path = tmp_path / "faucet.db"
    monkeypatch.setattr(faucet, "github_account_age_days", lambda *_args, **_kwargs: 30)

    class FailedTransfer:
        status_code = 500
        text = "admin token=super-secret path=/srv/rustchain/private.db"

    def fake_post(url, json, headers, timeout):
        return FailedTransfer()

    monkeypatch.setattr(faucet.requests, "post", fake_post)
    app = faucet.create_app({"DB_PATH": str(db_path), "DRY_RUN": False})
    app.config.update(TESTING=True)

    r = app.test_client().post(
        "/faucet/drip",
        json={"wallet": "rtc_wallet_1", "github_username": "alice"},
    )
    body = r.get_json()

    assert r.status_code == 502
    assert body == {
        "ok": False,
        "error": "transfer_failed",
        "details": {"error": "transfer_failed_500"},
    }
    response_text = r.get_data(as_text=True)
    assert "super-secret" not in response_text
    assert "/srv/rustchain/private.db" not in response_text
