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
