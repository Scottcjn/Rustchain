import importlib.util
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
ADMIN_KEY = "0123456789abcdef0123456789abcdef"


def _init_disclosure_schema(db_path):
    """(Re)create the tables read by the live /api/miners and /wallet/history routes.

    Columns mirror the node's own ``CREATE TABLE`` statements so seeded rows flow
    through the production SQL unchanged — a live-contract check rather than a mock.
    """
    con = sqlite3.connect(db_path)
    try:
        con.executescript(
            """
            DROP TABLE IF EXISTS miner_attest_recent;
            DROP TABLE IF EXISTS miner_attest_history;
            DROP TABLE IF EXISTS ledger;

            CREATE TABLE miner_attest_recent(
                miner TEXT PRIMARY KEY,
                ts_ok INTEGER NOT NULL,
                device_family TEXT,
                device_arch TEXT,
                entropy_score REAL DEFAULT 0.0,
                fingerprint_passed INTEGER DEFAULT 0,
                source_ip TEXT,
                warthog_bonus REAL DEFAULT 1.0,
                signing_pubkey TEXT,
                fingerprint_checks_json TEXT DEFAULT '{}'
            );

            CREATE TABLE miner_attest_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner TEXT NOT NULL,
                ts_ok INTEGER NOT NULL,
                device_family TEXT,
                device_arch TEXT,
                entropy_score REAL DEFAULT 0.0,
                fingerprint_passed INTEGER DEFAULT 0
            );

            CREATE TABLE ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                epoch INTEGER NOT NULL,
                miner_id TEXT NOT NULL,
                delta_i64 INTEGER NOT NULL,
                reason TEXT
            );
            """
        )
        con.commit()
    finally:
        con.close()


class TestPublicApiDisclosure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._db_path = os.path.join(cls._tmp.name, "import.db")
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = cls._db_path
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location("rustchain_integrated_public_api_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        # Pin the route's module-level DB_PATH to our temp DB for real-DB tests.
        # (Mock-based tests below patch sqlite3.connect and are unaffected.)
        cls.mod.DB_PATH = cls._db_path
        cls.client = cls.mod.app.test_client()

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

    def test_epoch_public_response_exposes_current_fields(self):
        with patch.object(self.mod, "current_slot", return_value=12345), \
             patch.object(self.mod, "slot_to_epoch", return_value=85), \
             patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchone.return_value = [10]

            resp = self.client.get("/epoch")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertEqual(body["epoch"], 85)
            self.assertEqual(body["slot"], 12345)
            self.assertEqual(body["epoch_pot"], self.mod.PER_EPOCH_RTC)
            self.assertEqual(body["enrolled_miners"], 10)

    def test_epoch_admin_receives_full_fields(self):
        with patch.object(self.mod, "current_slot", return_value=12345), \
             patch.object(self.mod, "slot_to_epoch", return_value=85), \
             patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchone.return_value = [10]

            resp = self.client.get("/epoch", headers={"X-Admin-Key": ADMIN_KEY})
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertEqual(body["slot"], 12345)
            self.assertEqual(body["epoch_pot"], self.mod.PER_EPOCH_RTC)
            self.assertEqual(body["enrolled_miners"], 10)

    def _seed_powerpc_miner(self, miner="addr1", last_ts=None, first_ts=None):
        """Seed one PowerPC G4 attestation (recent + history) into the temp DB."""
        _init_disclosure_schema(self._db_path)
        now = int(time.time())
        last_ts = now if last_ts is None else last_ts
        first_ts = (now - 100000) if first_ts is None else first_ts
        con = sqlite3.connect(self._db_path)
        con.execute(
            """INSERT INTO miner_attest_recent
               (miner, ts_ok, device_family, device_arch, entropy_score)
               VALUES (?,?,?,?,?)""",
            (miner, last_ts, "PowerPC", "G4", 0.95),
        )
        con.execute(
            """INSERT INTO miner_attest_history
               (miner, ts_ok, device_family, device_arch, entropy_score)
               VALUES (?,?,?,?,?)""",
            (miner, first_ts, "PowerPC", "G4", 0.95),
        )
        con.commit()
        con.close()
        return now

    def test_miners_public_response_exposes_records(self):
        """/api/miners returns the paginated {miners, pagination} envelope with HW classification."""
        self._seed_powerpc_miner()
        resp = self.client.get("/api/miners")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()

        self.assertIn("miners", body)
        self.assertIn("pagination", body)
        self.assertEqual(len(body["miners"]), 1)
        m = body["miners"][0]
        self.assertEqual(m["miner"], "addr1")
        self.assertEqual(m["hardware_type"], "PowerPC G4 (Vintage)")
        self.assertEqual(m["antiquity_multiplier"], 2.5)

    def test_miners_admin_receives_full_records(self):
        self._seed_powerpc_miner()
        resp = self.client.get("/api/miners", headers={"X-Admin-Key": ADMIN_KEY})
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()

        self.assertEqual(len(body["miners"]), 1)
        m = body["miners"][0]
        self.assertEqual(m["miner"], "addr1")
        self.assertEqual(m["hardware_type"], "PowerPC G4 (Vintage)")
        self.assertEqual(m["antiquity_multiplier"], 2.5)

    def test_wallet_balance_public_receives_value(self):
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchone.return_value = [1234567]

            resp = self.client.get("/wallet/balance?miner_id=alice")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertEqual(body["miner_id"], "alice")
            self.assertEqual(body["amount_i64"], 1234567)

    def test_wallet_balance_public_accepts_address_alias(self):
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchone.return_value = [7654321]

            resp = self.client.get("/wallet/balance?address=alice")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertEqual(body["miner_id"], "alice")
            self.assertEqual(body["amount_i64"], 7654321)

    def test_wallet_balance_admin_receives_value(self):
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchone.return_value = [1234567]

            resp = self.client.get("/wallet/balance?miner_id=alice", headers={"X-Admin-Key": ADMIN_KEY})
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertEqual(body["miner_id"], "alice")
            self.assertEqual(body["amount_i64"], 1234567)

    def test_wallet_balance_admin_accepts_address_alias(self):
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchone.return_value = [7654321]

            resp = self.client.get("/wallet/balance?address=alice", headers={"X-Admin-Key": ADMIN_KEY})
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertEqual(body["miner_id"], "alice")
            self.assertEqual(body["amount_i64"], 7654321)
            mock_conn.execute.assert_called_once_with(
                "SELECT amount_i64 FROM balances WHERE miner_id=?",
                ("alice",),
            )

    def test_wallet_balance_requires_identifier(self):
        resp = self.client.get("/wallet/balance")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "miner_id or address required"})

    def test_wallet_balance_rejects_conflicting_alias_values(self):
        resp = self.client.get(
            "/wallet/balance?miner_id=alice&address=bob",
            headers={"X-Admin-Key": ADMIN_KEY},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.get_json(),
            {
                "ok": False,
                "error": "miner_id and address must match when both are provided",
            },
        )

    def test_wallet_history_public_formats_unified_transaction_types(self):
        """The public envelope formats settled (ledger) and pending rows per the unified contract."""
        _init_disclosure_schema(self._db_path)
        con = sqlite3.connect(self._db_path)
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS pending_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                epoch INTEGER NOT NULL,
                from_miner TEXT NOT NULL,
                to_miner TEXT NOT NULL,
                amount_i64 INTEGER NOT NULL,
                reason TEXT,
                status TEXT DEFAULT 'pending',
                created_at INTEGER NOT NULL,
                confirms_at INTEGER NOT NULL,
                tx_hash TEXT
            );
            """
        )
        # Settled outbound transfer (ledger table)
        con.execute(
            "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?,?,?,?,?)",
            (1700000000, 9, "alice", 1_250_000, "transfer_out:bob:tx_settled"),
        )
        # Pending inbound transfer (pending_ledger table)
        con.execute(
            """INSERT INTO pending_ledger
               (ts, epoch, from_miner, to_miner, amount_i64, reason, status,
                created_at, confirms_at, tx_hash)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (1700001000, 9, "carol", "alice", 2_500_000, "signed_transfer:coffee",
             "pending", 1700001000, 1700087400, "tx_pending"),
        )
        con.commit()
        con.close()

        resp = self.client.get("/wallet/history?miner_id=alice&limit=10")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()

        self.assertIsInstance(body, dict)
        self.assertTrue(body["ok"])
        self.assertEqual(body["miner_id"], "alice")
        txs = body["transactions"]
        self.assertEqual(body["total"], 2)

        pending = next(t for t in txs if t.get("status") == "pending")
        self.assertEqual(pending["type"], "transfer_in")
        self.assertEqual(pending["from"], "carol")
        self.assertEqual(pending["tx_hash"], "tx_pending")

        settled = next(t for t in txs if t["tx_hash"] == "tx_settled")
        self.assertEqual(settled["type"], "transfer_out")
        self.assertEqual(settled["to"], "bob")
        self.assertNotIn("status", settled)  # settled ledger rows carry no status field

    def test_wallet_history_public_accepts_address_alias(self):
        _init_disclosure_schema(self._db_path)
        resp = self.client.get("/wallet/history?address=alice")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["miner_id"], "alice")
        self.assertEqual(body["transactions"], [])
        self.assertEqual(body["total"], 0)

    def test_wallet_history_requires_identifier(self):
        resp = self.client.get("/wallet/history")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "miner_id or address required"})

    def test_wallet_history_rejects_conflicting_alias_values(self):
        resp = self.client.get("/wallet/history?miner_id=alice&address=bob")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.get_json(),
            {
                "ok": False,
                "error": "miner_id and address must match when both are provided",
            },
        )

    def test_wallet_history_rejects_invalid_limit(self):
        resp = self.client.get("/wallet/history?miner_id=alice&limit=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "limit must be an integer"})


if __name__ == "__main__":
    unittest.main()
