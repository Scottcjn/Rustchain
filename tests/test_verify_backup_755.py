#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Automated RustChain SQLite Backup Verification (#755)."""

import hashlib
import importlib.util
import pathlib
import sqlite3
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFY_PATH = ROOT / "scripts" / "verify_backup.py"


def _load_verify_mod():
    spec = importlib.util.spec_from_file_location("verify_backup_755", VERIFY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _create_rustchain_db(
    db_path: pathlib.Path,
    *,
    positive_balance: float = 100.0,
    max_epoch: int = 344,
    omit_table: str | None = None,
) -> None:
    conn = sqlite3.connect(str(db_path))
    if omit_table != "balances":
        conn.execute("CREATE TABLE balances (miner_id TEXT, amount_rtc REAL)")
        conn.execute("INSERT INTO balances VALUES ('RTCminer1', ?)", (positive_balance,))
    if omit_table != "miner_attest_recent":
        conn.execute("CREATE TABLE miner_attest_recent (miner_id TEXT, timestamp INTEGER)")
        conn.execute("INSERT INTO miner_attest_recent VALUES ('RTCminer1', 1762800000)")
    if omit_table != "headers":
        conn.execute("CREATE TABLE headers (height INTEGER, hash TEXT)")
        conn.execute("INSERT INTO headers VALUES (13680, '00ab')")
    if omit_table != "ledger":
        conn.execute("CREATE TABLE ledger (tx_id TEXT, amount_rtc REAL)")
        conn.execute("INSERT INTO ledger VALUES ('tx1', 5.0)")
    if omit_table != "epoch_rewards":
        conn.execute("CREATE TABLE epoch_rewards (epoch INTEGER, miner_id TEXT, amount_rtc REAL)")
        conn.execute("INSERT INTO epoch_rewards VALUES (?, 'RTCminer1', 1.5)", (max_epoch,))
    conn.commit()
    conn.close()


class VerifyBackup755Test(unittest.TestCase):
    def setUp(self):
        self.mod = _load_verify_mod()
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_backup_and_live_db_pass_non_destructively(self):
        bak = self.tmp_path / "rustchain_v2_20261111.db.bak"
        live = self.tmp_path / "rustchain_v2.db"
        _create_rustchain_db(bak, positive_balance=250.0, max_epoch=343)
        _create_rustchain_db(live, positive_balance=251.5, max_epoch=344)

        before_sha = hashlib.sha256(bak.read_bytes()).hexdigest()
        rc = self.mod.main(["--backup-dir", str(self.tmp_path), "--live-db", str(live)])
        after_sha = hashlib.sha256(bak.read_bytes()).hexdigest()

        self.assertEqual(rc, 0)
        self.assertEqual(before_sha, after_sha, "Backup file must never be modified")

    def test_missing_backup_returns_exit_code_1_without_crashing(self):
        empty_dir = self.tmp_path / "empty_backups"
        empty_dir.mkdir()
        rc = self.mod.main(["--backup-dir", str(empty_dir)])
        self.assertEqual(rc, 1)

    def test_corrupted_sqlite_file_fails_integrity_check(self):
        bad_bak = self.tmp_path / "rustchain_v2_corrupt.db"
        bad_bak.write_bytes(b"NOT_A_VALID_SQLITE_HEADER_BYTES_1234567890")
        rc = self.mod.main(["--backup-file", str(bad_bak)])
        self.assertEqual(rc, 1)

    def test_zero_positive_balances_or_missing_table_fails(self):
        zero_bal = self.tmp_path / "rustchain_v2_zero.db"
        _create_rustchain_db(zero_bal, positive_balance=0.0, max_epoch=344)
        self.assertEqual(self.mod.main(["--backup-file", str(zero_bal)]), 1)

        missing_tbl = self.tmp_path / "rustchain_v2_no_ledger.db"
        _create_rustchain_db(missing_tbl, positive_balance=50.0, max_epoch=344, omit_table="ledger")
        self.assertEqual(self.mod.main(["--backup-file", str(missing_tbl)]), 1)

    def test_backup_more_than_one_epoch_behind_live_db_fails(self):
        stale_bak = self.tmp_path / "rustchain_v2_stale.db"
        live = self.tmp_path / "rustchain_v2_live.db"
        _create_rustchain_db(stale_bak, positive_balance=100.0, max_epoch=340)
        _create_rustchain_db(live, positive_balance=100.0, max_epoch=344)
        self.assertEqual(self.mod.main(["--backup-file", str(stale_bak), "--live-db", str(live)]), 1)


if __name__ == "__main__":
    unittest.main()
