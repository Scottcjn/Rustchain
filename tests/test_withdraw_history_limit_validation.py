import sqlite3

import integrated_node


def test_withdrawal_history_rejects_non_integer_limit(monkeypatch, tmp_path):
    db_path = tmp_path / "withdrawals.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE withdrawals (withdrawal_id TEXT, miner_pk TEXT, amount REAL, fee REAL, destination TEXT, status TEXT, created_at INTEGER, processed_at INTEGER, tx_hash TEXT, error_msg TEXT)")
        db.execute("CREATE TABLE balances (miner_pk TEXT, balance_rtc REAL)")

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))

    with integrated_node.app.test_client() as client:
        response = client.get(
            "/withdraw/history/miner1?limit=notanumber",
            headers={"X-Admin-Key": "0" * 32},
        )

    assert response.status_code == 400
    assert response.get_json()["error"] == "limit must be an integer"


def test_withdrawal_history_clamps_limit(monkeypatch, tmp_path):
    db_path = tmp_path / "withdrawals.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            CREATE TABLE withdrawals (
                withdrawal_id TEXT,
                miner_pk TEXT,
                amount REAL,
                fee REAL,
                destination TEXT,
                status TEXT,
                created_at INTEGER,
                processed_at INTEGER,
                tx_hash TEXT,
                error_msg TEXT
            )
            """
        )
        db.execute("CREATE TABLE balances (miner_pk TEXT, balance_rtc REAL)")
        db.execute("INSERT INTO balances VALUES (?, ?)", ("miner1", 123.0))
        for idx in range(250):
            db.execute(
                "INSERT INTO withdrawals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (f"w{idx}", "miner1", 1, 0, "dest", "done", idx, idx, "tx", None),
            )

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))

    with integrated_node.app.test_client() as client:
        response = client.get(
            "/withdraw/history/miner1?limit=100000",
            headers={"X-Admin-Key": "0" * 32},
        )

    assert response.status_code == 200
    assert len(response.get_json()["withdrawals"]) == 200
