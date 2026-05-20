# SPDX-License-Identifier: MIT

import sqlite3
import sys


def test_init_db_creates_miner_header_keys_for_headerkey_route(tmp_path, monkeypatch):
    node = sys.modules["integrated_node"]
    db_path = tmp_path / "fresh-node.db"
    admin_key = "0" * 32

    monkeypatch.setattr(node, "DB_PATH", str(db_path))
    monkeypatch.setenv("RC_ADMIN_KEY", admin_key)
    monkeypatch.setitem(node.app.config, "TESTING", True)

    node.init_db()

    response = node.app.test_client().post(
        "/miner/headerkey",
        headers={"X-API-Key": admin_key},
        json={"miner_id": "miner-one", "pubkey_hex": "a" * 64},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "miner_id": "miner-one",
        "pubkey_hex": "a" * 64,
    }
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT pubkey_hex FROM miner_header_keys WHERE miner_id = ?",
            ("miner-one",),
        ).fetchone()
    assert row == ("a" * 64,)


def test_headerkey_route_rejects_null_miner_id(tmp_path, monkeypatch):
    node = sys.modules["integrated_node"]
    db_path = tmp_path / "fresh-node.db"
    admin_key = "0" * 32

    monkeypatch.setattr(node, "DB_PATH", str(db_path))
    monkeypatch.setenv("RC_ADMIN_KEY", admin_key)
    monkeypatch.setitem(node.app.config, "TESTING", True)

    node.init_db()

    response = node.app.test_client().post(
        "/miner/headerkey",
        headers={"X-API-Key": admin_key},
        json={"miner_id": None, "pubkey_hex": "a" * 64},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "invalid miner_id or pubkey_hex",
    }
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT pubkey_hex FROM miner_header_keys WHERE miner_id = ?",
            ("None",),
        ).fetchone()
    assert row is None
