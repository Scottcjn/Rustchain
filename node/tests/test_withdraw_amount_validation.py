import importlib.util
import os
import sys
import tempfile
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestWithdrawAmountValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "import.db")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location("rustchain_integrated_withdraw_test", MODULE_PATH)
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

    def _payload(self, amount):
        return {
            "miner_pk": "miner-test",
            "amount": amount,
            "destination": "rtc-destination",
            "signature": "00",
            "nonce": "nonce-1",
        }

    def test_invalid_json_body_rejected(self):
        resp = self.client.post(
            "/withdraw/request",
            data="{not-json",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json().get("error"), "Invalid JSON body")

    def test_non_numeric_amount_rejected(self):
        resp = self.client.post("/withdraw/request", json=self._payload("abc"))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json().get("error"), "Amount must be a number")

    def test_nan_amount_rejected(self):
        resp = self.client.post("/withdraw/request", json=self._payload("NaN"))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json().get("error"), "Amount must be a finite positive number")

    def test_infinite_amount_rejected(self):
        resp = self.client.post("/withdraw/request", json=self._payload("inf"))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json().get("error"), "Amount must be a finite positive number")

    def test_minimum_withdrawal_check_still_applies(self):
        amount = max(0.000001, float(self.mod.MIN_WITHDRAWAL) / 2.0)
        resp = self.client.post("/withdraw/request", json=self._payload(amount))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Minimum withdrawal", resp.get_json().get("error", ""))


if __name__ == "__main__":
    unittest.main()
