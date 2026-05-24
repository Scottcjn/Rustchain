#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Opt-in SQLite state pruning for RustChain node operators.

This intentionally prunes only historical rows that are not part of the current
spendable UTXO set. Blocks, balances, unspent boxes, and epoch state are left
untouched so the tool can be used as a conservative first pruning slice.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

SPENT_UTXO_ARCHIVE_SCHEMA = """
CREATE TABLE IF NOT EXISTS archive_utxo_boxes (
    box_id TEXT PRIMARY KEY,
    value_nrtc INTEGER NOT NULL,
    proposition TEXT NOT NULL,
    owner_address TEXT NOT NULL,
    creation_height INTEGER NOT NULL,
    transaction_id TEXT NOT NULL,
    output_index INTEGER NOT NULL,
    tokens_json TEXT DEFAULT '[]',
    registers_json TEXT DEFAULT '{}',
    created_at INTEGER NOT NULL,
    spent_at INTEGER,
    spent_by_tx TEXT,
    archived_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
)
"""


@dataclass(frozen=True)
class PruneResult:
    dry_run: bool
    archive: bool
    current_height: int
    retain_blocks: int
    prune_before_height: int
    spent_utxo_rows: int
    expired_mempool_rows: int


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _require_columns(conn: sqlite3.Connection, table: str, required: Iterable[str]) -> bool:
    return _table_exists(conn, table) and set(required).issubset(_columns(conn, table))


def _current_height(conn: sqlite3.Connection) -> int:
    if not _require_columns(conn, "blocks", ["height"]):
        return 0
    row = conn.execute("SELECT COALESCE(MAX(height), 0) FROM blocks").fetchone()
    return int(row[0] or 0)


UTXO_BOX_COLUMNS = [
    "box_id",
    "value_nrtc",
    "proposition",
    "owner_address",
    "creation_height",
    "transaction_id",
    "output_index",
    "tokens_json",
    "registers_json",
    "created_at",
    "spent_at",
    "spent_by_tx",
]


def _count_spent_utxos(conn: sqlite3.Connection, prune_before_height: int) -> int:
    if not _require_columns(conn, "utxo_boxes", UTXO_BOX_COLUMNS):
        return 0
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM utxo_boxes
        WHERE spent_at IS NOT NULL
          AND creation_height < ?
        """,
        (prune_before_height,),
    ).fetchone()
    return int(row[0] or 0)


def _archive_spent_utxos(conn: sqlite3.Connection, prune_before_height: int) -> None:
    conn.execute(SPENT_UTXO_ARCHIVE_SCHEMA)
    conn.execute(
        """
        INSERT OR IGNORE INTO archive_utxo_boxes (
            box_id, value_nrtc, proposition, owner_address, creation_height,
            transaction_id, output_index, tokens_json, registers_json, created_at,
            spent_at, spent_by_tx
        )
        SELECT
            box_id, value_nrtc, proposition, owner_address, creation_height,
            transaction_id, output_index, tokens_json, registers_json, created_at,
            spent_at, spent_by_tx
        FROM utxo_boxes
        WHERE spent_at IS NOT NULL
          AND creation_height < ?
        """,
        (prune_before_height,),
    )


def _delete_spent_utxos(conn: sqlite3.Connection, prune_before_height: int) -> None:
    conn.execute(
        """
        DELETE FROM utxo_boxes
        WHERE spent_at IS NOT NULL
          AND creation_height < ?
        """,
        (prune_before_height,),
    )


def _count_expired_mempool(conn: sqlite3.Connection) -> int:
    if not _require_columns(conn, "utxo_mempool", ["tx_id", "expires_at"]):
        return 0
    row = conn.execute(
        "SELECT COUNT(*) FROM utxo_mempool WHERE expires_at < strftime('%s', 'now')"
    ).fetchone()
    return int(row[0] or 0)


def _delete_expired_mempool(conn: sqlite3.Connection) -> None:
    if not _require_columns(conn, "utxo_mempool", ["tx_id", "expires_at"]):
        return
    if _require_columns(conn, "utxo_mempool_inputs", ["tx_id"]):
        conn.execute(
            """
            DELETE FROM utxo_mempool_inputs
            WHERE tx_id IN (
                SELECT tx_id FROM utxo_mempool WHERE expires_at < strftime('%s', 'now')
            )
            """
        )
    conn.execute("DELETE FROM utxo_mempool WHERE expires_at < strftime('%s', 'now')")


def prune_state(
    db_path: str,
    retain_blocks: int,
    *,
    dry_run: bool = True,
    archive: bool = False,
) -> PruneResult:
    if retain_blocks < 0:
        raise ValueError("retain_blocks must be non-negative")

    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(db_path)

    with sqlite3.connect(path) as conn:
        height = _current_height(conn)
        prune_before_height = max(0, height - retain_blocks)
        spent_utxo_rows = _count_spent_utxos(conn, prune_before_height)
        expired_mempool_rows = _count_expired_mempool(conn)

        if not dry_run:
            with conn:
                if archive and spent_utxo_rows:
                    _archive_spent_utxos(conn, prune_before_height)
                if spent_utxo_rows:
                    _delete_spent_utxos(conn, prune_before_height)
                if expired_mempool_rows:
                    _delete_expired_mempool(conn)

        return PruneResult(
            dry_run=dry_run,
            archive=archive,
            current_height=height,
            retain_blocks=retain_blocks,
            prune_before_height=prune_before_height,
            spent_utxo_rows=spent_utxo_rows,
            expired_mempool_rows=expired_mempool_rows,
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prune historical RustChain SQLite state")
    parser.add_argument("--db", required=True, help="Path to rustchain_v2.db")
    parser.add_argument(
        "--retain-blocks",
        type=int,
        default=100_000,
        help="Keep spent UTXO history created in the most recent N blocks",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply pruning. Omit for dry-run mode.",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Copy pruned spent UTXOs into archive_utxo_boxes before deleting them.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        result = prune_state(
            args.db,
            args.retain_blocks,
            dry_run=not args.apply,
            archive=args.archive,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
