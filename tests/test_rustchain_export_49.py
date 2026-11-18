#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for RustChain Attestation Data Export Pipeline (#49, #1113, #8359)."""

import csv
import hashlib
import importlib.util
import json
import pathlib
import sqlite3
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "tools" / "rustchain_export.py"


def _load_export_mod():
    spec = importlib.util.spec_from_file_location("rustchain_export_49", EXPORT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RustChainExportPipeline49Test(unittest.TestCase):
    def setUp(self):
        self.mod = _load_export_mod()
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = pathlib.Path(self.tmp.name)
        self.db_path = self.tmp_path / "rustchain_v2.db"
        self._seed_sqlite_db(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def _seed_sqlite_db(self, db_path: pathlib.Path):
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE balances (miner_id TEXT, amount_rtc REAL, updated_at TEXT)")
        conn.execute("CREATE TABLE epoch_rewards (epoch INTEGER, miner_id TEXT, amount_rtc REAL, timestamp TEXT)")
        conn.execute("CREATE TABLE miner_attest_recent (miner_id TEXT, timestamp TEXT, arch TEXT, device_info TEXT)")
        conn.execute("CREATE TABLE epoch_state (epoch INTEGER, timestamp TEXT, pot_size_rtc REAL)")

        conn.executemany(
            "INSERT INTO balances VALUES (?, ?, ?)",
            [
                ("founder_vault", 50000.0, "2026-01-10T00:00:00Z"),
                ("RTCminerAlpha", 120.5, "2026-01-15T12:00:00Z"),
                ("RTCminerBeta", 45.25, "2026-01-20T12:00:00Z"),
                ("RTCminerGamma", 15.0, "2026-03-05T12:00:00Z"),
            ],
        )
        conn.executemany(
            "INSERT INTO epoch_rewards VALUES (?, ?, ?, ?)",
            [
                (101, "RTCminerAlpha", 1.5, "2026-01-15T12:00:00Z"),
                (102, "RTCminerBeta", 1.5, "2026-01-20T12:00:00Z"),
                (103, "RTCminerGamma", 1.5, "2026-03-05T12:00:00Z"),
            ],
        )
        conn.executemany(
            "INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?)",
            [
                ("RTCminerAlpha", "2026-01-15T12:00:00Z", "PowerPC G4", "Mac mini G4,1"),
                ("RTCminerBeta", "2026-01-20T12:00:00Z", "SPARC", "Sun Blade 150"),
                ("RTCminerGamma", "2026-03-05T12:00:00Z", "x86_64", "Ryzen 9, comma-test"),
            ],
        )
        conn.executemany(
            "INSERT INTO epoch_state VALUES (?, ?, ?)",
            [
                (101, "2026-01-15T12:00:00Z", 1.5),
                (102, "2026-01-20T12:00:00Z", 1.5),
                (103, "2026-03-05T12:00:00Z", 1.5),
            ],
        )
        conn.commit()
        conn.close()

    def test_sqlite_csv_export_writes_all_five_tables_and_valid_checksums(self):
        out_dir = self.tmp_path / "out_csv"
        rc = self.mod.main(["--format", "csv", "--db-path", str(self.db_path), "--output", str(out_dir)])
        self.assertEqual(rc, 0)

        for tbl in ("miners", "epochs", "rewards", "attestations", "balances"):
            csv_file = out_dir / f"{tbl}.csv"
            self.assertTrue(csv_file.exists(), f"Missing {csv_file}")
            with csv_file.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertGreaterEqual(len(rows), 3)

        manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
        for fname, meta in manifest["files"].items():
            actual_sha = hashlib.sha256((out_dir / fname).read_bytes()).hexdigest()
            self.assertEqual(actual_sha, meta["sha256"])

    def test_date_range_filtering_excludes_out_of_range_records(self):
        out_dir = self.tmp_path / "out_filtered"
        rc = self.mod.main([
            "--format", "json",
            "--db-path", str(self.db_path),
            "--from", "2026-01-01",
            "--to", "2026-02-01",
            "--output", str(out_dir),
        ])
        self.assertEqual(rc, 0)
        rewards = json.loads((out_dir / "rewards.json").read_text(encoding="utf-8"))
        self.assertEqual([r["epoch"] for r in rewards], [101, 102])

    def test_jsonl_and_parquet_formats_supported(self):
        out_jsonl = self.tmp_path / "out_jsonl"
        self.assertEqual(self.mod.main(["--format", "jsonl", "--db-path", str(self.db_path), "--output", str(out_jsonl)]), 0)
        lines = (out_jsonl / "miners.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 3)

        out_pq = self.tmp_path / "out_pq"
        self.assertEqual(self.mod.main(["--format", "parquet", "--db-path", str(self.db_path), "--output", str(out_pq)]), 0)
        pq_bytes = (out_pq / "miners.parquet").read_bytes()
        self.assertTrue(pq_bytes.startswith(b"PAR1") and pq_bytes.endswith(b"PAR1"))

    def test_gini_and_distribution_summary_excludes_founder_wallets(self):
        datasets = self.mod.extract_from_sqlite(self.db_path)
        dist = self.mod.build_distribution_summary(datasets["balances"])
        self.assertEqual(dist["total_wallets_count"], 4)
        self.assertEqual(dist["non_founder_wallets_count"], 3)
        self.assertEqual(dist["top_10_non_founder_holders"][0]["wallet_id"], "RTCminerAlpha")
        self.assertGreater(dist["gini_non_founder_wallets"], 0.0)
        self.assertLess(dist["gini_non_founder_wallets"], 1.0)

    def test_api_only_mode_without_database_access(self):
        def fake_fetcher(url: str, timeout: int = 15):
            if url.endswith("/epoch"):
                return {"epoch": 344, "epoch_pot": 1.5, "timestamp": "2026-11-11T00:00:00Z", "settled": True}
            if url.endswith("/api/miners"):
                return [{"miner": "RTCapiMiner1", "device_arch": "G4", "device_model": "PowerBook G4", "antiquity_multiplier": 2.5, "last_attest": "2026-11-11T00:00:00Z"}]
            if "/wallet/balance" in url:
                return {"amount_rtc": 88.75}
            return {}

        datasets = self.mod.extract_from_api("https://50.28.86.131", fetcher=fake_fetcher)
        self.assertEqual(len(datasets["miners"]), 1)
        self.assertEqual(datasets["miners"][0]["miner_id"], "RTCapiMiner1")
        self.assertEqual(datasets["balances"][0]["amount_rtc"], 88.75)


if __name__ == "__main__":
    unittest.main()
