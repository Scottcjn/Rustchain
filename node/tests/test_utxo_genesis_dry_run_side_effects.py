# SPDX-License-Identifier: Apache-2.0
"""Regression proof for rustchain-bounties #2819 dry-run side effects."""

import sqlite3
import sys
from pathlib import Path

NODE_DIR = Path(__file__).resolve().parents[1]
if str(NODE_DIR) not in sys.path:
    sys.path.insert(0, str(NODE_DIR))

from utxo_genesis_migration import migrate


def _make_balance_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL)"
        )
        conn.executemany(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            [
                ("RTCaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 1_000_000),
                ("RTCbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", 2_500_000),
            ],
        )
        conn.commit()


def _schema_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type IN ('table', 'index') AND name NOT LIKE 'sqlite_%'"
            )
        }


def test_genesis_dry_run_does_not_mutate_target_database_schema(tmp_path):
    """`--dry-run` must preview migration without creating UTXO schema objects."""
    db_path = tmp_path / "rustchain-dry-run.db"
    _make_balance_db(db_path)

    before = _schema_names(db_path)
    assert before == {"balances"}

    result = migrate(str(db_path), dry_run=True)
    assert "error" not in result

    after = _schema_names(db_path)

    # Current main fails here because migrate(..., dry_run=True) calls
    # UtxoDB.init_tables() against the real target database before previewing.
    assert after == before


def test_genesis_dry_run_reports_the_prospective_state_root(tmp_path):
    """Preview root must equal the corresponding real migration root."""
    preview_db = tmp_path / "preview.db"
    real_db = tmp_path / "real.db"
    _make_balance_db(preview_db)
    _make_balance_db(real_db)

    preview = migrate(str(preview_db), dry_run=True)
    real = migrate(str(real_db), dry_run=False)

    assert "error" not in preview
    assert "error" not in real
    assert preview["state_root"] == real["state_root"]
    assert _schema_names(preview_db) == {"balances"}
