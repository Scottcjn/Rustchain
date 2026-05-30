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
            self.assertEqual(balances[0]["amount_rtc"], "1.25")

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
            exporter.write_csv(path, [])
            self.assertEqual(path.read_text(encoding="utf-8").strip(), "")


if __name__ == "__main__":
    unittest.main()
