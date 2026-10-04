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
            "dest_address": "RTC" + "a" * 40,
            "amount_rtc": 1.0,
        }

    # POST /api/bridge/initiate is retired (410 Gone); the request validators
    # and create_bridge_transfer are kept for the historical record, so their
    # type/precision guarantees are exercised directly.

    def test_initiate_route_is_retired_and_writes_nothing(self):
        bodies = [
            self.valid_payload(),
            {**self.valid_payload(), "amount_rtc": "nan"},
            {**self.valid_payload(), "source_chain": []},
            ["not", "an", "object"],
        ]
        for body in bodies:
            with self.subTest(body=body):
                response = self.client.post("/api/bridge/initiate", json=body)
                self.assertEqual(response.status_code, 410)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(response.get_json()["code"], "WRTC_BRIDGE_DISABLED")
        conn = sqlite3.connect(self.db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM bridge_transfers").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 0)

    def test_malformed_json_field_types_are_rejected(self):
        cases = {
            "source_chain_list": {"source_chain": []},
            "dest_chain_dict": {"dest_chain": {}},
            "source_address_list": {"source_address": ["x"] * 12},
            "dest_address_dict": {"dest_address": {"wallet": "RTCdestination12345"}},
            "amount_bool": {"amount_rtc": True},
            "bridge_type_list": {"bridge_type": []},
            "memo_dict": {"memo": {"note": "not a string"}},
        }

        for name, override in cases.items():
            with self.subTest(name=name):
                result = bridge_api.validate_bridge_request({**self.valid_payload(), **override})
                self.assertFalse(result.ok)

    def test_non_finite_amounts_are_rejected(self):
        for amount_rtc in ("nan", "inf", "-inf"):
            with self.subTest(amount_rtc=amount_rtc):
                result = bridge_api.validate_bridge_request(
                    {**self.valid_payload(), "amount_rtc": amount_rtc}
                )
                self.assertFalse(result.ok)

    def test_overprecision_amount_is_rejected(self):
        result = bridge_api.validate_bridge_request(
            {**self.valid_payload(), "amount_rtc": "1.0000004"}
        )

        self.assertFalse(result.ok)
        self.assertIn("at most 6 decimal places", result.error)

    def test_six_decimal_amount_is_stored_exactly(self):
        result = bridge_api.validate_bridge_request(
            {**self.valid_payload(), "amount_rtc": "1.000001"}
        )
        self.assertTrue(result.ok, result.error)
        details = result.details
        req = bridge_api.BridgeTransferRequest(
            direction=details["direction"],
            source_chain=details["source_chain"],
            dest_chain=details["dest_chain"],
            source_address=details["source_address"],
            dest_address=details["dest_address"],
            amount_rtc=details["amount_rtc"],
            memo=details.get("memo"),
            bridge_type=details["bridge_type"],
        )
        conn = sqlite3.connect(self.db_path)
        try:
            ok, body = bridge_api.create_bridge_transfer(conn, req)
            self.assertTrue(ok, body)
            self.assertEqual(body["amount_rtc"], 1.000001)
            row = conn.execute(
                "SELECT amount_i64 FROM bridge_transfers WHERE tx_hash = ?",
                (body["tx_hash"],),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row[0], 1_000_001)

    def test_mixed_case_chain_uses_normalized_value_for_address_validation(self):
        result = bridge_api.validate_bridge_request(
            {**self.valid_payload(), "source_chain": "Base", "source_address": "not-a-base-wallet"}
        )
        self.assertTrue(result.ok, result.error)

        valid, _msg = bridge_api.validate_bridge_route_address(
            result.details["source_chain"], result.details["source_address"]
        )

        self.assertFalse(valid)

    def test_mixed_case_chains_are_normalized(self):
        result = bridge_api.validate_bridge_request(
            {**self.valid_payload(), "source_chain": "Solana", "dest_chain": "RustChain"}
        )

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.details["source_chain"], "solana")
        self.assertEqual(result.details["dest_chain"], "rustchain")

if __name__ == "__main__":
    unittest.main()
