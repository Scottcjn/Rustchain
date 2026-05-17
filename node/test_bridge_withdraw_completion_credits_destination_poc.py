import os
import sqlite3
import tempfile
import unittest

from bridge_api import (
    BRIDGE_UNIT,
    BridgeTransferRequest,
    create_bridge_transfer,
    init_bridge_schema,
    update_external_confirmation,
)
from lock_ledger import init_lock_ledger_schema


class TestBridgeWithdrawCompletionCreditsDestination(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)"
        )
        init_bridge_schema(self.conn.cursor())
        init_lock_ledger_schema(self.conn.cursor())
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        os.unlink(self.db_path)

    def test_completed_external_to_rustchain_withdraw_credits_destination(self):
        request = BridgeTransferRequest(
            direction="withdraw",
            source_chain="solana",
            dest_chain="rustchain",
            source_address="A" * 32,
            dest_address="RTCdest1234",
            amount_rtc=10.0,
        )

        ok, result = create_bridge_transfer(self.conn, request, admin_initiated=False)
        self.assertTrue(ok, result)

        ok, result = update_external_confirmation(
            self.conn,
            result["tx_hash"],
            external_tx_hash="solana_tx_123",
            confirmations=12,
            required_confirmations=12,
        )
        self.assertTrue(ok, result)
        self.assertEqual(result["status"], "completed")

        balance_i64 = self.conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            ("RTCdest1234",),
        ).fetchone()[0]
        self.assertEqual(balance_i64, 10 * BRIDGE_UNIT)


if __name__ == "__main__":
    unittest.main()
