#!/usr/bin/env python3
"""
RustChain Payout Worker
Processes pending withdrawals from queue → sent → completed
"""
import os, time, sqlite3, hashlib, json, logging
from datetime import datetime
from typing import Optional, Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('payout_worker')

# Configuration
DB_PATH = "./rustchain_v2.db"
BATCH_SIZE = 10
POLL_INTERVAL = 30  # seconds
MAX_RETRIES = 3
MOCK_MODE = os.environ.get("RUSTCHAIN_MOCK_MODE", "0") == "1"  # Default: production (False)


class ProductionWithdrawalNotConfigured(RuntimeError):
    """Raised when the worker is asked to broadcast without an implementation."""


class PayoutWorker:
    def __init__(self):
        self.db_path = DB_PATH
        self.stats = {
            'processed': 0,
            'failed': 0,
            'total_rtc': 0.0
        }

    def get_pending_withdrawals(self, limit: int = BATCH_SIZE) -> List[Dict]:
        """Fetch pending withdrawals from database"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT withdrawal_id, miner_pk, amount, fee, destination, created_at
                FROM withdrawals
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,)).fetchall()

            withdrawals = []
            for row in rows:
                withdrawals.append({
                    'withdrawal_id': row[0],
                    'miner_pk': row[1],
                    'amount': row[2],
                    'fee': row[3],
                    'destination': row[4],
                    'created_at': row[5]
                })

            return withdrawals

    def _record_broadcast_reconciliation_needed(
        self,
        withdrawal_id: str,
        tx_hash: str,
        error: str,
    ) -> None:
        """Keep broadcast withdrawals out of the refund path after DB failures."""
        message = (
            "Broadcast returned transaction hash but completion update failed; "
            f"manual reconciliation required: {error}"
        )
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE withdrawals
                    SET status = 'processing',
                        tx_hash = ?,
                        error_msg = ?
                    WHERE withdrawal_id = ?
                """, (tx_hash, message, withdrawal_id))
        except Exception as record_error:
            logger.error(
                "Failed to record reconciliation state for %s (%s): %s",
                withdrawal_id,
                tx_hash,
                record_error,
            )

    def lookup_withdrawal_status(self, tx_hash: str) -> Optional[bool]:
        """Return True if tx is confirmed, False if known failed, None if unknown.

        Production nodes should replace this hook with their chain lookup RPC.
        Keeping the default as None preserves manual reconciliation semantics
        without incorrectly marking broadcast withdrawals failed.
        """
        return None

    def reconcile_broadcast_withdrawals(self):
        """Resolve broadcast withdrawals that are waiting on chain reconciliation."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute("""
                    SELECT withdrawal_id, tx_hash
                    FROM withdrawals
                    WHERE status = 'processing'
                    AND tx_hash IS NOT NULL
                    AND tx_hash != ''
                """).fetchall()

            for withdrawal_id, tx_hash in rows:
                chain_status = self.lookup_withdrawal_status(tx_hash)
                if chain_status is None:
                    continue
                with sqlite3.connect(self.db_path) as conn:
                    if chain_status:
                        conn.execute("""
                            UPDATE withdrawals
                            SET status = 'completed',
                                processed_at = ?,
                                error_msg = NULL
                            WHERE withdrawal_id = ?
                            AND status = 'processing'
                            AND tx_hash = ?
                        """, (int(time.time()), withdrawal_id, tx_hash))
                    else:
                        conn.execute("""
                            UPDATE withdrawals
                            SET status = 'failed',
                                error_msg = 'Broadcast transaction not found or failed; manual refund required'
                            WHERE withdrawal_id = ?
                            AND status = 'processing'
                            AND tx_hash = ?
                        """, (withdrawal_id, tx_hash))
        except Exception as e:
            logger.error(f"Failed to reconcile broadcast withdrawals: {e}")

    def execute_withdrawal(self, withdrawal: Dict) -> Optional[str]:
        """Execute withdrawal transaction"""
        if MOCK_MODE:
            # Mock transaction - generate fake tx hash
            tx_data = f"{withdrawal['withdrawal_id']}:{withdrawal['destination']}:{withdrawal['amount']}"
            tx_hash = "0x" + hashlib.sha256(tx_data.encode()).hexdigest()

            # Simulate processing time
            time.sleep(0.5)

            # Random failure for testing (5% chance)
            import random
            if random.random() < 0.05:
                raise Exception("Mock transaction failed")

            return tx_hash
        else:
            # Real blockchain integration would go here
            # This would interact with actual RustChain nodes
            # Example:
            # tx = build_transaction(withdrawal)
            # tx_hash = broadcast_transaction(tx)
            # wait_for_confirmation(tx_hash)
            raise ProductionWithdrawalNotConfigured(
                "Production withdrawal execution is not configured; refusing to "
                "complete withdrawal without a broadcast transaction hash"
            )

    def process_withdrawal(self, withdrawal: Dict) -> bool:
        """Process a single withdrawal with balance deduction before execution."""
        withdrawal_id = withdrawal['withdrawal_id']
        tx_hash = None

        try:
            logger.info(f"Processing withdrawal {withdrawal_id}")
            logger.info(f"  Amount: {withdrawal['amount']} RTC")
            logger.info(f"  Destination: {withdrawal['destination']}")

            if not MOCK_MODE:
                message = (
                    "Production withdrawal execution is not configured; leaving "
                    "withdrawal pending for retry"
                )
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        "UPDATE withdrawals SET error_msg = ? "
                        "WHERE withdrawal_id = ? AND status = 'pending'",
                        (message, withdrawal_id),
                    )
                logger.error(f"✗ Withdrawal {withdrawal_id}: {message}")
                return False

            # ── Atomic balance check + deduction + status update ─────────
            # All three operations MUST happen in a single transaction so
            # that a crash between them cannot leave funds deducted without
            # a matching withdrawal, or vice-versa.
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    # Check sender has sufficient balance
                    row = conn.execute(
                        "SELECT balance FROM accounts WHERE public_key = ?",
                        (withdrawal['miner_pk'],)
                    ).fetchone()
                    current_balance = row[0] if row else 0

                    total_deduction = withdrawal['amount'] + withdrawal.get('fee', 0)
                    if current_balance < total_deduction:
                        conn.execute(
                            "UPDATE withdrawals SET status = 'failed', error_msg = ? "
                            "WHERE withdrawal_id = ?",
                            (f"Insufficient balance: have {current_balance}, need {total_deduction}",
                             withdrawal_id)
                        )
                        conn.execute("COMMIT")
                        logger.error(f"✗ Withdrawal {withdrawal_id}: insufficient balance")
                        self.stats['failed'] += 1
                        return False

                    # Deduct balance BEFORE broadcasting transaction
                    conn.execute(
                        "UPDATE accounts SET balance = balance - ? WHERE public_key = ?",
                        (total_deduction, withdrawal['miner_pk'])
                    )

                    # Mark as processing
                    conn.execute(
                        "UPDATE withdrawals SET status = 'processing' WHERE withdrawal_id = ?",
                        (withdrawal_id,)
                    )
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise

            # Execute withdrawal (broadcast transaction)
            tx_hash = self.execute_withdrawal(withdrawal)

            if tx_hash:
                # Mark as completed
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        UPDATE withdrawals
                        SET status = 'completed',
                            processed_at = ?,
                            tx_hash = ?
                        WHERE withdrawal_id = ?
                    """, (int(time.time()), tx_hash, withdrawal_id))

                logger.info(f"[OK] Withdrawal {withdrawal_id} completed: {tx_hash}")
                self.stats['processed'] += 1
                self.stats['total_rtc'] += withdrawal['amount']
                return True
            else:
                raise Exception("No transaction hash returned")

        except Exception as e:
            logger.error(f"✗ Withdrawal {withdrawal_id} failed: {e}")

            if tx_hash:
                self._record_broadcast_reconciliation_needed(
                    withdrawal_id,
                    tx_hash,
                    str(e),
                )
                self.stats['failed'] += 1
                return False

            # Refund balance on broadcast failure and mark as failed
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "UPDATE accounts SET balance = balance + ? WHERE public_key = ?",
                    (withdrawal['amount'] + withdrawal.get('fee', 0),
                     withdrawal['miner_pk'])
                )
                conn.execute("""
                    UPDATE withdrawals
                    SET status = 'failed',
                        error_msg = ?
                    WHERE withdrawal_id = ?
                """, (str(e), withdrawal_id))
                conn.execute("COMMIT")

            self.stats['failed'] += 1
            return False

    def recover_orphans(self):
        """Flag withdrawals stuck in processing without assuming safe refund.

        A ``processing`` row with no tx_hash is ambiguous: the worker may have
        crashed before broadcast, or it may have crashed after a successful
        broadcast but before persisting the tx_hash. Automatically refunding
        that state can double-pay the miner, so keep the debit in place and
        require explicit reconciliation evidence before any refund.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                rows = conn.execute("""
                    SELECT withdrawal_id
                    FROM withdrawals
                    WHERE status = 'processing'
                    AND (tx_hash IS NULL OR tx_hash = '')
                """).fetchall()

                for (withdrawal_id,) in rows:
                    logger.warning(
                        "Withdrawal %s is processing without tx_hash; "
                        "leaving debit intact for manual reconciliation",
                        withdrawal_id,
                    )
                    conn.execute(
                        """
                        UPDATE withdrawals
                        SET error_msg = 'Processing without tx_hash; manual reconciliation required before refund'
                        WHERE withdrawal_id = ?
                        AND status = 'processing'
                        AND (tx_hash IS NULL OR tx_hash = '')
                        """,
                        (withdrawal_id,),
                    )
                conn.execute("COMMIT")

                if rows:
                    logger.info(f"Flagged {len(rows)} ambiguous processing withdrawals for reconciliation.")

        except Exception as e:
            logger.error(f"Failed to recover orphans: {e}")

    def process_batch(self) -> int:
        """Process a batch of withdrawals"""
        withdrawals = self.get_pending_withdrawals()

        if not withdrawals:
            return 0

        logger.info(f"Processing batch of {len(withdrawals)} withdrawals")

        processed = 0
        for withdrawal in withdrawals:
            if self.process_withdrawal(withdrawal):
                processed += 1

            # Small delay between transactions
            time.sleep(1)

        return processed

    def run_forever(self):
        """Main worker loop"""
        logger.info("RustChain Payout Worker started")
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Mode: {'MOCK' if MOCK_MODE else 'PRODUCTION'}")
        logger.info(f"Poll interval: {POLL_INTERVAL}s")
        logger.info(f"Batch size: {BATCH_SIZE}")

        while True:
            try:
                # Recover pre-broadcast orphans before processing new batches to prevent stranded funds
                self.recover_orphans()

                # Reconcile already-broadcast withdrawals that were left in processing state
                self.reconcile_broadcast_withdrawals()

                # Process batch
                processed = self.process_batch()

                if processed > 0:
                    logger.info(f"Batch complete: {processed} withdrawals processed")
                    logger.info(f"Stats: {self.stats}")

                # Clean up old completed withdrawals (older than 7 days)
                self.cleanup_old_withdrawals()

                # Sleep before next batch
                time.sleep(POLL_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Shutdown requested")
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(POLL_INTERVAL * 2)  # Back off on error

    def cleanup_old_withdrawals(self):
        """Archive old completed withdrawals to cold storage."""
        cutoff = int(time.time()) - (7 * 24 * 3600)  # 7 days ago

        with sqlite3.connect(self.db_path) as conn:
            # Count old withdrawals
            count = conn.execute("""
                SELECT COUNT(*) FROM withdrawals
                WHERE status = 'completed' AND processed_at < ?
            """, (cutoff,)).fetchone()[0]

            if count > 0:
                # Archive to file (in production, send to cold storage)
                rows = conn.execute("""
                    SELECT withdrawal_id, miner_pk, amount, destination, tx_hash, processed_at
                    FROM withdrawals
                    WHERE status = 'completed' AND processed_at < ?
                """, (cutoff,)).fetchall()

                archive_dir = os.path.join(os.path.dirname(self.db_path), "archives")
                os.makedirs(archive_dir, exist_ok=True)
                archive_file = os.path.join(
                    archive_dir,
                    f"withdrawal_archive_{datetime.now().strftime('%Y%m%d')}.jsonl"
                )

                try:
                    with open(archive_file, 'a') as f:
                        for row in rows:
                            json.dump({
                                'withdrawal_id': row[0],
                                'miner_pk': row[1],
                                'amount': row[2],
                                'destination': row[3],
                                'tx_hash': row[4],
                                'processed_at': row[5]
                            }, f)
                            f.write('\n')
                            f.flush()
                except OSError as e:
                    logger.error(f"Failed to write archive {archive_file}: {e}")
                    return

                # Delete from database (only after successful archive)
                try:
                    conn.execute("""
                        DELETE FROM withdrawals
                        WHERE status = 'completed' AND processed_at < ?
                    """, (cutoff,))
                    logger.info(f"Archived and pruned {count} old withdrawals to {archive_file}")
                except Exception as e:
                    logger.error(
                        f"Archive written to {archive_file} but DB prune failed: {e}. "
                        "Manual cleanup may be needed."
                    )

    def get_stats(self) -> Dict:
        """Get worker statistics"""
        with sqlite3.connect(self.db_path) as conn:
            pending = conn.execute(
                "SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'"
            ).fetchone()[0]

            processing = conn.execute(
                "SELECT COUNT(*) FROM withdrawals WHERE status = 'processing'"
            ).fetchone()[0]

            completed = conn.execute(
                "SELECT COUNT(*) FROM withdrawals WHERE status = 'completed'"
            ).fetchone()[0]

            failed = conn.execute(
                "SELECT COUNT(*) FROM withdrawals WHERE status = 'failed'"
            ).fetchone()[0]

        return {
            'pending': pending,
            'processing': processing,
            'completed': completed,
            'failed': failed,
            'session_processed': self.stats['processed'],
            'session_failed': self.stats['failed'],
            'session_total_rtc': self.stats['total_rtc']
        }

def main():
    """Main entry point"""
    worker = PayoutWorker()

    try:
        # Print initial stats
        stats = worker.get_stats()
        logger.info(f"Initial queue state: {stats}")

        # Run worker
        worker.run_forever()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
