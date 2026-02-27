import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestAttestNonceReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "import.db")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location("rustchain_integrated_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    @classmethod
    def tearDownClass(cls):
        if cls._prev_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = cls._prev_db_path
        if cls._prev_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = cls._prev_admin_key
        cls._tmp.cleanup()

    def _conn(self):
        conn = sqlite3.connect(":memory:")
        self.mod.attest_ensure_tables(conn)
        return conn

    def test_nonce_replay_rejected(self):
        with self._conn() as conn:
            ok, err, _ = self.mod.attest_validate_and_store_nonce(
                conn,
                miner="miner-1",
                nonce="nonce-1",
                now_ts=1000,
                nonce_ts=1000,
            )
            self.assertTrue(ok)
            self.assertIsNone(err)

            ok, err, _ = self.mod.attest_validate_and_store_nonce(
                conn,
                miner="miner-1",
                nonce="nonce-1",
                now_ts=1001,
                nonce_ts=1001,
            )
            self.assertFalse(ok)
            self.assertEqual(err, "nonce_replay")

    def test_nonce_freshness_with_skew_window(self):
        with self._conn() as conn:
            ok, err, _ = self.mod.attest_validate_and_store_nonce(
                conn,
                miner="miner-1",
                nonce="nonce-stale",
                now_ts=1000,
                nonce_ts=900,
                skew_seconds=60,
            )
            self.assertFalse(ok)
            self.assertEqual(err, "nonce_stale")

            ok, err, _ = self.mod.attest_validate_and_store_nonce(
                conn,
                miner="miner-1",
                nonce="nonce-fresh",
                now_ts=1000,
                nonce_ts=950,
                skew_seconds=60,
            )
            self.assertTrue(ok)
            self.assertIsNone(err)

    def test_hex_nonce_without_timestamp_is_backward_compatible(self):
        with self._conn() as conn:
            nonce_ts = self.mod.extract_attestation_timestamp({}, {}, "a7f1c4e9")
            self.assertIsNone(nonce_ts)

            ok, err, _ = self.mod.attest_validate_and_store_nonce(
                conn,
                miner="miner-legacy",
                nonce="a7f1c4e9",
                now_ts=1000,
                nonce_ts=nonce_ts,
            )
            self.assertTrue(ok)
            self.assertIsNone(err)

    def test_challenge_is_one_time(self):
        with self._conn() as conn:
            conn.execute("INSERT INTO nonces (nonce, expires_at) VALUES (?, ?)", ("challenge-1", 1100))

            ok, err, _ = self.mod.attest_validate_challenge(conn, "challenge-1", now_ts=1000)
            self.assertTrue(ok)
            self.assertIsNone(err)

            ok, err, _ = self.mod.attest_validate_challenge(conn, "challenge-1", now_ts=1001)
            self.assertFalse(ok)
            self.assertEqual(err, "challenge_invalid")


    def test_challenge_bound_to_miner_rejects_relayed_submit(self):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO nonces (nonce, expires_at, miner_id) VALUES (?, ?, ?)",
                ("challenge-bound", 1100, "miner-A"),
            )

            ok, err, _ = self.mod.attest_validate_challenge(
                conn,
                "challenge-bound",
                miner="miner-B",
                now_ts=1000,
            )
            self.assertFalse(ok)
            self.assertEqual(err, "challenge_mismatch")

    def test_challenge_bound_to_miner_accepts_matching_submit(self):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO nonces (nonce, expires_at, miner_id) VALUES (?, ?, ?)",
                ("challenge-ok", 1100, "miner-A"),
            )

            ok, err, _ = self.mod.attest_validate_challenge(
                conn,
                "challenge-ok",
                miner="miner-A",
                now_ts=1000,
            )
            self.assertTrue(ok)
            self.assertIsNone(err)

    def test_expired_entries_cleanup(self):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO used_nonces (nonce, miner_id, first_seen, expires_at) VALUES (?, ?, ?, ?)",
                ("old-nonce", "miner-1", 900, 950),
            )
            self.mod.attest_cleanup_expired(conn, now_ts=1000)

            ok, err, _ = self.mod.attest_validate_and_store_nonce(
                conn,
                miner="miner-1",
                nonce="old-nonce",
                now_ts=1000,
                nonce_ts=None,
            )
            self.assertTrue(ok)
            self.assertIsNone(err)


if __name__ == "__main__":
    unittest.main()
