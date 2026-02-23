import importlib.util
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
ADMIN_KEY = "0123456789abcdef0123456789abcdef"


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

    def test_epoch_public_response_is_redacted(self):
        with patch.object(self.mod, "current_slot", return_value=12345), \
             patch.object(self.mod, "slot_to_epoch", return_value=85), \
             patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchone.return_value = [10]

            resp = self.client.get("/epoch")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertEqual(body["epoch"], 85)
            self.assertEqual(body["visibility"], "public_redacted")
            self.assertNotIn("slot", body)
            self.assertNotIn("epoch_pot", body)
            self.assertNotIn("enrolled_miners", body)

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

    def test_miners_public_response_is_redacted(self):
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchone.return_value = [7]

            resp = self.client.get("/api/miners")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertEqual(body["active_miners"], 7)
            self.assertEqual(body["window_seconds"], 3600)
            self.assertEqual(body["visibility"], "public_redacted")
            self.assertNotIn("miners", body)

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

    def test_wallet_balance_denies_unauthenticated_access(self):
        resp = self.client.get("/wallet/balance?miner_id=alice")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json(), {"ok": False, "reason": "admin_required"})

    def test_wallet_balance_admin_receives_value(self):
        with patch.object(self.mod.sqlite3, "connect") as mock_connect:
            mock_conn = mock_connect.return_value.__enter__.return_value
            mock_conn.execute.return_value.fetchone.return_value = [1234567]

            resp = self.client.get("/wallet/balance?miner_id=alice", headers={"X-Admin-Key": ADMIN_KEY})
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()

            self.assertEqual(body["miner_id"], "alice")
            self.assertEqual(body["amount_i64"], 1234567)


if __name__ == "__main__":
    unittest.main()
