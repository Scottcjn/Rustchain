# SPDX-License-Identifier: MIT

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rom_clustering_server import ROMClusteringServer, init_rom_tables


def test_rom_cluster_upsert_keeps_one_row_per_rom_hash(tmp_path):
    db_path = str(tmp_path / "roms.db")
    server = ROMClusteringServer(db_path, cluster_threshold=1)
    rom_hash = "ab" * 20

    assert server.process_rom_report("miner-1", rom_hash)[1] == "unique_rom"
    assert server.process_rom_report("miner-2", rom_hash)[1] == "rom_clustering"
    assert server.process_rom_report("miner-3", rom_hash)[1] == "rom_clustering"

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT cluster_id, cluster_size, miners FROM rom_clusters WHERE rom_hash = ?",
            (rom_hash,),
        ).fetchall()

    assert len(rows) == 1
    assert rows[0][1] == 3


def test_init_rom_tables_deduplicates_legacy_cluster_rows_before_unique_index(tmp_path):
    db_path = str(tmp_path / "legacy-roms.db")
    rom_hash = "cd" * 20
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE miner_rom_reports (
                miner_id TEXT NOT NULL,
                rom_hash TEXT NOT NULL,
                hash_type TEXT NOT NULL,
                platform TEXT,
                first_seen INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                report_count INTEGER DEFAULT 1,
                PRIMARY KEY (miner_id, rom_hash)
            );
            CREATE TABLE rom_clusters (
                cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
                rom_hash TEXT NOT NULL,
                hash_type TEXT NOT NULL,
                miners TEXT NOT NULL,
                cluster_size INTEGER NOT NULL,
                is_known_emulator_rom INTEGER DEFAULT 0,
                known_rom_info TEXT,
                first_detected INTEGER NOT NULL,
                last_updated INTEGER NOT NULL
            );
            CREATE TABLE miner_rom_flags (
                miner_id TEXT PRIMARY KEY,
                flag_reason TEXT NOT NULL,
                cluster_id INTEGER,
                flagged_at INTEGER NOT NULL,
                resolved INTEGER DEFAULT 0,
                resolved_at INTEGER
            );
        """)
        conn.execute(
            "INSERT INTO rom_clusters VALUES (1, ?, 'sha1', '[\"miner-1\", \"miner-2\"]', 2, 0, NULL, 10, 20)",
            (rom_hash,),
        )
        conn.execute(
            "INSERT INTO rom_clusters VALUES (2, ?, 'sha1', '[\"miner-1\", \"miner-2\", \"miner-3\"]', 3, 0, NULL, 11, 30)",
            (rom_hash,),
        )
        conn.execute(
            "INSERT INTO miner_rom_flags VALUES ('miner-3', 'rom_cluster:3_miners', 2, 30, 0, NULL)"
        )

    init_rom_tables(db_path)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT cluster_id, cluster_size, first_detected, last_updated FROM rom_clusters WHERE rom_hash = ?",
            (rom_hash,),
        ).fetchall()
        index_rows = conn.execute("PRAGMA index_list(rom_clusters)").fetchall()
        flag_cluster_id = conn.execute(
            "SELECT cluster_id FROM miner_rom_flags WHERE miner_id = 'miner-3'"
        ).fetchone()[0]

    assert len(rows) == 1
    assert rows[0][1:] == (3, 10, 30)
    assert flag_cluster_id == rows[0][0]
    assert any(row[2] for row in index_rows if row[1] == "idx_rom_clusters_hash_type")
