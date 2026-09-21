# SPDX-License-Identifier: MIT
"""Regression: POST /agent/jobs must fail closed on a node with no usable
settlement verifier, regardless of the require_signed_settlement flag.

_settlement_enforced() enforces signed settlement for EVERY job created after
the cutoff, whatever the client sent. But the verifier-readiness gate at post
time only ran when the client opted in (require_signed=1). So a job posted
with require_signed_settlement=false on a node with no RC_SETTLEMENT_PUBKEY
was created and its escrow locked, and then accept / dispute / cancel all
failed with no_settlement_pubkey_configured. A worker who delivered could
never be paid; the poster could only wait for the TTL auto-refund.
"""
import sqlite3

import pytest
from flask import Flask

import rip302_agent_economy as r302
from tests.rip302_auth_helpers import SETTLEMENT_KEY

ADMIN_KEY = "a" * 64
JOB = {
    "poster_wallet": "poster",
    "title": "Write a scraper",
    "description": "Scrape the public listing page and return a CSV of rows.",
    "category": "code",
    "reward_rtc": 1,
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    # No verifier on this node: pubkey unset.
    monkeypatch.setattr(r302, "SETTLEMENT_PUBKEY_HEX", "")
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN_KEY)
    db = tmp_path / "jobs.db"
    app = Flask(__name__)
    r302.register_agent_economy(app, str(db))
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL)")
        conn.execute("INSERT INTO balances VALUES (?, ?)", ("poster", 50_000_000))
    return {"client": app.test_client(), "db": db}


def _balance(db, wallet):
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", (wallet,)).fetchone()
    return row[0] if row else 0


@pytest.mark.parametrize("flag", [False, 0, "false", "0", "no", "off", ""])
def test_unsigned_flag_cannot_lock_escrow_without_verifier(env, flag):
    r = env["client"].post("/agent/jobs",
                           json={**JOB, "require_signed_settlement": flag},
                           headers={"X-Admin-Key": ADMIN_KEY})
    assert r.status_code == 400, r.data
    assert "signed_settlement_unavailable" in r.get_json()["error"]
    # Nothing moved: escrow was never locked.
    assert _balance(env["db"], "poster") == 50_000_000
    assert _balance(env["db"], r302.ESCROW_WALLET) == 0
    with sqlite3.connect(env["db"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM agent_jobs").fetchone()[0] == 0


def test_signed_flag_still_rejected_without_verifier(env):
    # Pre-existing behaviour, kept.
    r = env["client"].post("/agent/jobs",
                           json={**JOB, "require_signed_settlement": True},
                           headers={"X-Admin-Key": ADMIN_KEY})
    assert r.status_code == 400
    assert "signed_settlement_unavailable" in r.get_json()["error"]


def test_unsigned_flag_posts_fine_when_verifier_is_ready(env, monkeypatch):
    # With a pinned key the job can be settled later, so the post goes through.
    monkeypatch.setattr(r302, "SETTLEMENT_PUBKEY_HEX", SETTLEMENT_KEY.verify_key.encode().hex())
    r = env["client"].post("/agent/jobs",
                           json={**JOB, "require_signed_settlement": False},
                           headers={"X-Admin-Key": ADMIN_KEY})
    assert r.status_code == 201, r.data
    # Escrow now holds reward (+ platform fee); poster was debited.
    assert _balance(env["db"], r302.ESCROW_WALLET) >= 1_000_000
    assert _balance(env["db"], "poster") < 50_000_000
