#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests for the RustChain attestation exporter."""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rustchain_export as exporter


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_json(self, path, params=None):
        self.calls.append((path, params or {}))
        if path == "/api/miners":
            return {
                "miners": [
                    {
                        "miner": "alice",
                        "device_arch": "G4",
                        "device_family": "PowerPC",
                        "hardware_type": "PowerPC G4",
                        "antiquity_multiplier": 2.5,
                        "first_attest": 1780000000,
                        "last_attest": 1780003600,
                    }
                ]
            }
        if path == "/epoch":
            return {"epoch": 179, "slot": 25844, "epoch_pot": 1.5, "enrolled_miners": 1}
        if path == "/rewards/epoch/179":
            return {
                "epoch": 179,
                "timestamp": 1780007200,
                "total_pot": 1.5,
                "total_distributed": 1.5,
                "miner_count": 1,
                "settlement_hash": "abc",
                "rewards": {"alice": 1.5},
            }
        if path == "/wallet/balance":
            return {"ok": True, "miner_id": params["miner_id"], "amount_rtc": 12.5}
        if path == "/wallet/history":
            return {
                "ok": True,
                "miner_id": params["miner_id"],
                "transactions": [
                    {
                        "tx_hash": "tx1",
                        "amount": 2.0,
                        "status": "pending",
                        "timestamp": 1780007300,
                    }
                ],
            }
        raise AssertionError(path)


class ExporterTests(unittest.TestCase):
    def test_parse_date_accepts_calendar_day(self):
        self.assertEqual(exporter.parse_date("2026-05-31"), 1780185600)
        self.assertEqual(exporter.parse_date("2026-05-31", end_of_day=True), 1780271999)

    def test_api_export_builds_required_tables(self):
        tables = exporter.export_from_api(
            FakeClient(),
            date_window=exporter.DateWindow(),
            reward_epochs=[179],
        )

        self.assertEqual(len(tables["miners"]), 1)
        self.assertEqual(len(tables["attestations"]), 1)
        self.assertEqual(tables["epochs"][0]["timestamp"], 1780007200)
        self.assertEqual(tables["balances"][0]["amount_rtc"], 12.5)
        self.assertTrue(any(row.get("miner_id") == "alice" for row in tables["rewards"]))
        self.assertTrue(any(row.get("tx_hash") == "tx1" for row in tables["rewards"]))

    def test_write_csv_escapes_nested_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "miners.csv"
            exporter.write_csv(path, [{"miner": "alice", "meta": {"arch": "G4"}}])
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["miner"], "alice")
            self.assertEqual(json.loads(rows[0]["meta"]), {"arch": "G4"})

    def test_sqlite_export_reads_core_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "rustchain.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE miner_attest_recent (miner_id TEXT, last_attest INTEGER)")
                conn.execute("CREATE TABLE balances (miner_id TEXT, amount_rtc REAL)")
                conn.execute("CREATE TABLE epoch_state (epoch INTEGER, timestamp INTEGER)")
                conn.execute("CREATE TABLE epoch_rewards (epoch INTEGER, miner_id TEXT, amount_rtc REAL)")
                conn.execute("CREATE TABLE ledger (tx_hash TEXT, amount_rtc REAL, created_at INTEGER)")
                conn.execute(
                    "INSERT INTO miner_attest_recent VALUES (?, ?)",
                    ("alice", 1780003600),
                )
                conn.execute("INSERT INTO balances VALUES (?, ?)", ("alice", 1.25))
                conn.execute("INSERT INTO epoch_state VALUES (?, ?)", (179, 1780007200))
                conn.execute("INSERT INTO epoch_rewards VALUES (?, ?, ?)", (179, "alice", 1.5))
                conn.execute("INSERT INTO ledger VALUES (?, ?, ?)", ("tx1", 2.0, 1780007300))

            tables = exporter.export_from_sqlite(str(db_path), date_window=exporter.DateWindow())

        self.assertEqual(tables["miners"][0]["miner_id"], "alice")
        self.assertEqual(tables["balances"][0]["amount_rtc"], 1.25)
        self.assertTrue(any(row.get("tx_hash") == "tx1" for row in tables["rewards"]))


if __name__ == "__main__":
    unittest.main()
