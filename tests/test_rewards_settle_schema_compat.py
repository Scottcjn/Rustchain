# SPDX-License-Identifier: MIT

import sqlite3


def test_init_db_schema_supports_rewards_settle(tmp_path, monkeypatch):
    import integrated_node
    import rewards_implementation_rip200 as rewards

    db_path = tmp_path / "rewards_settle.sqlite3"
    admin_key = "c" * 32
    monkeypatch.setenv("RC_ADMIN_KEY", admin_key)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 1000)
    monkeypatch.setattr(integrated_node, "slot_to_epoch", lambda slot: slot // integrated_node.EPOCH_SLOTS)
    monkeypatch.setattr(rewards, "DB_PATH", str(db_path))
    monkeypatch.setattr(rewards, "ANTI_DOUBLE_MINING_AVAILABLE", False)
    monkeypatch.setattr(
        rewards,
        "calculate_epoch_rewards_time_aged",
        lambda db_path_arg, epoch, total, current, prev: {"alice": total},
    )

    integrated_node.init_db()
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS miner_attest_recent(miner TEXT, device_arch TEXT)")
        conn.execute("INSERT INTO miner_attest_recent(miner, device_arch) VALUES (?, ?)", ("alice", "x86_64"))
        conn.commit()

    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as client:
        response = client.post(
            "/rewards/settle",
            headers={"X-Admin-Key": admin_key},
            json={"epoch": 0},
        )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    with sqlite3.connect(db_path) as conn:
        epoch_cols = {row[1] for row in conn.execute("PRAGMA table_info(epoch_state)")}
        balance_cols = {row[1] for row in conn.execute("PRAGMA table_info(balances)")}
        balance = conn.execute(
            "SELECT miner_id, amount_i64 FROM balances WHERE miner_id = ?",
            ("alice",),
        ).fetchone()
        settled = conn.execute(
            "SELECT settled FROM epoch_state WHERE epoch = ?",
            (0,),
        ).fetchone()

    assert {"settled", "settled_ts"}.issubset(epoch_cols)
    assert {"miner_id", "amount_i64"}.issubset(balance_cols)
    assert balance == ("alice", rewards.PER_EPOCH_URTC)
    assert settled == (1,)
