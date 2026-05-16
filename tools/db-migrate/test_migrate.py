import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "migrate.py"
SPEC = importlib.util.spec_from_file_location("db_migrate", MODULE_PATH)
db_migrate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(db_migrate)


def test_parse_migration_accepts_case_and_whitespace_markers(tmp_path):
    migration_file = tmp_path / "V0001__case_whitespace.sql"
    migration_file.write_text(
        """
        -- migration metadata

          --   up

        CREATE TABLE miners (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

          --   down

        DROP TABLE miners;
        """,
        encoding="utf-8",
    )

    up_sql, down_sql = db_migrate._parse_migration(str(migration_file))

    assert up_sql == (
        "CREATE TABLE miners (\n"
        "            id INTEGER PRIMARY KEY,\n"
        "            name TEXT NOT NULL\n"
        "        );"
    )
    assert down_sql == "DROP TABLE miners;"


def test_parse_migration_allows_missing_down_block(tmp_path):
    migration_file = tmp_path / "V0002__up_only.sql"
    migration_file.write_text(
        """
        -- UP

        CREATE INDEX idx_miners_name ON miners(name);
        """,
        encoding="utf-8",
    )

    up_sql, down_sql = db_migrate._parse_migration(str(migration_file))

    assert up_sql == "CREATE INDEX idx_miners_name ON miners(name);"
    assert down_sql == ""
