# SPDX-License-Identifier: Apache-2.0
"""Tests for the public, complete wallet balance export (issue #8359)."""

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestApiBalancesExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.db_path = os.path.join(cls.tmp.name, "balances-export.db")
        os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
        os.environ["RUSTCHAIN_DB_PATH"] = cls.db_path
        os.environ.setdefault("RUSTCHAIN_DISABLE_P2P_AUTO_START", "1")
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)
        spec = importlib.util.spec_from_file_location("rustchain_balance_export_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.mod.DB_PATH = cls.db_path
        cls.client = cls.mod.app.test_client()
        cls.original_epoch_reader = cls.mod._balance_export_current_epoch
        cls.original_rate_limit = cls.mod.BALANCE_EXPORT_RATE_LIMIT
        cls.original_rate_cap = cls.mod.BALANCE_EXPORT_RATE_MAX_KEYS

    @classmethod
    def tearDownClass(cls):
        cls.mod._balance_export_current_epoch = cls.original_epoch_reader
        cls.mod.BALANCE_EXPORT_RATE_LIMIT = cls.original_rate_limit
        cls.mod.BALANCE_EXPORT_RATE_MAX_KEYS = cls.original_rate_cap
        cls.tmp.cleanup()

    def setUp(self):
        self.mod._BALANCE_EXPORT_PAGE_CACHE.clear()
        self.mod._BALANCE_EXPORT_RATE_BUCKETS.clear()
        self.mod.BALANCE_EXPORT_RATE_LIMIT = 1000
        self.mod.BALANCE_EXPORT_RATE_MAX_KEYS = 4096
        self.mod._balance_export_current_epoch = lambda: 42
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS balances")
            conn.execute("DROP TABLE IF EXISTS ledger")

    def _create_modern(self, rows, with_ledger=True):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)")
            conn.executemany("INSERT INTO balances VALUES (?, ?)", rows)
            if with_ledger:
                conn.execute(
                    "CREATE TABLE ledger (id INTEGER PRIMARY KEY, ts INTEGER, epoch INTEGER, "
                    "miner_id TEXT, delta_i64 INTEGER, reason TEXT)"
                )

    def _get(self, query="", ip="203.0.113.10"):
        return self.client.get(
            "/api/balances/export" + query,
            environ_base={"REMOTE_ADDR": ip},
        )

    def test_exports_every_wallet_with_required_schema_and_classification(self):
        native = "RTC" + "aB" * 20
        rows = [
            ("z-hosted", -500_000),
            (native, 1_500_000),
            ("founder_future_bucket", 2_000_000),
            ("bcn_relay", 0),
            ("@unusual-handle", 250_000),
        ]
        self._create_modern(rows)
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?, 1, ?, 1, 'test')",
                [(10, native), (12, native), (8, "bcn_relay")],
            )

        first = self._get("?limit=2&offset=0")
        second = self._get("?limit=2&offset=2", ip="203.0.113.11")
        third = self._get("?limit=2&offset=4", ip="203.0.113.12")
        self.assertEqual([first.status_code, second.status_code, third.status_code], [200, 200, 200])
        payloads = [first.get_json(), second.get_json(), third.get_json()]
        exported = [item for payload in payloads for item in payload["balances"]]
        self.assertEqual(len(exported), len(rows))
        self.assertEqual({item["wallet"] for item in exported}, {wallet for wallet, _ in rows})
        self.assertTrue(all(set(item) == {
            "wallet", "balance_rtc", "is_founder", "kind", "last_activity"
        } for item in exported))
        self.assertEqual([item["wallet"] for item in exported], sorted(wallet for wallet, _ in rows))

        by_wallet = {item["wallet"]: item for item in exported}
        self.assertEqual(by_wallet[native]["kind"], "native")
        self.assertEqual(by_wallet[native]["last_activity"], 12)
        self.assertEqual(by_wallet["bcn_relay"]["kind"], "bcn")
        self.assertEqual(by_wallet["bcn_relay"]["last_activity"], 8)
        self.assertEqual(by_wallet["founder_future_bucket"]["kind"], "hosted_handle")
        self.assertTrue(by_wallet["founder_future_bucket"]["is_founder"])
        self.assertEqual(by_wallet["z-hosted"]["balance_rtc"], -0.5)
        self.assertIsNone(by_wallet["@unusual-handle"]["last_activity"])
        self.assertTrue(all(payload["total"] == len(rows) for payload in payloads))

    def test_duplicate_identifiers_are_not_collapsed_or_excluded(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE balances (miner_id TEXT, amount_i64 INTEGER)")
            conn.executemany(
                "INSERT INTO balances VALUES (?, ?)",
                [("duplicate", 1_000_000), ("duplicate", 2_000_000)],
            )
            conn.execute("CREATE TABLE ledger (ts INTEGER, miner_id TEXT)")
            conn.execute("INSERT INTO ledger VALUES (9, 'duplicate')")

        response = self._get()
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["count"], 2)
        self.assertEqual(
            [row["balance_rtc"] for row in payload["balances"]],
            [1.0, 2.0],
        )

    def test_legacy_schema_exports_all_rows(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL)")
            conn.executemany(
                "INSERT INTO balances VALUES (?, ?)",
                [("legacy-a", 1.25), ("legacy-b", 0.0)],
            )

        response = self._get()
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(
            [(row["wallet"], row["balance_rtc"]) for row in payload["balances"]],
            [("legacy-a", 1.25), ("legacy-b", 0.0)],
        )

    def test_mixed_schema_uses_legacy_value_when_modern_value_is_null(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE balances (miner_id TEXT, amount_i64 INTEGER, "
                "miner_pk TEXT, balance_rtc REAL)"
            )
            conn.executemany(
                "INSERT INTO balances VALUES (?, ?, ?, ?)",
                [
                    ("modern", 2_500_000, "old-modern", 99.0),
                    (None, None, "legacy-during-migration", 7.25),
                    ("null-everywhere", None, "ignored-name", None),
                ],
            )

        response = self._get()
        self.assertEqual(response.status_code, 200)
        by_wallet = {row["wallet"]: row for row in response.get_json()["balances"]}
        self.assertEqual(by_wallet["modern"]["balance_rtc"], 2.5)
        self.assertEqual(by_wallet["legacy-during-migration"]["balance_rtc"], 7.25)
        self.assertIsNone(by_wallet["null-everywhere"]["balance_rtc"])

    def test_missing_optional_ledger_is_null_but_malformed_ledger_fails(self):
        self._create_modern([("alice", 1)], with_ledger=False)
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["balances"][0]["last_activity"])

        self.mod._BALANCE_EXPORT_PAGE_CACHE.clear()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE ledger (wrong_column TEXT)")
        response = self._get(ip="203.0.113.11")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["error"], "balances_unavailable")

    def test_page_cache_is_epoch_scoped_and_bypassed_when_epoch_is_unknown(self):
        self._create_modern([("alice", 1_000_000)])
        epoch = [7]
        self.mod._balance_export_current_epoch = lambda: epoch[0]
        self.assertEqual(self._get().get_json()["balances"][0]["balance_rtc"], 1.0)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE balances SET amount_i64 = 2000000 WHERE miner_id = 'alice'")
        self.assertEqual(self._get(ip="203.0.113.11").get_json()["balances"][0]["balance_rtc"], 1.0)
        epoch[0] = 8
        self.assertEqual(self._get(ip="203.0.113.12").get_json()["balances"][0]["balance_rtc"], 2.0)

        def epoch_failure():
            raise RuntimeError("clock unavailable")

        self.mod._balance_export_current_epoch = epoch_failure
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE balances SET amount_i64 = 3000000 WHERE miner_id = 'alice'")
        first = self._get(ip="203.0.113.13").get_json()
        self.assertIsNone(first["epoch"])
        self.assertEqual(first["balances"][0]["balance_rtc"], 3.0)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE balances SET amount_i64 = 4000000 WHERE miner_id = 'alice'")
        second = self._get(ip="203.0.113.14").get_json()
        self.assertEqual(second["balances"][0]["balance_rtc"], 4.0)

    def test_rate_limit_is_per_ip_returns_retry_after_and_is_bounded(self):
        self._create_modern([])
        self.mod.BALANCE_EXPORT_RATE_LIMIT = 2
        for _ in range(2):
            self.assertEqual(self._get(ip="198.51.100.1").status_code, 200)
        limited = self._get(ip="198.51.100.1")
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.get_json()["error"], "rate_limited")
        self.assertIn("Retry-After", limited.headers)
        self.assertEqual(self._get(ip="198.51.100.2").status_code, 200)

        self.mod._BALANCE_EXPORT_RATE_BUCKETS.clear()
        self.mod.BALANCE_EXPORT_RATE_MAX_KEYS = 3
        for index in range(10):
            self.mod._check_balance_export_rate_limit(f"192.0.2.{index}", now_ts=100 + index)
        self.assertLessEqual(len(self.mod._BALANCE_EXPORT_RATE_BUCKETS), 3)

    def test_rejects_invalid_pagination(self):
        self._create_modern([])
        cases = [
            ("?limit=x", "limit must be an integer"),
            ("?limit=0", "limit must be >= 1"),
            ("?limit=101", "limit must be <= 100"),
            ("?offset=x", "offset must be an integer"),
            ("?offset=-1", "offset must be >= 0"),
        ]
        for index, (query, error) in enumerate(cases):
            with self.subTest(query=query):
                response = self._get(query, ip=f"192.0.2.{100 + index}")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"], error)


if __name__ == "__main__":
    unittest.main()
