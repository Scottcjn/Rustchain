# SPDX-License-Identifier: MIT
"""RIP-302-SEC / SEC-2 auth gates.

Before these gates, poster_wallet and worker_wallet were plain strings: anyone
could post a job as another wallet (moving its balance into escrow) or accept a
delivery as the poster (releasing that escrow). These tests pin the gates shut.
Deliberately does NOT use the operator-authorised client from
rip302_auth_helpers.
"""
import hashlib
import sqlite3

import pytest
from flask import Flask
from nacl.signing import SigningKey

import rip302_agent_economy as r302
from tests.rip302_auth_helpers import SETTLEMENT_KEY, settlement_sig

ADMIN_KEY = "a" * 64
JOB = {
    "title": "Write a scraper",
    "description": "Scrape the public listing page and return a CSV of rows.",
    "category": "code",
    "reward_rtc": 1,
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(r302, "SETTLEMENT_PUBKEY_HEX", SETTLEMENT_KEY.verify_key.encode().hex())
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN_KEY)
    db = tmp_path / "jobs.db"
    app = Flask(__name__)
    r302.register_agent_economy(app, str(db))
    user = SigningKey(bytes([7] * 32))
    pub = user.verify_key.encode().hex()
    wallet = "RTC" + hashlib.sha256(bytes.fromhex(pub)).hexdigest()[:40]
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL)")
        conn.executemany("INSERT INTO balances VALUES (?, ?)",
                         [("poster", 50_000_000), (wallet, 50_000_000)])
    return {"client": app.test_client(), "db": db, "key": user, "pub": pub, "wallet": wallet}


def _balance(db, wallet):
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", (wallet,)).fetchone()
    return row[0] if row else 0


def _signed_create(env, nonce="n1", **over):
    body = {**JOB, "poster_wallet": env["wallet"], "nonce": nonce, **over}
    reward, _ = r302._parse_job_reward(body["reward_rtc"])
    msg = r302._create_job_message(env["wallet"], nonce, reward, body["category"])
    body["poster_pubkey"] = env["pub"]
    body["poster_sig"] = env["key"].sign(msg).signature.hex()
    return body


def test_named_wallet_create_needs_admin_key(env):
    c = env["client"]
    r = c.post("/agent/jobs", json={**JOB, "poster_wallet": "poster"})
    assert r.status_code == 401 and r.get_json()["code"] == "ADMIN_KEY_REQUIRED"
    r = c.post("/agent/jobs", json={**JOB, "poster_wallet": "poster"},
               headers={"X-Admin-Key": "wrong"})
    assert r.status_code == 401
    assert _balance(env["db"], "poster") == 50_000_000
    r = c.post("/agent/jobs", json={**JOB, "poster_wallet": "poster"},
               headers={"X-Admin-Key": ADMIN_KEY})
    assert r.status_code == 201


def test_keyed_wallet_create_needs_its_own_signature(env):
    c = env["client"]
    r = c.post("/agent/jobs", json={**JOB, "poster_wallet": env["wallet"]})
    assert r.status_code == 401 and r.get_json()["code"] == "SIG_REQUIRED"
    # Someone else's key can't post as this wallet.
    forged = _signed_create(env)
    forged["poster_pubkey"] = SigningKey(bytes([9] * 32)).verify_key.encode().hex()
    assert c.post("/agent/jobs", json=forged).status_code == 401
    # A signature for 1 RTC can't be replayed onto 500 RTC.
    tampered = {**_signed_create(env), "reward_rtc": 500}
    assert c.post("/agent/jobs", json=tampered).status_code == 401
    assert _balance(env["db"], env["wallet"]) == 50_000_000
    assert c.post("/agent/jobs", json=_signed_create(env)).status_code == 201


def test_create_signature_is_single_use(env):
    c = env["client"]
    body = _signed_create(env, nonce="once")
    assert c.post("/agent/jobs", json=body).status_code == 201
    assert c.post("/agent/jobs", json=body).status_code in (400, 401, 409)


def test_create_refused_without_settlement_key(env, monkeypatch):
    monkeypatch.setattr(r302, "SETTLEMENT_PUBKEY_HEX", "")
    r = env["client"].post("/agent/jobs", json=_signed_create(env))
    assert r.status_code == 400 and "signed_settlement_unavailable" in r.get_json()["error"]


def _delivered_job(env):
    c = env["client"]
    job_id = c.post("/agent/jobs", json=_signed_create(env)).get_json()["job_id"]
    assert c.post(f"/agent/jobs/{job_id}/claim", json={"worker_wallet": "worker"}).status_code == 200
    assert c.post(f"/agent/jobs/{job_id}/deliver", json={
        "worker_wallet": "worker", "result_summary": "done",
        "deliverable_url": "https://example.com/out.csv"}).status_code == 200
    return job_id


@pytest.mark.parametrize("action", ["accept", "dispute"])
def test_settlement_needs_authority_signature(env, action):
    c = env["client"]
    job_id = _delivered_job(env)
    body = {"poster_wallet": env["wallet"], "reason": "not what I asked for"}
    # Knowing the poster string is no longer enough.
    assert c.post(f"/agent/jobs/{job_id}/{action}", json=body).status_code in (401, 403)
    # A signature for another job or another action doesn't transfer.
    for sig in (settlement_sig("other-job", action),
                settlement_sig(job_id, "cancel" if action != "cancel" else "accept"),
                SigningKey(bytes([3] * 32)).sign(f"{job_id}:{action}".encode()).signature.hex()):
        r = c.post(f"/agent/jobs/{job_id}/{action}", json={**body, "settlement_sig": sig})
        assert r.status_code in (401, 403)
    assert _balance(env["db"], "worker") == 0
    r = c.post(f"/agent/jobs/{job_id}/{action}",
               json={**body, "settlement_sig": settlement_sig(job_id, action)})
    assert r.status_code == 200


def test_cancel_needs_authority_signature(env):
    c = env["client"]
    job_id = c.post("/agent/jobs", json=_signed_create(env)).get_json()["job_id"]
    body = {"poster_wallet": env["wallet"]}
    assert c.post(f"/agent/jobs/{job_id}/cancel", json=body).status_code in (401, 403)
    r = c.post(f"/agent/jobs/{job_id}/cancel",
               json={**body, "settlement_sig": settlement_sig(job_id, "cancel")})
    assert r.status_code == 200
