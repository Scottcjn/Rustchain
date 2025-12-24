#!/usr/bin/env python3
"""
RustChain Payout Worker
Processes pending withdrawals from queue → sent → completed
"""
import time, sqlite3, hashlib, json, logging
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
MOCK_MODE = True  # Set False for real blockchain integration

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
            pass

    def process_withdrawal(self, withdrawal: Dict) -> bool:
        """Process a single withdrawal"""
        withdrawal_id = withdrawal['withdrawal_id']

        try:
            logger.info(f"Processing withdrawal {withdrawal_id}")
            logger.info(f"  Amount: {withdrawal['amount']} RTC")
            logger.info(f"  Destination: {withdrawal['destination']}")

            # Mark as processing
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE withdrawals
                    SET status = 'processing'
                    WHERE withdrawal_id = ?
                """, (withdrawal_id,))

            # Execute withdrawal
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

                logger.info(f"✓ Withdrawal {withdrawal_id} completed: {tx_hash}")
                self.stats['processed'] += 1
                self.stats['total_rtc'] += withdrawal['amount']
                return True
            else:
                raise Exception("No transaction hash returned")

        except Exception as e:
            logger.error(f"✗ Withdrawal {withdrawal_id} failed: {e}")

            # Mark as failed
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE withdrawals
                    SET status = 'failed',
                        error_msg = ?
                    WHERE withdrawal_id = ?
                """, (str(e), withdrawal_id))

            self.stats['failed'] += 1
            return False

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
        """Archive old completed withdrawals"""
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
                    SELECT * FROM withdrawals
                    WHERE status = 'completed' AND processed_at < ?
                """, (cutoff,)).fetchall()

                archive_file = f"withdrawal_archive_{datetime.now().strftime('%Y%m%d')}.json"
                with open(archive_file, 'a') as f:
                    for row in rows:
                        json.dump({
                            'withdrawal_id': row[0],
                            'miner_pk': row[1],
                            'amount': row[2],
                            'destination': row[4],
                            'tx_hash': row[8],
                            'processed_at': row[7]
                        }, f)
                        f.write('\n')

                # Delete from database
                conn.execute("""
                    DELETE FROM withdrawals
                    WHERE status = 'completed' AND processed_at < ?
                """, (cutoff,))

                logger.info(f"Archived {count} old withdrawals to {archive_file}")

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