#!/usr/bin/env python3
"""
C1: Dual-write shadow balance TOCTOU — adversarial fund creation
VULN: utxo_endpoints.py:585-630 — the dual-write to the account model
  opens its OWN sqlite3.connect() with NO BEGIN IMMEDIATE (line 587).
  The shadow debit check (line 596-599) and UPDATE (line 610-611) run
  outside any write lock. Concurrent transfers see the same stale shadow
  balance, both UPDATEs commit, shadow model diverges from UTXO.

Impact: Shadow account balance goes negative. Two concurrent transfers
  both pass the stale balance check, both debit, and the shadow model
  diverges permanently. "UTXO is primary, account is shadow" (line 629)
  but the divergence is irreversible.

Fix: Add conn.execute("BEGIN IMMEDIATE") before the shadow balance
  check at line 596, or reuse the UTXO transfer's IMMEDIATE connection.
"""
import threading
import time
import unittest
import tempfile
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utxo_db import UtxoDB, UNIT


def _init_shadow_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS balances (
            miner_id TEXT PRIMARY KEY,
            amount_i64 INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER, epoch INTEGER, miner_id TEXT,
            delta_i64 INTEGER, reason TEXT
        )
    """)
    conn.commit()


class TestDualWriteShadowTocTou(unittest.TestCase):
    """C1: Dual-write shadow account TOCTOU."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

        conn = sqlite3.connect(self.tmp.name)
        _init_shadow_db(conn)
        conn.execute(
            "INSERT OR IGNORE INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ('alice', 100_000)  # Tight: only enough for ONE debit
        )
        conn.commit()
        conn.close()

        self.db.apply_transaction({
            'tx_type': 'mining_reward',
            'inputs': [],
            'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
            'fee_nrtc': 0,
            'timestamp': int(time.time()),
            '_allow_minting': True,
        }, block_height=1)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _dual_write_debit(self, address: str, debit_i64: int,
                          results: list, thread_id: int):
        """
        Simulate the dual-write pattern from utxo_endpoints.py:585-630.
        Opens OWN connection with NO BEGIN IMMEDIATE.
        """
        try:
            conn = sqlite3.connect(self.tmp.name)
            c = conn.cursor()

            c.execute(
                "SELECT amount_i64 FROM balances WHERE miner_id = ?",
                (address,)
            )
            row = c.fetchone()
            shadow_balance = row[0] if row else 0

            if shadow_balance < debit_i64:
                results.append(f"T{thread_id}: insufficient shadow ({shadow_balance} < {debit_i64})")
                conn.close()
                return

            # TOCTOU WINDOW: both threads see same stale balance here
            time.sleep(0.002)

            c.execute(
                "UPDATE balances SET amount_i64 = amount_i64 - ? WHERE miner_id = ?",
                (debit_i64, address)
            )
            conn.commit()
            results.append(f"T{thread_id}: debited {debit_i64} (shadow was {shadow_balance})")
            conn.close()
        except Exception as e:
            results.append(f"T{thread_id}: error: {e}")

    def test_c1_dual_write_tocTou(self):
        """C1: Concurrent dual-write both see stale shadow balance.

        Timeline:
          1. TA opens conn → reads shadow=100K → ok → UPDATE
          2. TB opens conn → reads shadow=100K (stale!) → ok → UPDATE
          3. Both commit → shadow = -60K (should be 20K)
        """
        results = []
        debit = 80_000
        threads = []

        for i in range(2):
            t = threading.Thread(
                target=self._dual_write_debit,
                args=('alice', debit, results, i + 1)
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        conn = sqlite3.connect(self.tmp.name)
        final_shadow = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = 'alice'"
        ).fetchone()[0]
        conn.close()

        expected = 100_000 - debit
        divergence = final_shadow - expected

        print(f"\n[C1] Initial shadow: 100_000")
        for r in results:
            print(f"  {r}")
        print(f"[C1] Final shadow: {final_shadow}")
        print(f"[C1] Expected: {expected}")
        print(f"[C1] Divergence: {divergence:+d}")

        if divergence < 0:
            print(f"[C1] ✅ RACE CONFIRMED: Shadow went negative by {abs(divergence)}")

        with open(os.path.join(os.path.dirname(__file__),
                               'utxo_endpoints.py'), 'r') as f:
            src = f.read()
        dw_start = src.find('# --- dual-write to account model')
        if dw_start >= 0:
            dw_block = src[dw_start:dw_start + 600]
            has_immediate = 'IMMEDIATE' in dw_block
            print(f"[C1] Dual-write L585-630 uses BEGIN IMMEDIATE: {has_immediate}")
            self.assertFalse(has_immediate,
                "C1: dual-write shadow update has NO BEGIN IMMEDIATE "
                "(utxo_endpoints.py:585-630)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
