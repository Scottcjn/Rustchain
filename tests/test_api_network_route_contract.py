import sqlite3
from unittest.mock import MagicMock, patch

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
        conn.executemany(
            """
            INSERT INTO node_registry
            (node_id, wallet_address, url, name, registered_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("node-1", "RTC_wallet_1", "http://node1.example.test", "one", 123, 1),
                ("node-2", "RTC_wallet_2", "http://node2.example.test", "two", 124, 1),
            ],
        )
        conn.commit()


def _fake_get(url, **kwargs):
    response = MagicMock()
    response.status_code = 200
    return response


def test_api_network_returns_documented_network_summary(tmp_path, monkeypatch):
    db_path = tmp_path / "nodes.db"
    _init_node_registry(db_path)
    api_globals = integrated_node.api_network.__globals__
    monkeypatch.setitem(api_globals, "DB_PATH", str(db_path))
    api_globals["_NODE_HEALTH_CACHE"].clear()

    client = api_globals["app"].test_client()
    with patch("requests.get", side_effect=_fake_get):
        response = client.get("/api/network?limit=2")

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["peers"] == 2
    assert data["online_peers"] == 2
    assert data["count"] == 2
    assert data["total"] == 2
    assert [node["node_id"] for node in data["nodes"]] == ["node-1", "node-2"]


def test_api_peers_returns_documented_peer_list(tmp_path, monkeypatch):
    db_path = tmp_path / "nodes.db"
    _init_node_registry(db_path)
    api_globals = integrated_node.api_peers.__globals__
    monkeypatch.setitem(api_globals, "DB_PATH", str(db_path))
    api_globals["_NODE_HEALTH_CACHE"].clear()

    client = api_globals["app"].test_client()
    with patch("requests.get", side_effect=_fake_get):
        response = client.get("/api/peers?limit=1")

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["count"] == 1
    assert data["total"] == 2
    assert len(data["peers"]) == 1
    assert data["peers"][0]["node_id"] == "node-1"


def test_api_network_reuses_node_limit_validation(tmp_path, monkeypatch):
    db_path = tmp_path / "nodes.db"
    _init_node_registry(db_path)
    api_globals = integrated_node.api_network.__globals__
    monkeypatch.setitem(api_globals, "DB_PATH", str(db_path))

    client = api_globals["app"].test_client()
    response = client.get("/api/network?limit=not-an-int")

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "limit must be an integer"}
