# SPDX-License-Identifier: MIT
import gc
import os
import tempfile
import unittest

from flask import Flask

import payout_ledger


class TestPayoutLedgerAdminAuth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.original_db_path = payout_ledger.DB_PATH
        self.original_admin_key = os.environ.get("RC_ADMIN_KEY")
        self.original_payout_key = os.environ.get("PAYOUT_ADMIN_KEY")
        self.original_ledger_key = os.environ.get("PAYOUT_LEDGER_ADMIN_KEY")
        payout_ledger.DB_PATH = self.db_path
        app = Flask(__name__)
        payout_ledger.register_ledger_routes(app)
        self.client = app.test_client()

    def tearDown(self):
        payout_ledger.DB_PATH = self.original_db_path
        self._restore_env("RC_ADMIN_KEY", self.original_admin_key)
        self._restore_env("PAYOUT_ADMIN_KEY", self.original_payout_key)
        self._restore_env("PAYOUT_LEDGER_ADMIN_KEY", self.original_ledger_key)
        gc.collect()
        try:
            os.unlink(self.db_path)
        except PermissionError:
            pass

    @staticmethod
    def _restore_env(name, value):
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    def _seed_record(self):
        payout_ledger.init_payout_ledger_tables()
        return payout_ledger.ledger_create(
            "bounty-1",
            "alice",
            7.5,
            wallet_address="RTC-private-wallet",
        )

    def _auth(self, key="expected-admin"):
        return {"X-Admin-Key": key}

    def test_routes_fail_closed_when_admin_key_unset(self):
        os.environ.pop("RC_ADMIN_KEY", None)
        os.environ.pop("PAYOUT_ADMIN_KEY", None)
        os.environ.pop("PAYOUT_LEDGER_ADMIN_KEY", None)

        responses = [
            self.client.get("/ledger"),
            self.client.get("/api/ledger"),
            self.client.get("/api/ledger/anything"),
            self.client.get("/api/ledger/summary"),
            self.client.post("/api/ledger", json={}),
            self.client.patch("/api/ledger/anything/status", json={"status": "confirmed"}),
        ]

        for response in responses:
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.get_json()["error"], "admin key not configured")

    def test_unauthorized_requests_cannot_read_or_mutate_ledger(self):
        os.environ["RC_ADMIN_KEY"] = "expected-admin"
        record_id = self._seed_record()

        denied = [
            self.client.get("/ledger"),
            self.client.get("/api/ledger"),
            self.client.get(f"/api/ledger/{record_id}"),
            self.client.get("/api/ledger/summary"),
            self.client.post(
                "/api/ledger",
                json={
                    "bounty_id": "evil",
                    "contributor": "mallory",
                    "amount_rtc": 1000,
                },
            ),
            self.client.patch(
                f"/api/ledger/{record_id}/status",
                json={"status": "confirmed", "tx_hash": "fake"},
            ),
        ]

        for response in denied:
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.get_json()["error"], "unauthorized")

        row = payout_ledger.ledger_get(record_id)
        self.assertEqual(row["status"], "queued")
        self.assertEqual(row["tx_hash"], "")

    def test_authorized_admin_can_read_create_and_update(self):
        os.environ["RC_ADMIN_KEY"] = "expected-admin"

        create = self.client.post(
            "/api/ledger",
            headers=self._auth(),
            json={
                "bounty_id": "bounty-2",
                "contributor": "bob",
                "amount_rtc": 12.25,
                "wallet_address": "RTC-private-wallet",
            },
        )

        self.assertEqual(create.status_code, 201)
        record_id = create.get_json()["id"]

        listed = self.client.get("/api/ledger", headers=self._auth())
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()[0]["id"], record_id)

        update = self.client.patch(
            f"/api/ledger/{record_id}/status",
            headers={"X-API-Key": "expected-admin"},
            json={"status": "confirmed", "tx_hash": "tx-ok"},
        )
        self.assertEqual(update.status_code, 200)

        row = payout_ledger.ledger_get(record_id)
        self.assertEqual(row["status"], "confirmed")
        self.assertEqual(row["tx_hash"], "tx-ok")

    def test_specific_payout_ledger_key_takes_precedence(self):
        os.environ["RC_ADMIN_KEY"] = "general-admin"
        os.environ["PAYOUT_LEDGER_ADMIN_KEY"] = "ledger-admin"
        self._seed_record()

        wrong = self.client.get("/api/ledger", headers=self._auth("general-admin"))
        right = self.client.get("/api/ledger", headers=self._auth("ledger-admin"))

        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(right.status_code, 200)


if __name__ == "__main__":
    unittest.main()
