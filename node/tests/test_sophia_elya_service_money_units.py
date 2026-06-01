# SPDX-License-Identifier: MIT
import importlib.util
import sqlite3
import tempfile
from pathlib import Path


def load_service(tmp_path):
    module_path = Path(__file__).resolve().parents[1] / "sophia_elya_service.py"
    spec = importlib.util.spec_from_file_location("sophia_elya_service_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DB_PATH = str(tmp_path / "elya.db")
    return module


def test_balances_schema_uses_integer_micro_rtc():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        service = load_service(Path(tmp))

        service.init_db()

        with sqlite3.connect(service.DB_PATH) as conn:
            columns = {
                row[1]: row[2].upper()
                for row in conn.execute("PRAGMA table_info(balances)").fetchall()
            }

        assert columns["balance_rtc"] == "INTEGER"


def test_finalize_epoch_stores_integer_micro_rtc_and_returns_public_rtc():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        service = load_service(Path(tmp))
        service.init_db()

        with sqlite3.connect(service.DB_PATH) as conn:
            conn.execute(
                "INSERT INTO epoch_state(epoch, accepted_blocks, finalized) VALUES (?,?,?)",
                (7, 1, 0),
            )
            conn.execute(
                "INSERT INTO epoch_enroll(epoch, miner_pk, weight) VALUES (?,?,?)",
                (7, "RTC_miner", 1.0),
            )

        result = service.finalize_epoch(7, 0.1)

        assert result["ok"] is True
        assert result["payouts"] == [("RTC_miner", 0.1)]
        assert service.get_balance("RTC_miner") == 0.1

        with sqlite3.connect(service.DB_PATH) as conn:
            stored_type, stored_value = conn.execute(
                "SELECT typeof(balance_rtc), balance_rtc FROM balances WHERE miner_pk=?",
                ("RTC_miner",),
            ).fetchone()

        assert stored_type == "integer"
        assert stored_value == 100_000


def test_epoch_state_schema_adds_settlement_columns_to_legacy_table():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        service = load_service(Path(tmp))

        with sqlite3.connect(service.DB_PATH) as conn:
            conn.execute(
                "CREATE TABLE epoch_state ("
                "epoch INTEGER PRIMARY KEY, "
                "accepted_blocks INTEGER DEFAULT 0, "
                "finalized INTEGER DEFAULT 0)"
            )
            conn.execute(
                "INSERT INTO epoch_state(epoch, accepted_blocks, finalized) VALUES (?,?,?)",
                (7, 1, 1),
            )

        service.init_db()

        with sqlite3.connect(service.DB_PATH) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(epoch_state)")}
            row = conn.execute(
                "SELECT finalized, settled FROM epoch_state WHERE epoch=?",
                (7,),
            ).fetchone()

        assert {"settled", "settled_ts"} <= columns
        assert row == (1, 1)


def test_finalize_epoch_marks_settled_and_blocks_second_credit():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        service = load_service(Path(tmp))
        service.init_db()

        with sqlite3.connect(service.DB_PATH) as conn:
            conn.execute(
                "INSERT INTO epoch_state(epoch, accepted_blocks, finalized, settled) VALUES (?,?,?,?)",
                (7, 1, 0, 0),
            )
            conn.execute(
                "INSERT INTO epoch_enroll(epoch, miner_pk, weight) VALUES (?,?,?)",
                (7, "RTC_miner", 1.0),
            )

        first = service.finalize_epoch(7, 0.1)
        second = service.finalize_epoch(7, 0.1)

        assert first["ok"] is True
        assert second == {"ok": False, "reason": "already_settled"}
        assert service.get_balance("RTC_miner") == 0.1

        with sqlite3.connect(service.DB_PATH) as conn:
            row = conn.execute(
                "SELECT finalized, settled, settled_ts FROM epoch_state WHERE epoch=?",
                (7,),
            ).fetchone()

        assert row[0] == 1
        assert row[1] == 1
        assert isinstance(row[2], int)


def test_finalize_epoch_respects_existing_settled_marker_without_crediting():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        service = load_service(Path(tmp))
        service.init_db()

        with sqlite3.connect(service.DB_PATH) as conn:
            conn.execute(
                "INSERT INTO epoch_state(epoch, accepted_blocks, finalized, settled) VALUES (?,?,?,?)",
                (7, 1, 0, 1),
            )
            conn.execute(
                "INSERT INTO epoch_enroll(epoch, miner_pk, weight) VALUES (?,?,?)",
                (7, "RTC_miner", 1.0),
            )

        result = service.finalize_epoch(7, 0.1)

        assert result == {"ok": False, "reason": "already_settled"}
        assert service.get_balance("RTC_miner") == 0.0


def test_legacy_real_balances_are_migrated_to_micro_rtc():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        service = load_service(Path(tmp))

        with sqlite3.connect(service.DB_PATH) as conn:
            conn.execute(
                "CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL DEFAULT 0)"
            )
            conn.execute(
                "INSERT INTO balances(miner_pk, balance_rtc) VALUES (?, ?)",
                ("RTC_legacy", 1.234567),
            )

        service.init_db()

        with sqlite3.connect(service.DB_PATH) as conn:
            column_type = conn.execute("PRAGMA table_info(balances)").fetchall()[1][2]
            stored_type, stored_value = conn.execute(
                "SELECT typeof(balance_rtc), balance_rtc FROM balances WHERE miner_pk=?",
                ("RTC_legacy",),
            ).fetchone()

        assert column_type.upper() == "INTEGER"
        assert stored_type == "integer"
        assert stored_value == 1_234_567
        assert service.get_balance("RTC_legacy") == 1.234567


def test_finalize_epoch_idempotent_pays_once():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        service = load_service(Path(tmp))
        service.init_db()
        for _ in range(2):
            service.inc_epoch_block(5)
        service.enroll_epoch(5, "m1", 1.0)
        r1 = service.finalize_epoch(5, 1.5)
        bal1 = service.get_balance("m1")
        r2 = service.finalize_epoch(5, 1.5)
        bal2 = service.get_balance("m1")
        assert r1["ok"] is True
        assert r2["ok"] is False and r2["reason"] == "already_settled"
        assert bal1 == bal2  # double-settlement guard: paid exactly once


def test_inc_epoch_block_does_not_inflate_count_after_finalize():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        service = load_service(Path(tmp))
        service.init_db()
        for _ in range(3):
            service.inc_epoch_block(7)
        service.enroll_epoch(7, "m1", 1.0)
        assert service.finalize_epoch(7, 1.5)["blocks"] == 3
        service.inc_epoch_block(7)  # late block after settlement
        with sqlite3.connect(service.DB_PATH) as conn:
            blocks = conn.execute(
                "SELECT accepted_blocks FROM epoch_state WHERE epoch=7"
            ).fetchone()[0]
        assert blocks == 3  # count the reward was computed against is frozen


def test_null_settled_row_is_still_payable():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        service = load_service(Path(tmp))
        service.init_db()
        service.enroll_epoch(9, "m1", 1.0)
        with sqlite3.connect(service.DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO epoch_state(epoch, accepted_blocks, finalized, settled) "
                "VALUES (9, 2, 0, NULL)"
            )
        res = service.finalize_epoch(9, 1.5)
        assert res["ok"] is True  # NULL settled must not make the epoch unpayable
        assert service.get_balance("m1") > 0
