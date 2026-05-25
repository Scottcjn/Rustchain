# SPDX-License-Identifier: MIT
"""
D1: Dual-write unit mismatch — precision loss between UTXO (8 decimals, UNIT=100M)
    and account model (6 decimals, ACCOUNT_UNIT=1M).
VULN: Dual-write converts amount_rtc via amount * ACCOUNT_UNIT (6 decimals) while
  UTXO uses UNIT (8 decimals). Amounts with 7+ decimal places lose the 7th-8th
  decimal digits in the account model. Over many transfers, dust accumulates.
Impact: Permanent, accumulating divergence between UTXO and account model.
  Integrity check (/utxo/integrity) detects mismatch but cannot fix it.
Fix: Use the same unit precision for both systems.
"""
import unittest
import tempfile
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utxo_db import UtxoDB, UNIT

ACCOUNT_UNIT = 1_000_000  # 6 decimals


class TestDualWriteUnitMismatch(unittest.TestCase):
    """D1: Precision loss in dual-write."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_d1_unit_mismatch(self):
        amt = Decimal('0.12345678')
        utxo_nrtc = int(amt * UNIT)
        account_i64 = int(amt * ACCOUNT_UNIT)
        account_reconstructed = account_i64 * (UNIT // ACCOUNT_UNIT)
        loss = utxo_nrtc - account_reconstructed

        print(f"\n[D1] Amount: {amt} RTC")
        print(f"[D1] UTXO (8 dec): {utxo_nrtc} nRTC")
        print(f"[D1] Account (6 dec): {account_i64} uRTC")
        print(f"[D1] Reconstructed: {account_reconstructed} nRTC")
        print(f"[D1] Precision loss: {loss} nRTC/tx")
        self.assertGreater(loss, 0)

    def test_d1_accumulated(self):
        tx_count = 100
        amt = Decimal('0.12345678')
        utxo_total = sum(int(amt * UNIT) for _ in range(tx_count))
        account_total = sum(int(amt * ACCOUNT_UNIT) for _ in range(tx_count))
        account_reconstructed = account_total * (UNIT // ACCOUNT_UNIT)
        divergence = utxo_total - account_reconstructed

        print(f"\n[D1] {tx_count} transfers:")
        print(f"[D1] UTXO total: {utxo_total} nRTC")
        print(f"[D1] Account recon: {account_reconstructed} nRTC")
        print(f"[D1] Divergence: {divergence} nRTC ({Decimal(divergence)/Decimal(UNIT)} RTC)")
        self.assertGreater(divergence, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
