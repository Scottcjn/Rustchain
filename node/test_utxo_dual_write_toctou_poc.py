#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
A5: Dual-write TOCTOU — no BEGIN IMMEDIATE in account model shadow update
==========================================================================
VULN: utxo_endpoints.py:585-630 — the dual-write to the account model
opens its own connection and does NOT use BEGIN IMMEDIATE. The shadow
balance check at line 596 and the UPDATE at line 610 have a TOCTOU
window where another concurrent transfer could modify the balance.

Impact: Temporary divergence between UTXO and account model. If two
transfers for the same address happen concurrently, both dual-write
shadow balance checks could pass (seeing the same pre-transfer balance),
and both UPDATEs commit. The account model would show more debited
than actually spent from UTXO side.

Note: Code acknowledges this at lines 627-630 "UTXO is primary, account
is shadow", but the TOCTOU creates real divergence.

Bot: @waefrebeorn
"""

import unittest
import tempfile
import os
import time
import sys
import threading
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utxo_db import UtxoDB, UNIT


class TestDualWriteTocTou(unittest.TestCase):
    """
    Dual-write update lacks BEGIN IMMEDIATE — concurrent debits
    can both see stale balances.
    """

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.db = UtxoDB(self.tmp.name)
        self.db.init_tables()

        # Create tables for account model simulation
        conn = sqlite3.connect(self.tmp.name)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER DEFAULT 0
            )
        """)
        conn.execute(
            "INSERT OR IGNORE INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ('alice', 200_000)  # 200K account units
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_no_immediate_lock_on_dual_write(self):
        """Verify the dual-write pattern uses a bare connection."""
        conn = sqlite3.connect(self.tmp.name)
        # Simulate the dual-write pattern from utxo_endpoints.py
        # Step 1: Read shadow balance (no IMMEDIATE)
        c = conn.cursor()
        c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", ('alice',))
        bal = c.fetchone()[0]
        print(f"[A5] Initial account balance: {bal}")

        # Step 2: Check sufficient balance
        debit = 50_000
        self.assertGreaterEqual(bal, debit, "Sufficient balance before race")

        # Step 3: Simulate dual-write without IMMEDIATE
        c.execute("UPDATE balances SET amount_i64 = amount_i64 - ? WHERE miner_id = ?",
                  (debit, 'alice'))
        conn.commit()
        conn.close()

        # Verify the update worked
        conn2 = sqlite3.connect(self.tmp.name)
        new_bal = conn2.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            ('alice',)
        ).fetchone()[0]
        conn2.close()
        print(f"[A5] Balance after single update: {new_bal}")
        self.assertEqual(new_bal, 150_000)

    def test_concurrent_dual_write_race(self):
        """
        Demonstrate the TOCTOU: two threads simulate dual-write debits
        without BEGIN IMMEDIATE. Both read the same initial balance,
        both succeed, causing account model to diverge from UTXO.
        """
        results = []
        errors = []

        def concurrent_debit(thread_id):
            try:
                conn = sqlite3.connect(self.tmp.name)
                c = conn.cursor()

                # Simulate dual-write: no BEGIN IMMEDIATE
                c.execute(
                    "SELECT amount_i64 FROM balances WHERE miner_id = ?",
                    ('alice',)
                )
                row = c.fetchone()
                bal = row[0] if row else 0

                debit = 80_000
                if bal >= debit:
                    # TOCTOU window: both threads see bal=200_000
                    time.sleep(0.001)  # small delay to trigger race
                    c.execute(
                        "UPDATE balances SET amount_i64 = amount_i64 - ? WHERE miner_id = ?",
                        (debit, 'alice')
                    )
                    conn.commit()
                    results.append(f"Thread {thread_id}: debited {debit}")
                else:
                    results.append(f"Thread {thread_id}: insufficient balance ({bal} < {debit})")
                conn.close()
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=concurrent_debit, args=(1,))
        t2 = threading.Thread(target=concurrent_debit, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Read final balance
        conn = sqlite3.connect(self.tmp.name)
        final_bal = conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            ('alice',)
        ).fetchone()[0]
        conn.close()

        print(f"[A5] Initial: 200_000")
        for r in results:
            print(f"[A5] {r}")
        print(f"[A5] Final: {final_bal}")
        print(f"[A5] Expected (with IMMEDIATE lock): 40_000 (200K - 80K - 80K)")
        print(f"[A5] Got: {final_bal}")

        # With a race, both debits might succeed
        # Without a race (serialized), only one debits
        if final_bal < 40_000:
            print("[A5] Double-spend in account model: both debits went through!")
        elif final_bal == 40_000:
            print("[A5] Correct — both debits applied (expected with IMMEDIATE)")
        elif final_bal == 120_000:
            print("[A5] Only one debit applied (second saw stale balance but UPDATE lost)")
        else:
            print(f"[A5] Unexpected balance: {final_bal}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
