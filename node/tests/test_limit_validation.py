import importlib.util
import os
import sys
import tempfile
import unittest


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
ADMIN_KEY = "0123456789abcdef0123456789abcdef"


class TestLimitValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "import.db")
        os.environ["RC_ADMIN_KEY"] = ADMIN_KEY

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location("rustchain_integrated_limit_validation_test", MODULE_PATH)
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

    def test_api_miner_attestations_rejects_non_integer_limit(self):
        resp = self.client.get("/api/miner/alice/attestations?limit=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "limit must be an integer"})

    def test_api_balances_rejects_non_integer_limit(self):
        resp = self.client.get("/api/balances?limit=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "limit must be an integer"})

    def test_pending_list_rejects_non_integer_limit(self):
        resp = self.client.get("/pending/list?limit=abc", headers={"X-Admin-Key": ADMIN_KEY})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "limit must be an integer"})


if __name__ == "__main__":
    unittest.main()
