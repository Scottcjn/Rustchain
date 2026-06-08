import sqlite3
import sys
from types import SimpleNamespace


integrated_node = sys.modules["integrated_node"]


def test_api_stats_route_returns_network_statistics(monkeypatch, tmp_path):
    db_path = tmp_path / "api_stats.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE balances (miner_pk TEXT, amount_i64 INTEGER)")
        conn.execute("CREATE TABLE withdrawals (status TEXT)")
        conn.execute("INSERT INTO balances VALUES ('miner-a', 125000000)")
        conn.execute("INSERT INTO balances VALUES ('miner-b', 0)")
        conn.execute("INSERT INTO withdrawals VALUES ('pending')")
        conn.execute("INSERT INTO withdrawals VALUES ('paid')")

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)
    monkeypatch.setattr(integrated_node, "slot_to_epoch", lambda slot: 85)

    integrated_node.app.config["TESTING"] = True
    response = integrated_node.app.test_client().get("/api/stats")

    assert response.status_code == 200
    data = response.get_json()
    assert data["epoch"] == 85
    assert data["total_miners"] == 2
    assert data["total_balance"] == 125.0
    assert data["pending_withdrawals"] == 1
    assert data["version"] == "2.2.1-security-hardened"


def test_network_info_route_matches_rust_wallet_contract(monkeypatch):
    monkeypatch.setattr(integrated_node, "CHAIN_ID", "rustchain-mainnet-v2")
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 43210)
    monkeypatch.setattr(
        integrated_node,
        "p2p_node",
        SimpleNamespace(peers={"peer-a": object(), "peer-b": object()}),
        raising=False,
    )

    integrated_node.app.config["TESTING"] = True
    response = integrated_node.app.test_client().get("/network/info")

    assert response.status_code == 200
    data = response.get_json()
    assert data == {
        "chain_id": "rustchain-mainnet-v2",
        "network": "mainnet",
        "block_height": 43210,
        "peer_count": 2,
        "min_fee": 1000,
        "version": "2.2.1-security-hardened",
    }
