# SPDX-License-Identifier: MIT
"""
Tests for OTC bridge precision-column migration hardening.

Two defects closed:
  1. SQL injection — table_name was interpolated straight into PRAGMA/ALTER/
     UPDATE DDL (SQLite can't parameterize identifiers). Now allowlist-gated.
  2. Migration atomicity — concurrent workers racing the PRAGMA->ALTER window
     hit `duplicate column name`. ALTER is now idempotent; COALESCE backfill is
     already idempotent.
"""
import importlib.util
import os
import sqlite3
import sys
from pathlib import Path

import pytest


def load_otc_bridge(tmp_path):
    module_path = Path(__file__).resolve().parents[1] / "otc-bridge" / "otc_bridge.py"
    db_path = tmp_path / "otc_bridge.db"
    previous_db_path = os.environ.get("OTC_DB_PATH")
    os.environ["OTC_DB_PATH"] = str(db_path)

    module_name = f"otc_bridge_migration_test_{abs(hash(db_path))}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        if previous_db_path is None:
            os.environ.pop("OTC_DB_PATH", None)
        else:
            os.environ["OTC_DB_PATH"] = previous_db_path


def _legacy_orders_table(conn):
    """A pre-migration orders table carrying the old float money columns."""
    conn.execute("""
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            amount_rtc REAL,
            price_per_rtc REAL,
            total_quote REAL
        )
    """)
    conn.execute(
        "INSERT INTO orders (order_id, amount_rtc, price_per_rtc, total_quote) "
        "VALUES ('otc_x', 2.5, 0.1, 0.25)"
    )


def test_migration_backfills_integer_columns(tmp_path):
    module = load_otc_bridge(tmp_path)
    conn = sqlite3.connect(":memory:")
    _legacy_orders_table(conn)

    module.migrate_precision_columns(conn.cursor(), "orders")

    row = conn.execute(
        "SELECT amount_micro_rtc, price_per_rtc_nano_quote, total_quote_nano "
        "FROM orders WHERE order_id='otc_x'"
    ).fetchone()
    assert row == (
        round(2.5 * module.RTC_UNIT),
        round(0.1 * module.QUOTE_PRICE_SCALE),
        round(0.25 * module.QUOTE_PRICE_SCALE),
    )


def test_migration_is_idempotent_when_run_twice(tmp_path):
    module = load_otc_bridge(tmp_path)
    conn = sqlite3.connect(":memory:")
    _legacy_orders_table(conn)

    module.migrate_precision_columns(conn.cursor(), "orders")
    # Second run must not raise (the common no-op path).
    module.migrate_precision_columns(conn.cursor(), "orders")

    cols = module.table_columns(conn.cursor(), "orders")
    assert {"amount_micro_rtc", "price_per_rtc_nano_quote", "total_quote_nano"}.issubset(cols)


def test_migration_tolerates_concurrent_duplicate_column(tmp_path):
    """Simulates the race: a column already added by another worker between the
    PRAGMA read and the ALTER. Must be swallowed, not raised."""
    module = load_otc_bridge(tmp_path)
    conn = sqlite3.connect(":memory:")
    _legacy_orders_table(conn)
    # Pre-add one of the precision columns out of band.
    conn.execute("ALTER TABLE orders ADD COLUMN price_per_rtc_nano_quote INTEGER")

    # Should complete and add the remaining columns without raising.
    module.migrate_precision_columns(conn.cursor(), "orders")
    cols = module.table_columns(conn.cursor(), "orders")
    assert {"amount_micro_rtc", "total_quote_nano"}.issubset(cols)


def test_migration_rejects_unknown_table(tmp_path):
    module = load_otc_bridge(tmp_path)
    conn = sqlite3.connect(":memory:")
    with pytest.raises(ValueError):
        module.migrate_precision_columns(conn.cursor(), "orders; DROP TABLE orders")


def test_table_columns_rejects_unknown_table(tmp_path):
    module = load_otc_bridge(tmp_path)
    conn = sqlite3.connect(":memory:")
    with pytest.raises(ValueError):
        module.table_columns(conn.cursor(), "sqlite_master")


def test_real_duplicate_column_error_still_raises(tmp_path):
    """Only `duplicate column name` is swallowed; other OperationalErrors (e.g.
    a missing table) must still surface."""
    module = load_otc_bridge(tmp_path)
    conn = sqlite3.connect(":memory:")  # no 'orders' table at all
    with pytest.raises(sqlite3.OperationalError):
        module.migrate_precision_columns(conn.cursor(), "orders")