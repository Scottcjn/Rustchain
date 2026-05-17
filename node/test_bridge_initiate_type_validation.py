# SPDX-License-Identifier: Apache-2.0
import os
import sqlite3
import tempfile
import unittest

from flask import Flask

import bridge_api


class TestBridgeInitiateTypeValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        bridge_api.DB_PATH = self.db_path
        conn = sqlite3.connect(self.db_path)
        try:
            bridge_api.init_bridge_schema(conn.cursor())
            conn.execute(
                "CREATE TABLE IF NOT EXISTS balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lock_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bridge_transfer_id INTEGER,
                    miner_id TEXT,
                    amount_i64 INTEGER,
                    lock_type TEXT,
                    locked_at INTEGER,
                    unlock_at INTEGER,
                    status TEXT,
                    created_at INTEGER
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

        app = Flask(__name__)
        bridge_api.register_bridge_routes(app)
        app.config["TESTING"] = False
        self.client = app.test_client()

    def tearDown(self):
        self.client = None
        os.unlink(self.db_path)

    def valid_payload(self):
        return {
            "direction": "withdraw",
            "source_chain": "solana",
            "dest_chain": "rustchain",
            "source_address": "S" * 32,
            "dest_address": "RTCdestination12345",
            "amount_rtc": 1.0,
        }

    def test_malformed_json_field_types_return_400_not_500(self):
        cases = {
            "source_chain_list": {"source_chain": []},
            "dest_chain_dict": {"dest_chain": {}},
            "source_address_list": {"source_address": ["x"] * 12},
            "dest_address_dict": {"dest_address": {"wallet": "RTCdestination12345"}},
            "bridge_type_list": {"bridge_type": []},
            "memo_dict": {"memo": {"note": "not a string"}},
        }

        for name, override in cases.items():
            with self.subTest(name=name):
                payload = {**self.valid_payload(), **override}
                response = self.client.post("/api/bridge/initiate", json=payload)
                self.assertEqual(response.status_code, 400)

    def test_non_finite_amounts_return_400_not_500(self):
        for amount_rtc in ("nan", "inf", "-inf"):
            with self.subTest(amount_rtc=amount_rtc):
                payload = {**self.valid_payload(), "amount_rtc": amount_rtc}
                response = self.client.post("/api/bridge/initiate", json=payload)
                self.assertEqual(response.status_code, 400)

    def test_mixed_case_chain_uses_normalized_value_for_address_validation(self):
        payload = {
            **self.valid_payload(),
            "source_chain": "Base",
            "source_address": "not-a-base-wallet",
        }

        response = self.client.post("/api/bridge/initiate", json=payload)

        self.assertEqual(response.status_code, 400)

    def test_successful_mixed_case_chain_response_uses_normalized_values(self):
        payload = {
            **self.valid_payload(),
            "source_chain": "Solana",
            "dest_chain": "RustChain",
        }

        response = self.client.post("/api/bridge/initiate", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["source_chain"], "solana")
        self.assertEqual(body["dest_chain"], "rustchain")


if __name__ == "__main__":
    unittest.main()
