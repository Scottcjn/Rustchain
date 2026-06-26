import csv
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rustchain_export as exporter


def make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE miner_attest_recent (
            miner TEXT PRIMARY KEY,
            device_family TEXT,
            device_arch TEXT,
            hardware_type TEXT,
            ts_ok INTEGER,
            entropy_score REAL,
            warthog_bonus REAL
        );
        CREATE TABLE balances (
            miner_id TEXT PRIMARY KEY,
            amount_i64 INTEGER DEFAULT 0
        );
        CREATE TABLE epoch_state (
            epoch INTEGER PRIMARY KEY,
            settled INTEGER DEFAULT 0,
            settled_ts INTEGER
        );
        CREATE TABLE epoch_rewards (
            epoch INTEGER,
            miner_id TEXT,
            share_i64 INTEGER
        );
        CREATE TABLE ledger (
            ts INTEGER,
            epoch INTEGER,
            miner_id TEXT,
            delta_i64 INTEGER,
            reason TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("aliceRTC", "PowerPC", "G4", "PowerPC G4", 1770112912, 0.5, 2.5),
    )
    conn.execute(
        "INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("oldRTC", "x86", "x86_64", "PC", 1600000000, 0.1, 1.0),
    )
    conn.execute("INSERT INTO balances VALUES (?, ?)", ("aliceRTC", 1250000))
    conn.execute("INSERT INTO balances VALUES (?, ?)", ("bobRTC", 500000))
    conn.execute("INSERT INTO balances VALUES (?, ?)", ("carolRTC", 999999))
    conn.execute("INSERT INTO epoch_state VALUES (?, ?, ?)", (62, 1, 1770113000))
    conn.execute("INSERT INTO epoch_rewards VALUES (?, ?, ?)", (62, "aliceRTC", 1250000))
    conn.execute("INSERT INTO ledger VALUES (?, ?, ?, ?, ?)", (1770113000, 62, "aliceRTC", 1250000, "reward"))
    conn.commit()
    conn.close()


class RustChainExportTests(unittest.TestCase):
    def test_db_export_writes_csv_with_date_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "rustchain.sqlite"
            out_dir = tmp_path / "out"
            make_db(db_path)

            rc = exporter.main(
                [
                    "--mode",
                    "db",
                    "--db",
                    str(db_path),
                    "--format",
                    "csv",
                    "--output",
                    str(out_dir),
                    "--from",
                    "2026-02-01",
                ]
            )

            self.assertEqual(rc, 0)
            with (out_dir / "miners.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["miner_id"] for row in rows], ["aliceRTC"])

            with (out_dir / "balances.csv").open(newline="", encoding="utf-8") as handle:
                balances = list(csv.DictReader(handle))
            self.assertEqual(
                {row["miner_id"]: row["amount_rtc"] for row in balances},
                {
                    "aliceRTC": "1.25",
                    "bobRTC": "0.5",
                    "carolRTC": "0.999999",
                },
            )

            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))[0]
            self.assertEqual(manifest["tables"]["miners"], 1)
            self.assertEqual(manifest["format"], "csv")

    def test_api_export_uses_public_endpoints(self):
        calls = []

        def fake_fetch(node_url, endpoint, timeout, insecure):
            calls.append(endpoint)
            if endpoint == "/api/miners":
                return [
                    {
                        "miner": "aliceRTC",
                        "device_family": "PowerPC",
                        "device_arch": "G4",
                        "hardware_type": "PowerPC G4",
                        "antiquity_multiplier": 2.5,
                        "entropy_score": 0.5,
                        "last_attest": 1770112912,
                    }
                ]
            if endpoint.startswith("/wallet/balance"):
                return {"amount_rtc": 3.5}
            if endpoint == "/epoch":
                return {"epoch": 62, "slot": 9010, "epoch_pot": 1.5, "enrolled_miners": 1, "blocks_per_epoch": 144}
            raise AssertionError(endpoint)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(exporter, "fetch_json", fake_fetch):
            out_dir = Path(tmp) / "api"
            rc = exporter.main(["--mode", "api", "--format", "jsonl", "--output", str(out_dir)])

            self.assertEqual(rc, 0)
            self.assertIn("/api/miners", calls)
            self.assertIn("/epoch", calls)
            rows = [json.loads(line) for line in (out_dir / "miners.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["miner_id"], "aliceRTC")
            self.assertEqual(rows[0]["total_earnings_rtc"], 3.5)

    def test_empty_csv_still_has_header_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.csv"
            exporter.write_csv(path, [], ["col1", "col2"])
            self.assertEqual(path.read_text(encoding="utf-8").strip(), "col1,col2")

    def test_balance_amount_normalizes_micro_columns_by_source(self):
        self.assertEqual(exporter.balance_amount_rtc({"amount_i64": 1}), 0.000001)
        self.assertEqual(exporter.balance_amount_rtc({"amount_i64": 500_000}), 0.5)
        self.assertEqual(exporter.balance_amount_rtc({"balance_urtc": 999_999}), 0.999999)
        self.assertEqual(exporter.balance_amount_rtc({"balance_rtc": 0.5}), 0.5)

    def test_csv_export_neutralizes_formula_injection(self):
        rows = [
            {
                "miner_id": "=cmd|'/c calc'!A0",
                "device_arch": "+SUM(A1:A2)",
                "hardware_type": "-2+3",
                "reason": "@SUM(1)",
                "tabbed": "\tlead",
                "safe": "PowerPC G4",
                "amount": 1.25,
                "none_field": None,
                "empty_field": "",
                "already_quoted": "'safe",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "rows.csv"
            exporter.write_csv(csv_path, rows)
            with csv_path.open(newline="", encoding="utf-8") as handle:
                out = list(csv.DictReader(handle))[0]
            self.assertEqual(out["miner_id"], "'=cmd|'/c calc'!A0")
            self.assertEqual(out["device_arch"], "'+SUM(A1:A2)")
            self.assertEqual(out["hardware_type"], "'-2+3")
            self.assertEqual(out["reason"], "'@SUM(1)")
            self.assertEqual(out["tabbed"], "'\tlead")
            self.assertEqual(out["safe"], "PowerPC G4")
            self.assertEqual(out["amount"], "1.25")
            self.assertEqual(out["none_field"], "")
            self.assertEqual(out["empty_field"], "")
            self.assertEqual(out["already_quoted"], "'safe")

            json_path = Path(tmp) / "rows.json"
            exporter.write_json(json_path, rows)
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded[0]["miner_id"], "=cmd|'/c calc'!A0")
            self.assertEqual(loaded[0]["device_arch"], "+SUM(A1:A2)")


if __name__ == "__main__":
    unittest.main()
