# SPDX-License-Identifier: MIT
import sqlite3
import time

from node.state_pruning import SPENT_UTXO_ARCHIVE_SCHEMA, prune_state


def _seed_db(path):
    now = int(time.time())
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE blocks (height INTEGER PRIMARY KEY);
            CREATE TABLE utxo_boxes (
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
                spent_by_tx TEXT
            );
            CREATE TABLE utxo_mempool (
                tx_id TEXT PRIMARY KEY,
                tx_data_json TEXT NOT NULL,
                fee_nrtc INTEGER DEFAULT 0,
                submitted_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE utxo_mempool_inputs (
                box_id TEXT NOT NULL PRIMARY KEY,
                tx_id TEXT NOT NULL
            );
            """
        )
        conn.executemany("INSERT INTO blocks(height) VALUES (?)", [(1,), (50,), (120,)])
        conn.executemany(
            """
            INSERT INTO utxo_boxes (
                box_id, value_nrtc, proposition, owner_address, creation_height,
                transaction_id, output_index, tokens_json, registers_json, created_at,
                spent_at, spent_by_tx
            )
            VALUES (?, 1, '00', 'alice', ?, ?, 0, '[]', '{}', ?, ?, ?)
            """,
            [
                ("old-spent", 10, "tx-old", now - 100, now - 50, "spend-old"),
                ("recent-spent", 115, "tx-recent", now - 90, now - 10, "spend-recent"),
                ("old-unspent", 5, "tx-live", now - 80, None, None),
            ],
        )
        conn.executemany(
            "INSERT INTO utxo_mempool(tx_id, tx_data_json, submitted_at, expires_at) VALUES (?, '{}', ?, ?)",
            [
                ("expired", now - 100, now - 1),
                ("active", now, now + 1000),
            ],
        )
        conn.executemany(
            "INSERT INTO utxo_mempool_inputs(box_id, tx_id) VALUES (?, ?)",
            [("expired-input", "expired"), ("active-input", "active")],
        )


def test_state_pruning_dry_run_does_not_delete_rows(tmp_path):
    db_path = tmp_path / "rustchain.db"
    _seed_db(db_path)

    result = prune_state(str(db_path), retain_blocks=100, dry_run=True, archive=True)

    assert result.current_height == 120
    assert result.prune_before_height == 20
    assert result.spent_utxo_rows == 1
    assert result.expired_mempool_rows == 1
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM utxo_boxes").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM utxo_mempool").fetchone()[0] == 2


def test_state_pruning_archives_only_old_spent_utxos_and_keeps_current_state(tmp_path):
    db_path = tmp_path / "rustchain.db"
    _seed_db(db_path)

    result = prune_state(str(db_path), retain_blocks=100, dry_run=False, archive=True)

    assert result.spent_utxo_rows == 1
    with sqlite3.connect(db_path) as conn:
        boxes = {
            row[0]: row[1]
            for row in conn.execute("SELECT box_id, spent_at FROM utxo_boxes ORDER BY box_id")
        }
        assert boxes == {"old-unspent": None, "recent-spent": boxes["recent-spent"]}
        assert boxes["recent-spent"] is not None
        archived = conn.execute("SELECT box_id FROM archive_utxo_boxes").fetchall()
        assert archived == [("old-spent",)]


def test_state_pruning_refreshes_existing_archive_row_before_delete(tmp_path):
    db_path = tmp_path / "rustchain.db"
    _seed_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(SPENT_UTXO_ARCHIVE_SCHEMA)
        conn.execute(
            """
            INSERT INTO archive_utxo_boxes (
                box_id, value_nrtc, proposition, owner_address, creation_height,
                transaction_id, output_index, tokens_json, registers_json, created_at,
                spent_at, spent_by_tx
            )
            VALUES ('old-spent', 999, 'stale', 'stale-owner', 0, 'stale-tx', 99, '["stale"]', '{"stale": true}', 1, 2, 'stale-spend')
            """
        )

    prune_state(str(db_path), retain_blocks=100, dry_run=False, archive=True)

    with sqlite3.connect(db_path) as conn:
        archived = conn.execute(
            """
            SELECT value_nrtc, proposition, owner_address, creation_height,
                   transaction_id, output_index, tokens_json, registers_json,
                   spent_by_tx
            FROM archive_utxo_boxes
            WHERE box_id = 'old-spent'
            """
        ).fetchone()
        assert archived == (1, "00", "alice", 10, "tx-old", 0, "[]", "{}", "spend-old")
        assert conn.execute("SELECT COUNT(*) FROM utxo_boxes WHERE box_id = 'old-spent'").fetchone()[0] == 0


def test_state_pruning_enables_foreign_key_enforcement_on_prune_connection(tmp_path, monkeypatch):
    db_path = tmp_path / "rustchain.db"
    _seed_db(db_path)
    real_connect = sqlite3.connect
    pragma_calls = []

    class TrackingConnection:
        def __init__(self, inner):
            self._inner = inner

        def __enter__(self):
            self._inner.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            return self._inner.__exit__(exc_type, exc, tb)

        def execute(self, sql, *args, **kwargs):
            if str(sql).strip().upper() == "PRAGMA FOREIGN_KEYS=ON":
                pragma_calls.append(sql)
            return self._inner.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    def tracking_connect(*args, **kwargs):
        return TrackingConnection(real_connect(*args, **kwargs))

    monkeypatch.setattr("node.state_pruning.sqlite3.connect", tracking_connect)

    prune_state(str(db_path), retain_blocks=100, dry_run=True)

    assert pragma_calls == ["PRAGMA foreign_keys=ON"]


def test_state_pruning_removes_expired_mempool_inputs_with_parent(tmp_path):
    db_path = tmp_path / "rustchain.db"
    _seed_db(db_path)

    prune_state(str(db_path), retain_blocks=100, dry_run=False)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT tx_id FROM utxo_mempool").fetchall() == [("active",)]
        assert conn.execute("SELECT tx_id FROM utxo_mempool_inputs").fetchall() == [("active",)]
