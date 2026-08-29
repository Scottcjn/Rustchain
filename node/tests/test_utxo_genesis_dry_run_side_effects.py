# SPDX-License-Identifier: Apache-2.0
"""Regression proof for rustchain-bounties #2819 dry-run side effects."""

import sqlite3
import sys
from pathlib import Path

NODE_DIR = Path(__file__).resolve().parents[1]
if str(NODE_DIR) not in sys.path:
    sys.path.insert(0, str(NODE_DIR))

from utxo_genesis_migration import migrate


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
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL)"
        )
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("RTCaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 1_000_000),
        )
        conn.commit()

    before = _schema_names(db_path)
    assert before == {"balances"}

    result = migrate(str(db_path), dry_run=True)
    assert "error" not in result

    after = _schema_names(db_path)

    # Current main fails here because migrate(..., dry_run=True) calls
    # UtxoDB.init_tables() against the real target database before previewing.
    assert after == before
