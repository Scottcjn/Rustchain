# SPDX-License-Identifier: MIT

import os
import sqlite3
import sys

from flask import Flask


sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "node"))

import rewards_implementation_rip200 as rewards

ADMIN_KEY = "abcdefghijklmnopqrstuvwxyz123456"


def _app_with_balances(tmp_path, monkeypatch):
    db_path = tmp_path / "rewards.db"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)")
        db.execute("INSERT INTO balances VALUES (?, ?)", ("alice", 1_000_000))

    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN_KEY)
    app = Flask(__name__)
    app.config["TESTING"] = True
    rewards.register_rewards_rip200(app, str(db_path))
    return app


def test_wallet_balance_admin_guard_uses_module_hmac(tmp_path, monkeypatch):
    app = _app_with_balances(tmp_path, monkeypatch)

    response = app.test_client().get(
        "/wallet/balance?miner_id=alice",
        headers={"X-Admin-Key": ADMIN_KEY},
    )

    assert response.status_code == 200
    assert response.get_json()["amount_i64"] == 1_000_000


def test_wallet_balance_rejects_wrong_admin_key_without_500(tmp_path, monkeypatch):
    app = _app_with_balances(tmp_path, monkeypatch)

    response = app.test_client().get(
        "/wallet/balance?miner_id=alice",
        headers={"X-Admin-Key": "wrong"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"].startswith("Unauthorized")


def test_all_balances_admin_guard_uses_module_hmac(tmp_path, monkeypatch):
    app = _app_with_balances(tmp_path, monkeypatch)

    response = app.test_client().get(
        "/wallet/balances/all",
        headers={"X-Admin-Key": ADMIN_KEY},
    )

    assert response.status_code == 200
    assert response.get_json()["total_urtc"] == 1_000_000
