# SPDX-License-Identifier: MIT
"""Regression tests for miner header key schema initialisation."""

import sys


def test_init_db_creates_miner_header_keys_table(tmp_path):
    node = sys.modules["integrated_node"]
    db_path = tmp_path / "node.sqlite"
    old_db_path = node.DB_PATH
    old_testing = node.app.config.get("TESTING")

    try:
        node.DB_PATH = str(db_path)
        node.init_db()
        node.app.config["TESTING"] = True

        with node.app.test_client() as client:
            response = client.post(
                "/miner/headerkey",
                headers={"X-API-Key": "0" * 32},
                json={"miner_id": "miner-one", "pubkey_hex": "a" * 64},
            )

        assert response.status_code == 200
        assert response.get_json() == {
            "ok": True,
            "miner_id": "miner-one",
            "pubkey_hex": "a" * 64,
        }
    finally:
        node.DB_PATH = old_db_path
        node.app.config["TESTING"] = old_testing
