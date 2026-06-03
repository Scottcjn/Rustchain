# SPDX-License-Identifier: MIT

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


def _load_migrate_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "db-migrate" / "migrate.py"
    spec = importlib.util.spec_from_file_location("db_migrate", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migrate = _load_migrate_module()


def test_parse_migration_splits_up_and_down_blocks(tmp_path):
    migration = tmp_path / "V0001__create_widgets.sql"
    migration.write_text(
        """
        -- UP
        CREATE TABLE widgets(id INTEGER PRIMARY KEY);
        INSERT INTO widgets(id) VALUES (1);

        -- DOWN
        DROP TABLE widgets;
        """,
        encoding="utf-8",
    )

    up_sql, down_sql = migrate._parse_migration(str(migration))

    assert "CREATE TABLE widgets" in up_sql
    assert "INSERT INTO widgets" in up_sql
    assert "DROP TABLE widgets" not in up_sql
    assert down_sql == "DROP TABLE widgets;"


def test_parse_migration_handles_missing_down_block(tmp_path):
    migration = tmp_path / "V0002__up_only.sql"
    migration.write_text(
        """
        -- up
        CREATE TABLE only_up(id INTEGER);
        """,
        encoding="utf-8",
    )

    up_sql, down_sql = migrate._parse_migration(str(migration))

    assert up_sql == "CREATE TABLE only_up(id INTEGER);"
    assert down_sql == ""


def test_discover_migrations_sorts_valid_files_and_skips_bad_names(tmp_path):
    (tmp_path / "V0020__second_valid.sql").write_text(
        "-- UP\nCREATE TABLE second_valid(id INTEGER);\n-- DOWN\nDROP TABLE second_valid;",
        encoding="utf-8",
    )
    (tmp_path / "not_a_migration.sql").write_text("-- UP\nSELECT 1;", encoding="utf-8")
    (tmp_path / "V0019__first_valid.sql").write_text(
        "-- UP\nCREATE TABLE first_valid(id INTEGER);\n-- DOWN\nDROP TABLE first_valid;",
        encoding="utf-8",
    )

    migrations = migrate._discover_migrations(str(tmp_path))

    assert [m["version"] for m in migrations] == ["0019", "0020"]
    assert [m["name"] for m in migrations] == ["first valid", "second valid"]
    assert all(m["checksum"] for m in migrations)


def test_run_sql_block_ignores_empty_statements_and_executes_each_statement():
    conn = sqlite3.connect(":memory:")

    migrate._run_sql_block(
        conn,
        """
        ;
        CREATE TABLE widgets(id INTEGER PRIMARY KEY, name TEXT);
        ;
        INSERT INTO widgets(name) VALUES ('alpha');
        INSERT INTO widgets(name) VALUES ('beta');
        ;
        """,
    )

    rows = conn.execute("SELECT name FROM widgets ORDER BY id").fetchall()
    conn.close()

    assert rows == [("alpha",), ("beta",)]
