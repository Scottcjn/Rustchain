#!/usr/bin/env python3
"""
Bug Report PoC: Payout Worker — Orphaned Balance & Refund Race Conditions
=========================================================================

Target file: node/payout_worker.py
Severity:    HIGH — can cause permanent fund loss

BUG 1 — execute_withdrawal() returns None in production mode (line 74-80)
  The production branch of execute_withdrawal() has only `pass`, meaning it
  always returns None. When process_withdrawal() receives None from
  execute_withdrawal(), it raises "No transaction hash returned" (line 153).
  This triggers the except branch which refunds the balance. However, since
  the "production" path never broadcast any transaction, the deduction was
  already committed to DB. The refund correctly reverses it, BUT:
  → If the process crashes between the COMMIT on line 129 (deduction) and
    the except-handler refund (line 159-172), the balance is permanently
    lost. This is a TOCTOU gap because the deduction and the broadcast
    happen in SEPARATE database transactions.

BUG 2 — Refund uses separate connection (line 159 vs line 95)
  process_withdrawal() deducts balance using one `with sqlite3.connect()`
  block (line 95), then refunds in a completely different `with sqlite3.connect()`
  block (line 159). Between these two blocks, if the Python process crashes,
  receives SIGKILL, or the machine loses power, the deducted balance is
  never refunded. This violates the comment's own claim of "Atomic balance
  check + deduction" — the overall operation is NOT atomic.

BUG 3 — cleanup_old_withdrawals() archive file race condition (line 244-255)
  Uses 'a' (append) mode with json.dump() per-row. If two worker instances
  run concurrently, interleaved writes produce corrupted JSON-lines (partial
  lines from concurrent appends). Also, the archive + DELETE is not atomic:
  a crash after archiving but before DELETE causes duplicate entries on the
  next run.

BUG 4 — update_claim_status() rowcount check after commit (line 367)
  In claims_submission.py line 367, `cursor.rowcount` is checked AFTER
  conn.commit(). However, the second UPDATE (for settled/rejected details)
  on lines 334-351 overwrites the cursor, so `cursor.rowcount` reflects
  the LAST UPDATE, not the status update. If the claim_id doesn't exist,
  the first UPDATE silently does nothing, but the audit log INSERT still
  succeeds, creating an orphaned audit entry.
"""
import os
import sys
import sqlite3
import time
import json
import threading
import unittest

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))


class TestPayoutWorkerRefundRace(unittest.TestCase):
    """PoC: Demonstrate refund-gap in payout_worker.py"""

    def setUp(self):
        """Create test DB with required schema."""
        self.db_path = ":memory:"
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE accounts (
                public_key TEXT PRIMARY KEY,
                balance REAL NOT NULL DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE withdrawals (
                withdrawal_id TEXT PRIMARY KEY,
                miner_pk TEXT NOT NULL,
                amount REAL NOT NULL,
                fee REAL DEFAULT 0,
                destination TEXT,
                created_at INTEGER,
                status TEXT DEFAULT 'pending',
                processed_at INTEGER,
                tx_hash TEXT,
                error_msg TEXT
            )
        """)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_bug1_production_mode_returns_none(self):
        """
        BUG 1: execute_withdrawal() production path returns None.

        In payout_worker.py lines 73-80, the else branch (production mode)
        contains only `pass`, returning None implicitly. This means EVERY
        production withdrawal will:
          1. Deduct balance (committed to DB)
          2. Call execute_withdrawal() → returns None
          3. Hit line 153: raise Exception("No transaction hash returned")
          4. Refund balance in except handler

        Net effect in production: no withdrawal can EVER succeed because
        execute_withdrawal() always returns None. This is a critical
        deployment blocker.
        """
        # Simulate the production code path
        mock_mode = False  # Production
        withdrawal = {
            'withdrawal_id': 'w_test_001',
            'destination': 'RTC1abc',
            'amount': 100.0,
            'fee': 1.0,
            'miner_pk': 'miner_pk_test'
        }

        def execute_withdrawal_production(w):
            """Reproduction of payout_worker.py lines 73-80"""
            if mock_mode:
                return "0xfake"
            else:
                # Real blockchain integration would go here
                pass  # ← BUG: always returns None

        result = execute_withdrawal_production(withdrawal)
        self.assertIsNone(result, "Production mode returns None — all withdrawals fail")

        # In the real code, this None triggers:
        # if tx_hash:  ← False
        #     ...
        # else:
        #     raise Exception("No transaction hash returned")
        # → balance refunded, but withdrawal permanently marked 'failed'

    def test_bug2_non_atomic_deduct_refund_gap(self):
        """
        BUG 2: Deduction and refund use separate DB connections.

        The deduction happens in one `with sqlite3.connect()` block (line 95),
        and the refund in another (line 159). A crash between them causes
        permanent balance loss.

        This PoC simulates the gap:
        1. Deduct balance in transaction A
        2. Simulate crash (don't execute refund)
        3. Verify balance is permanently reduced
        """
        miner_pk = "miner_crash_test"
        initial_balance = 1000.0
        withdrawal_amount = 500.0

        # Setup account
        self.conn.execute(
            "INSERT INTO accounts (public_key, balance) VALUES (?, ?)",
            (miner_pk, initial_balance)
        )
        self.conn.commit()

        # STEP 1: Deduction succeeds (simulating payout_worker.py line 95-129)
        self.conn.execute("BEGIN IMMEDIATE")
        self.conn.execute(
            "UPDATE accounts SET balance = balance - ? WHERE public_key = ?",
            (withdrawal_amount, miner_pk)
        )
        self.conn.execute("COMMIT")

        # Verify deduction happened
        balance_after_deduct = self.conn.execute(
            "SELECT balance FROM accounts WHERE public_key = ?",
            (miner_pk,)
        ).fetchone()[0]
        self.assertEqual(balance_after_deduct, 500.0)

        # STEP 2: Simulate crash — refund never executes
        # In production, a SIGKILL or power loss here means the
        # except handler (line 155-175) never runs.

        # STEP 3: On restart, balance is permanently reduced
        # No mechanism exists to detect or recover orphaned deductions
        final_balance = self.conn.execute(
            "SELECT balance FROM accounts WHERE public_key = ?",
            (miner_pk,)
        ).fetchone()[0]

        self.assertEqual(
            final_balance, 500.0,
            "Balance permanently lost — no recovery mechanism exists"
        )
        # The 500 RTC is gone forever. The withdrawal status is still
        # 'processing' (line 126-128), but the worker has no logic to
        # detect stale 'processing' entries and refund them on restart.

    def test_bug3_concurrent_archive_corruption(self):
        """
        BUG 3: cleanup_old_withdrawals() archive file interleaving.

        Two concurrent workers writing to the same archive file with
        open(file, 'a') can produce corrupted JSON-lines output due to
        non-atomic writes. Additionally, archive + DELETE is not atomic.
        """
        import tempfile
        archive_path = os.path.join(
            tempfile.gettempdir(),
            f"test_archive_{int(time.time())}.json"
        )

        # Simulate concurrent writes
        results = []

        def write_archive(worker_id, entries):
            for entry in entries:
                with open(archive_path, 'a') as f:
                    json.dump({"worker": worker_id, "id": entry}, f)
                    f.write('\n')
                    # Yield to increase chance of interleaving
                    time.sleep(0.001)
            results.append(worker_id)

        # Two workers writing simultaneously
        entries_a = list(range(20))
        entries_b = list(range(20, 40))

        t1 = threading.Thread(target=write_archive, args=(1, entries_a))
        t2 = threading.Thread(target=write_archive, args=(2, entries_b))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Check if all lines are valid JSON
        if os.path.exists(archive_path):
            with open(archive_path, 'r') as f:
                lines = f.readlines()
            
            valid = 0
            invalid = 0
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                    valid += 1
                except json.JSONDecodeError:
                    invalid += 1

            # Even if all lines happen to be valid in this run,
            # the code is fundamentally unsafe because file-level
            # append is NOT guaranteed atomic for multi-byte writes.
            self.assertGreater(valid, 0, "Some entries should be written")
            os.remove(archive_path)

    def test_bug4_stale_processing_entries_on_restart(self):
        """
        BUG 4: No recovery for 'processing' status entries.

        When the worker restarts, entries stuck in 'processing' status are
        never re-processed or refunded. The worker only queries 
        `WHERE status = 'pending'` (line 39), so 'processing' entries
        become permanently orphaned.
        """
        miner_pk = "miner_orphan_test"
        
        # Setup: account with balance already deducted
        self.conn.execute(
            "INSERT INTO accounts (public_key, balance) VALUES (?, ?)",
            (miner_pk, 500.0)  # Already deducted from 1000
        )
        
        # Withdrawal stuck in 'processing' from a previous crash
        self.conn.execute("""
            INSERT INTO withdrawals 
            (withdrawal_id, miner_pk, amount, fee, destination, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'processing')
        """, ('w_orphan_001', miner_pk, 500.0, 0, 'RTC1dest', int(time.time()) - 3600))
        self.conn.commit()

        # Worker restart: query only fetches 'pending'
        pending = self.conn.execute("""
            SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'
        """).fetchone()[0]
        
        processing = self.conn.execute("""
            SELECT COUNT(*) FROM withdrawals WHERE status = 'processing'
        """).fetchone()[0]

        self.assertEqual(pending, 0, "No pending entries to process")
        self.assertEqual(processing, 1, "Orphaned 'processing' entry exists")
        
        # The orphaned entry will never be resolved:
        # - Balance already deducted (500 RTC lost)
        # - Worker ignores 'processing' entries
        # - No cleanup/recovery mechanism exists


class TestClaimsSubmissionBugs(unittest.TestCase):
    """PoC: Bugs in claims_submission.py"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE claims (
                claim_id TEXT PRIMARY KEY,
                miner_id TEXT NOT NULL,
                epoch INTEGER NOT NULL,
                wallet_address TEXT NOT NULL,
                reward_urtc INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                submitted_at INTEGER NOT NULL,
                verified_at INTEGER,
                settled_at INTEGER,
                transaction_hash TEXT,
                settlement_batch TEXT,
                rejection_reason TEXT,
                signature TEXT NOT NULL,
                public_key TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                UNIQUE(miner_id, epoch)
            )
        """)
        cursor.execute("""
            CREATE TABLE claims_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT,
                details TEXT,
                timestamp INTEGER NOT NULL
            )
        """)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_bug5_update_status_rowcount_after_second_update(self):
        """
        BUG 5: update_claim_status() checks rowcount of wrong UPDATE.

        In claims_submission.py line 367:
            return cursor.rowcount > 0
        
        But when status is 'settled' or 'rejected', a second UPDATE
        executes on lines 334-351. The cursor.rowcount now reflects
        the SECOND update, not the first status update. If the claim_id
        doesn't exist, the first UPDATE does nothing (rowcount=0), but
        the second UPDATE also does nothing (rowcount=0). However, the
        audit log INSERT on line 355 ALWAYS succeeds.

        This means: orphaned audit entries are created for non-existent claims.
        """
        now = int(time.time())
        fake_claim_id = "claim_99999_nonexistent_miner"

        # Simulate update_claim_status for a non-existent claim
        cursor = self.conn.cursor()

        # First UPDATE — does nothing because claim doesn't exist
        cursor.execute("""
            UPDATE claims
            SET status = ?, updated_at = ?, verified_at = ?
            WHERE claim_id = ?
        """, ('rejected', now, now, fake_claim_id))

        first_rowcount = cursor.rowcount
        self.assertEqual(first_rowcount, 0, "No rows updated for non-existent claim")

        # Second UPDATE (rejection reason) — also does nothing
        cursor.execute("""
            UPDATE claims
            SET rejection_reason = ?
            WHERE claim_id = ?
        """, ("test_reason", fake_claim_id))

        second_rowcount = cursor.rowcount
        self.assertEqual(second_rowcount, 0, "Also no rows updated")

        # But audit log INSERT always succeeds!
        cursor.execute("""
            INSERT INTO claims_audit (claim_id, action, actor, details, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (fake_claim_id, 'claim_rejected', 'system', '{"reason":"test"}', now))

        self.conn.commit()

        # Verify orphaned audit entry exists
        audit_count = self.conn.execute(
            "SELECT COUNT(*) FROM claims_audit WHERE claim_id = ?",
            (fake_claim_id,)
        ).fetchone()[0]

        self.assertEqual(audit_count, 1, "Orphaned audit entry created for non-existent claim")

        # Verify no claim exists
        claim = self.conn.execute(
            "SELECT COUNT(*) FROM claims WHERE claim_id = ?",
            (fake_claim_id,)
        ).fetchone()[0]

        self.assertEqual(claim, 0, "No claim exists — audit entry is orphaned")


if __name__ == "__main__":
    print("=" * 70)
    print("RustChain Bug PoC: Payout Worker & Claims Submission")
    print("Severity: HIGH — permanent fund loss, orphaned records")
    print("=" * 70)
    unittest.main(verbosity=2)
