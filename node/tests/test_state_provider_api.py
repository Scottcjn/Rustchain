# SPDX-License-Identifier: MIT

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rustchain_sync import (
    FallbackStateProvider,
    InMemoryStateProvider,
    RustChainSyncManager,
    SQLiteStateProvider,
)


def test_sync_manager_accepts_injected_state_provider():
    provider = InMemoryStateProvider(
        tables={
            "miner_attest_recent": [
                {"miner_id": "miner-a", "last_attest": 10},
            ],
        },
        primary_keys={"miner_attest_recent": "miner_id"},
    )
    sync = RustChainSyncManager(":memory:", "sync-secret", state_provider=provider)

    assert sync.SYNC_TABLES == ["miner_attest_recent"]
    assert sync.get_table_data("miner_attest_recent") == [
        {"miner_id": "miner-a", "last_attest": 10},
    ]
    assert sync.get_sync_status()["tables"]["miner_attest_recent"]["count"] == 1


def test_fallback_state_provider_uses_secondary_when_primary_fails():
    class BrokenProvider:
        def get_available_sync_tables(self):
            raise RuntimeError("primary unavailable")

        def calculate_table_hash(self, table_name):
            raise RuntimeError("primary unavailable")

        def get_merkle_root(self):
            raise RuntimeError("primary unavailable")

        def get_primary_key(self, table_name):
            raise RuntimeError("primary unavailable")

        def get_table_data(self, table_name, limit=200, offset=0):
            raise RuntimeError("primary unavailable")

        def apply_sync_payload(self, table_name, remote_data):
            raise RuntimeError("primary unavailable")

        def get_count(self, table_name):
            raise RuntimeError("primary unavailable")

    secondary = InMemoryStateProvider(
        tables={"epoch_rewards": [{"epoch": 7, "reward": 100}]},
        primary_keys={"epoch_rewards": "epoch"},
    )
    provider = FallbackStateProvider([BrokenProvider(), secondary])

    assert provider.get_available_sync_tables() == ["epoch_rewards"]
    assert provider.get_primary_key("epoch_rewards") == "epoch"
    assert provider.get_table_data("epoch_rewards") == [
        {"epoch": 7, "reward": 100},
    ]
    assert provider.get_count("epoch_rewards") == 1


def test_default_sqlite_provider_preserves_existing_sync_behavior(tmp_path):
    db_path = tmp_path / "rustchain.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE miner_attest_recent (
                miner_id TEXT PRIMARY KEY,
                last_attest INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO miner_attest_recent (miner_id, last_attest) VALUES (?, ?)",
            ("miner-a", 10),
        )
        conn.commit()

    sync = RustChainSyncManager(str(db_path), "sync-secret")

    assert isinstance(sync.state_provider, SQLiteStateProvider)
    assert sync.get_available_sync_tables() == ["miner_attest_recent"]
    assert sync.get_table_data("miner_attest_recent") == [
        {"miner_id": "miner-a", "last_attest": 10},
    ]

    assert sync.apply_sync_payload(
        "miner_attest_recent",
        [{"miner_id": "miner-a", "last_attest": 5}],
    )
    assert sync.get_table_data("miner_attest_recent") == [
        {"miner_id": "miner-a", "last_attest": 10},
    ]

    assert sync.apply_sync_payload(
        "miner_attest_recent",
        [{"miner_id": "miner-a", "last_attest": 12}],
    )
    assert sync.get_table_data("miner_attest_recent") == [
        {"miner_id": "miner-a", "last_attest": 12},
    ]
