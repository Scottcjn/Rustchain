import importlib.util
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
ADMIN_KEY = "0123456789abcdef0123456789abcdef"


def _make_disclosure_side_effect(ledger=(), rewards=(), pending=()):
    """Build a side_effect for ``db.execute`` that dispatches on the FROM
    clause so each of the three live-route queries returns the right rows.

    Live route, in order: ``ledger``, ``epoch_rewards`` (LEFT JOIN
    ``epoch_state``), ``pending_ledger``.
    """

    def _execute(sql, *args, **kwargs):
        cursor = MagicMock()
        sql_lower = (sql or "").lower()
        if "from ledger" in sql_lower and "pending_ledger" not in sql_lower:
            cursor.fetchall.return_value = list(ledger)
        elif "from epoch_rewards" in sql_lower:
            cursor.fetchall.return_value = list(rewards)
        elif "from pending_ledger" in sql_lower:
            cursor.fetchall.return_value = list(pending)
        else:
            cursor.fetchall.return_value = []
        return cursor

    return _execute


class TestPublicApiDisclosure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "import.db")
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location("rustchain_integrated_public_api_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
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

    def test_miners_public_response_exposes_records(self):
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_cursor = mock_conn.cursor.return_value

            row = {
                "miner": "addr1",
                "ts_ok": 1700000000,
                "device_family": "PowerPC",
                "device_arch": "G4",
                "entropy_score": 0.95,
            }

            miners_query = MagicMock()
            miners_query.fetchall.return_value = [row]

            first_attest_query = MagicMock()
            first_attest_query.fetchone.return_value = [1699990000]

            mock_cursor.execute.side_effect = [miners_query, first_attest_query]

            resp = self.client.get("/api/miners")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertEqual(len(body), 1)
            self.assertEqual(body[0]["miner"], "addr1")
            self.assertEqual(body[0]["hardware_type"], "PowerPC G4 (Vintage)")
            self.assertEqual(body[0]["antiquity_multiplier"], 2.5)

    def test_miners_admin_receives_full_records(self):
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_cursor = mock_conn.cursor.return_value

            row = {
                "miner": "addr1",
                "ts_ok": 1700000000,
                "device_family": "PowerPC",
                "device_arch": "G4",
                "entropy_score": 0.95,
            }

            miners_query = MagicMock()
            miners_query.fetchall.return_value = [row]

            first_attest_query = MagicMock()
            first_attest_query.fetchone.return_value = [1699990000]

            mock_cursor.execute.side_effect = [miners_query, first_attest_query]

            resp = self.client.get("/api/miners", headers={"X-Admin-Key": ADMIN_KEY})
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertEqual(len(body), 1)
            self.assertEqual(body[0]["miner"], "addr1")
            self.assertEqual(body[0]["hardware_type"], "PowerPC G4 (Vintage)")
            self.assertEqual(body[0]["antiquity_multiplier"], 2.5)

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

    def test_wallet_history_public_returns_unified_envelope_with_confirmed_reward_and_pending(self):
        """Envelope {ok, miner_id, transactions, total} with one of each kind."""
        ledger_rows = [
            (1700001000, 200, "alice", 2500000, "transfer_in:bob:tx_pending_alias"),
        ]
        reward_rows = [
            (201, 1250000, 1),
        ]
        pending_rows = [
            (1700000500, "alice", "bob", 2500000, None, "pending", "tx_pending", 1700000500),
        ]
        side_effect = MagicMock(side_effect=_make_disclosure_side_effect(
            ledger=ledger_rows, rewards=reward_rows, pending=pending_rows,
        ))
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute = side_effect
            resp = self.client.get("/wallet/history?miner_id=alice&limit=3")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertTrue(body["ok"])
            self.assertEqual(body["miner_id"], "alice")
            self.assertEqual(body["total"], 3)
            txs = body["transactions"]
            self.assertEqual(len(txs), 3)
            by_hash = {t.get("tx_hash"): t for t in txs}

            # Confirmed ledger row surfaces as transfer_in with from=bob
            conf = by_hash.get("tx_pending_alias")
            self.assertIsNotNone(conf)
            self.assertEqual(conf["type"], "transfer_in")
            self.assertEqual(conf["from"], "bob")
            self.assertEqual(conf["amount"], 2.5)
            self.assertEqual(conf["epoch"], 200)
            self.assertNotIn("status", conf)

            # Reward row surfaces as type=reward
            reward = next((t for t in txs if t["type"] == "reward"), None)
            self.assertIsNotNone(reward)
            self.assertEqual(reward["epoch"], 201)
            self.assertEqual(reward["amount"], 1.25)

            # Pending row surfaces as transfer_out with status=pending
            pend = by_hash.get("tx_pending")
            self.assertIsNotNone(pend)
            self.assertEqual(pend["type"], "transfer_out")
            self.assertEqual(pend["to"], "bob")
            self.assertEqual(pend["status"], "pending")

    def test_wallet_history_public_accepts_address_alias(self):
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute = MagicMock(side_effect=_make_disclosure_side_effect())
            resp = self.client.get("/wallet/history?address=alice")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()
            self.assertEqual(body["miner_id"], "alice")
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

    def test_wallet_history_envelope_does_not_leak_legacy_flat_array(self):
        """Regression guard: the body must never be a bare JSON array.
        The pre-#997 contract returned ``[{...}, ...]`` directly; the unified
        contract returns ``{ok, miner_id, transactions, total}``."""
        ledger_rows = [
            (1700000000, 200, "alice", 100, "transfer_in:bob:tx1"),
        ]
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute = MagicMock(side_effect=_make_disclosure_side_effect(
                ledger=ledger_rows,
            ))
            body = self.client.get("/wallet/history?miner_id=alice").get_json()
            self.assertIsInstance(body, dict)
            self.assertNotIsInstance(body, list)
            self.assertIn("transactions", body)
            self.assertIsInstance(body["transactions"], list)


if __name__ == "__main__":
    unittest.main()
