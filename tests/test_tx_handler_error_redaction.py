#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Regression tests for transaction API internal error redaction.
"""

import os

from flask import Flask

from node.rustchain_tx_handler import create_tx_api_routes

# These GET endpoints became admin-gated in #6295 ("require admin auth on tx
# handler GET endpoints — prevents unauthorized transaction surveillance"). The
# redaction these tests verify happens AFTER the auth check, so the request must
# authenticate to reach (and trigger) the internal-error path.
_ADMIN_KEY = "test-admin-key"
_ADMIN_HDR = {"X-Admin-Key": _ADMIN_KEY}


LEAKY_ERROR = "no such table: pending_transactions at /srv/rustchain/prod.db"


class ExplodingPool:
    db_path = "/srv/rustchain/prod.db"

    def _boom(self):
        raise RuntimeError(LEAKY_ERROR)

    def get_transaction_status(self, tx_hash):
        self._boom()

    def get_pending_transactions(self, limit):
        self._boom()

    def get_balance(self, address):
        self._boom()

    def get_available_balance(self, address):
        self._boom()

    def get_pending_amount(self, address):
        self._boom()

    def get_wallet_nonce(self, address):
        self._boom()

    def _get_pending_nonces(self, address):
        self._boom()


def _client_for_exploding_pool():
    os.environ["RC_ADMIN_KEY"] = _ADMIN_KEY  # so require_admin() is configured (not 503)
    app = Flask(__name__)
    app.config["TESTING"] = True
    create_tx_api_routes(app, ExplodingPool())
    return app.test_client()


def _assert_redacted(response):
    assert response.status_code == 500
    assert response.get_json() == {"error": "internal_error"}
    assert b"pending_transactions" not in response.data
    assert b"/srv/rustchain/prod.db" not in response.data


def test_tx_status_redacts_internal_exception_details():
    with _client_for_exploding_pool() as client:
        _assert_redacted(client.get("/tx/status/hash_1", headers=_ADMIN_HDR))


def test_tx_pending_redacts_internal_exception_details():
    with _client_for_exploding_pool() as client:
        _assert_redacted(client.get("/tx/pending", headers=_ADMIN_HDR))


def test_wallet_balance_redacts_internal_exception_details():
    with _client_for_exploding_pool() as client:
        _assert_redacted(client.get("/wallet/alice/balance", headers=_ADMIN_HDR))


def test_wallet_nonce_redacts_internal_exception_details():
    with _client_for_exploding_pool() as client:
        _assert_redacted(client.get("/wallet/alice/nonce", headers=_ADMIN_HDR))


def test_wallet_history_redacts_internal_exception_details(monkeypatch):
    from node import rustchain_tx_handler as tx_handler

    def raise_connect_error(*args, **kwargs):
        raise RuntimeError(LEAKY_ERROR)

    monkeypatch.setattr(tx_handler.sqlite3, "connect", raise_connect_error)

    with _client_for_exploding_pool() as client:
        _assert_redacted(client.get("/wallet/alice/history", headers=_ADMIN_HDR))
