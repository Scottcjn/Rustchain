import os
import sqlite3

os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)
os.environ.setdefault("DB_PATH", ":memory:")

import integrated_node


def _init_node_registry(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE node_registry (
                node_id TEXT,
                wallet_address TEXT,
                url TEXT,
                name TEXT,
                registered_at INTEGER,
                is_active INTEGER
            )
            """
        )
        conn.execute(
            """
            INSERT INTO node_registry
            (node_id, wallet_address, url, name, registered_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("node-1", "RTC_wallet", "http://127.0.0.1:9000", "local", 123, 1),
        )
        conn.commit()


def test_api_nodes_admin_check_uses_constant_time_compare(tmp_path, monkeypatch):
    db_path = tmp_path / "nodes.db"
    _init_node_registry(db_path)
    api_nodes_globals = integrated_node.api_nodes.__globals__
    monkeypatch.setitem(api_nodes_globals, "DB_PATH", str(db_path))
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key-0000000000000000")

    calls = []
    real_compare_digest = api_nodes_globals["hmac"].compare_digest

    def tracking_compare_digest(expected, provided):
        calls.append((expected, provided))
        return real_compare_digest(expected, provided)

    monkeypatch.setattr(api_nodes_globals["hmac"], "compare_digest", tracking_compare_digest)

    client = api_nodes_globals["app"].test_client()
    response = client.get("/api/nodes", headers={"X-Admin-Key": "wrong-admin-key"})
    assert response.status_code == 200
    assert calls == [("test-admin-key-0000000000000000", "wrong-admin-key")]

    calls.clear()
    response = client.get(
        "/api/nodes",
        headers={"X-Admin-Key": "test-admin-key-0000000000000000"},
    )
    assert response.status_code == 200
    assert calls == [
        ("test-admin-key-0000000000000000", "test-admin-key-0000000000000000")
    ]
