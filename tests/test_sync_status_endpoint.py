# SPDX-License-Identifier: MIT
"""
Tests for node sync status and monitoring health endpoints (fixes #8507).
Validates /health/sync and /api/sync-status return canonical json payloads for Prometheus/Datadog.
"""

import sys
import sqlite3
from pathlib import Path
import pytest

# Ensure node imports work
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "node"))


def test_sync_status_endpoints(tmp_path):
    node = sys.modules.get("integrated_node")
    if not node:
        import tests.conftest as conftest
        node = conftest.load_node_module("integrated_node", "rustchain_v2_integrated_v2.2.1_rip200.py")

    test_db = str(tmp_path / "node_sync.db")
    orig_db = node.DB_PATH
    node.DB_PATH = test_db

    try:
        client = node.app.test_client()

        # 1. Test /health/sync on empty / uninitialized node
        resp1 = client.get("/health/sync")
        assert resp1.status_code == 200
        data1 = resp1.get_json()
        assert "is_synced" in data1
        assert "current_block" in data1
        assert "network_block" in data1
        assert data1["current_block"] == 0
        assert data1["is_synced"] is False

        # 2. Test /api/sync-status alias
        resp2 = client.get("/api/sync-status")
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert data2["is_synced"] == data1["is_synced"]
        assert data2["current_block"] == data1["current_block"]
        assert data2["network_block"] == data1["network_block"]

        # 3. Test when headers table is present and synchronized
        current_net = node.current_slot()
        with sqlite3.connect(test_db, timeout=3) as db:
            db.execute("CREATE TABLE IF NOT EXISTS headers (slot INTEGER PRIMARY KEY, hash TEXT)")
            db.execute("INSERT OR REPLACE INTO headers (slot, hash) VALUES (?, ?)", (current_net, "0x" + "a" * 64))

        resp3 = client.get("/health/sync")
        assert resp3.status_code == 200
        data3 = resp3.get_json()
        assert data3["current_block"] == current_net
        assert data3["is_synced"] is True
        assert data3["lag_slots"] == 0
    finally:
        node.DB_PATH = orig_db
