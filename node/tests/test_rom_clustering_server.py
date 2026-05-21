# SPDX-License-Identifier: MIT

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rom_clustering_server import (
    ROMClusteringServer,
    init_rom_tables,
    integrate_with_attestation,
)


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
            "SELECT cluster_id, cluster_size, miners, first_detected, last_updated FROM rom_clusters WHERE rom_hash = ?",
            (rom_hash,),
        ).fetchall()
        index_rows = conn.execute("PRAGMA index_list(rom_clusters)").fetchall()
        flag_cluster_id = conn.execute(
            "SELECT cluster_id FROM miner_rom_flags WHERE miner_id = 'miner-3'"
        ).fetchone()[0]

    assert len(rows) == 1
    assert rows[0][1] == 3
    assert json.loads(rows[0][2]) == ["miner-1", "miner-2", "miner-3"]
    assert rows[0][3:] == (10, 30)
    assert flag_cluster_id == rows[0][0]
    assert any(row[2] for row in index_rows if row[1] == "idx_rom_clusters_hash_type")


def test_init_rom_tables_merges_partial_legacy_duplicate_cluster_miners(tmp_path):
    db_path = str(tmp_path / "partial-legacy-roms.db")
    rom_hash = "ef" * 20
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
            "INSERT INTO rom_clusters VALUES (1, ?, 'sha1', '[\"miner-a\", \"miner-b\"]', 2, 0, NULL, 10, 30)",
            (rom_hash,),
        )
        conn.execute(
            "INSERT INTO rom_clusters VALUES (2, ?, 'sha1', '[\"miner-b\", \"miner-c\"]', 2, 0, NULL, 11, 20)",
            (rom_hash,),
        )
        conn.execute(
            "INSERT INTO miner_rom_flags VALUES ('miner-c', 'rom_cluster:2_miners', 2, 20, 0, NULL)"
        )

    init_rom_tables(db_path)

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT cluster_id, cluster_size, miners, first_detected, last_updated FROM rom_clusters WHERE rom_hash = ?",
            (rom_hash,),
        ).fetchone()
        flag_cluster_id = conn.execute(
            "SELECT cluster_id FROM miner_rom_flags WHERE miner_id = 'miner-c'"
        ).fetchone()[0]

    assert row[1] == 3
    assert json.loads(row[2]) == ["miner-a", "miner-b", "miner-c"]
    assert row[3:] == (10, 30)
    assert flag_cluster_id == row[0]


def test_process_rom_report_rejects_non_string_rom_hash(tmp_path):
    db_path = str(tmp_path / "roms.db")
    server = ROMClusteringServer(db_path)

    result = server.process_rom_report("miner-1", {"hash": "ab" * 20})

    assert result == (False, "invalid_rom_report", {"field": "rom_hash"})


def test_integrate_with_attestation_rejects_malformed_fingerprint_shapes(tmp_path):
    db_path = str(tmp_path / "roms.db")
    server = ROMClusteringServer(db_path)

    assert integrate_with_attestation(
        {"miner_id": "miner-1", "fingerprint": []},
        server,
    ) == (False, "invalid_fingerprint")
    assert integrate_with_attestation(
        {"miner_id": "miner-1", "fingerprint": {"checks": []}},
        server,
    ) == (False, "invalid_fingerprint_checks")
    assert integrate_with_attestation(
        {"miner_id": "miner-1", "fingerprint": {"checks": {"rom_fingerprint": []}}},
        server,
    ) == (False, "invalid_rom_fingerprint")
    assert integrate_with_attestation(
        {
            "miner_id": "miner-1",
            "fingerprint": {
                "checks": {
                    "rom_fingerprint": {
                        "data": {"rom_hashes": []},
                    },
                },
            },
        },
        server,
    ) == (False, "invalid_rom_hashes")
