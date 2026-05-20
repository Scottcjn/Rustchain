# SPDX-License-Identifier: MIT
"""Regression coverage for miner header-key schema initialization."""

import sqlite3
import sys


integrated_node = sys.modules["integrated_node"]
ADMIN_KEY = "0" * 32
ADMIN_HEADERS = {"X-API-Key": ADMIN_KEY}


def test_init_db_creates_miner_header_keys_for_headerkey_route(tmp_path, monkeypatch):
    db_path = tmp_path / "rustchain.db"
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN_KEY)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    integrated_node.app.config["TESTING"] = True

    integrated_node.init_db()

    pubkey_hex = "a" * 64
    with integrated_node.app.test_client() as client:
        response = client.post(
            "/miner/headerkey",
            headers=ADMIN_HEADERS,
            json={"miner_id": "miner-a", "pubkey_hex": pubkey_hex},
        )

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "miner_id": "miner-a",
        "pubkey_hex": pubkey_hex,
    }

    with sqlite3.connect(db_path) as db:
        stored = db.execute(
            "SELECT pubkey_hex FROM miner_header_keys WHERE miner_id = ?",
            ("miner-a",),
        ).fetchone()

    assert stored == (pubkey_hex,)
