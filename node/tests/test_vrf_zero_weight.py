import os
import sqlite3

os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)
os.environ.setdefault("DB_PATH", ":memory:")

import integrated_node


def _init_epoch_enroll(db_path, weight):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight REAL)"
        )
        conn.execute(
            "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
            (1, "miner-zero", weight),
        )
        conn.commit()


def test_vrf_selection_returns_false_for_zero_total_weight(tmp_path, monkeypatch):
    db_path = tmp_path / "zero_weight.db"
    _init_epoch_enroll(db_path, 0.0)
    monkeypatch.setitem(integrated_node.vrf_is_selected.__globals__, "DB_PATH", str(db_path))

    assert integrated_node.vrf_is_selected("miner-zero", 144) is False


def test_vrf_selection_returns_false_for_sub_fixed_point_total_weight(tmp_path, monkeypatch):
    db_path = tmp_path / "sub_fixed_point_weight.db"
    _init_epoch_enroll(db_path, 0.0000000001)
    monkeypatch.setitem(integrated_node.vrf_is_selected.__globals__, "DB_PATH", str(db_path))

    assert integrated_node.vrf_is_selected("miner-zero", 144) is False
