#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Regression tests for /tx/submit request validation.
"""

from pathlib import Path

from flask import Flask

from node.rustchain_tx_handler import TransactionPool, create_tx_api_routes


def _client_for_tx_routes(db_path: Path):
    app = Flask(__name__)
    app.config["TESTING"] = True
    pool = TransactionPool(str(db_path))
    create_tx_api_routes(app, pool)
    return app.test_client()


def test_tx_submit_rejects_non_object_json(tmp_path):
    with _client_for_tx_routes(tmp_path / "tx.db") as client:
        response = client.post("/tx/submit", json=["not", "an", "object"])

        assert response.status_code == 400
        assert response.get_json() == {"error": "JSON object required"}


def test_tx_submit_rejects_malformed_json_without_500(tmp_path):
    with _client_for_tx_routes(tmp_path / "tx.db") as client:
        response = client.post(
            "/tx/submit",
            data="{",
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.get_json() == {"error": "No JSON data provided"}
