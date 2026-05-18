import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from flask import Flask

NODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NODE_DIR))

from gpu_render_endpoints import register_gpu_render_endpoints


class GpuRenderEndpointValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "gpu.db")
        with sqlite3.connect(self.db_path) as db:
            db.execute("CREATE TABLE balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL DEFAULT 0)")
            db.execute(
                """
                CREATE TABLE render_escrow (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT,
                    from_wallet TEXT,
                    to_wallet TEXT,
                    amount_rtc REAL,
                    status TEXT,
                    created_at INTEGER,
                    released_at INTEGER,
                    escrow_secret_hash TEXT
                )
                """
            )
            db.execute("INSERT INTO balances (miner_pk, balance_rtc) VALUES ('payer', 10)")

        app = Flask(__name__)
        register_gpu_render_endpoints(app, self.db_path, "secret")
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def _post(self, path, payload):
        return self.client.post(path, json=payload, headers={"X-Admin-Key": "secret"})

    def test_escrow_rejects_non_string_wallet_before_sqlite(self):
        resp = self._post(
            "/api/gpu/escrow",
            {
                "job_type": "render",
                "from_wallet": {"id": "payer"},
                "to_wallet": "provider",
                "amount_rtc": 1,
            },
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "from_wallet must be a string")

    def test_release_rejects_non_string_job_id_before_sqlite(self):
        resp = self._post(
            "/api/gpu/release",
            {
                "job_id": {"id": "job1"},
                "actor_wallet": "payer",
                "escrow_secret": "secret",
            },
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "job_id must be a string")


if __name__ == "__main__":
    unittest.main()
