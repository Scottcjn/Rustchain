# SPDX-License-Identifier: MIT
"""Tests for /api/tokenomics (node/tokenomics_route.py).

The endpoint must report supply and ledger counts only. It must not publish a
USD reference rate, a holder-count price schedule, or any milestone trigger.
"""
import sqlite3

import pytest
from flask import Flask

import tokenomics_route as tr


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "ledger.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE balances (miner_id TEXT, amount_i64 INTEGER)")
        conn.executemany(
            "INSERT INTO balances VALUES (?, ?)",
            [("a", 2_500_000), ("b", 500_000), ("c", 0)],
        )
    tr._cache.update(ts=0.0, holders=0, wallets=0, circulating_rtc=0.0)
    app = Flask(__name__)
    tr.register_tokenomics(app, str(db))
    yield app.test_client()
    tr._cache.update(ts=0.0, holders=0, wallets=0, circulating_rtc=0.0)


@pytest.mark.parametrize("path", ["/api/tokenomics", "/tokenomics"])
def test_reports_supply_and_ledger_counts(client, path):
    r = client.get(path)
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True
    assert d["token"] == "RTC"
    assert d["total_supply_rtc"] == 8_388_608
    assert d["holders"] == 2
    assert d["wallets"] == 3
    assert d["circulating_rtc"] == 3.0
    assert isinstance(d["as_of"], int)


def test_no_rate_schedule_fields(client):
    d = client.get("/api/tokenomics").get_json()
    for key in ("reference_rate_usd", "rate_basis", "milestones", "next_milestone"):
        assert key not in d


def test_policy_is_neutral_statement(client):
    d = client.get("/api/tokenomics").get_json()
    assert d["policy"] == tr.POLICY
    assert "no cash value" in d["policy"]
    assert "no off-ramp" in d["policy"]


def test_body_has_no_usd_or_schedule_language(client):
    body = client.get("/api/tokenomics").get_data(as_text=True).lower()
    for s in ("usd", "$", "milestone", "ratchet", "market discovery",
              "reference rate", "holders_remaining", "12458"):
        assert s not in body, s


def test_ledger_error_returns_503(tmp_path):
    tr._cache.update(ts=0.0)
    app = Flask(__name__)
    tr.register_tokenomics(app, str(tmp_path / "missing" / "no.db"))
    r = app.test_client().get("/api/tokenomics")
    assert r.status_code == 503
    assert r.get_json()["ok"] is False
