import importlib.util
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


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
        try:
            cls._tmp.cleanup()
        except OSError:
            pass

    def test_api_miner_attestations_rejects_non_integer_limit(self):
        resp = self.client.get(
            "/api/miner/alice/attestations?limit=abc",
            headers={"X-Admin-Key": ADMIN_KEY},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "limit must be an integer"})

    def test_api_balances_rejects_non_integer_limit(self):
        resp = self.client.get(
            "/api/balances?limit=abc",
            headers={"X-Admin-Key": ADMIN_KEY},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "limit must be an integer"})

    def test_admin_limit_validation_preserves_auth_boundary(self):
        resp = self.client.get("/api/balances?limit=abc")
        self.assertEqual(resp.status_code, 401)

    def test_pending_list_rejects_non_integer_limit(self):
        resp = self.client.get("/pending/list?limit=abc", headers={"X-Admin-Key": ADMIN_KEY})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json(), {"ok": False, "error": "limit must be an integer"})

    def test_pending_list_clamps_negative_limit(self):
        mock_db = MagicMock()
        mock_db.__enter__.return_value = mock_db
        mock_db.__exit__.return_value = False
        mock_db.execute.return_value.fetchall.return_value = []

        with patch.object(self.mod.sqlite3, "connect", return_value=mock_db):
            resp = self.client.get("/pending/list?limit=-1", headers={"X-Admin-Key": ADMIN_KEY})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"ok": True, "count": 0, "pending": []})
        self.assertEqual(mock_db.execute.call_args.args[1], ("pending", 1))


if __name__ == "__main__":
    unittest.main()
