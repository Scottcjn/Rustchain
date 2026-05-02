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
        """Fetch and lock pending withdrawals atomically to prevent double payouts."""
        withdrawals = []
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                # FIX: Use BEGIN IMMEDIATE to lock the database during selection and update
                conn.execute("BEGIN IMMEDIATE")
                
                rows = conn.execute("""
                    SELECT withdrawal_id, miner_pk, amount, fee, destination, created_at
                    FROM withdrawals
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (limit,)).fetchall()

                for row in rows:
                    w = {
                        'withdrawal_id': row[0],
                        'miner_pk': row[1],
                        'amount': row[2],
                        'fee': row[3],
                        'destination': row[4],
                        'created_at': row[5]
                    }
                    withdrawals.append(w)
                    
                    # Mark as processing IMMEDIATELY within the same transaction
                    conn.execute("""
                        UPDATE withdrawals
                        SET status = 'processing'
                        WHERE withdrawal_id = ?
                    """, (w['withdrawal_id'],))
                
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error during withdrawal fetch: {e}")
            
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
        """Process a single withdrawal with retry logic."""
        withdrawal_id = withdrawal['withdrawal_id']
        retries = 0

        while retries < MAX_RETRIES:
            try:
                logger.info(f"Executing withdrawal {withdrawal_id} (Attempt {retries + 1}/{MAX_RETRIES})")

                # Execute withdrawal
                tx_hash = self.execute_withdrawal(withdrawal)

                if tx_hash:
                    # Mark as completed
                    now = int(time.time())
                    # FIX: Calculate processing duration to identify network/node latency
                    duration = now - withdrawal.get('created_at', now)
                    
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute("""
                            UPDATE withdrawals
                            SET status = 'completed',
                                processed_at = ?,
                                tx_hash = ?,
                                retry_count = ?
                            WHERE withdrawal_id = ?
                        """, (now, tx_hash, retries, withdrawal_id))

                    logger.info(f"[OK] Withdrawal {withdrawal_id} completed in {duration}s: {tx_hash}")
                    self.stats['processed'] += 1
                    self.stats['total_rtc'] += withdrawal['amount']
                    return True
                else:
                    raise Exception("No transaction hash returned")

            except Exception as e:
                retries += 1
                logger.error(f"Attempt {retries} failed for {withdrawal_id}: {e}")
                if retries < MAX_RETRIES:
                    time.sleep(2 ** retries) # Exponential backoff
                else:
                    # Final failure
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute("""
                            UPDATE withdrawals
                            SET status = 'failed',
                                error_msg = ?,
                                retry_count = ?
                            WHERE withdrawal_id = ?
                        """, (str(e), retries, withdrawal_id))
                    self.stats['failed'] += 1
                    return False
        return False

    def process_batch(self) -> int:
        """Process a batch of withdrawals efficiently."""
        # FIX: Use a larger batch size for selection and process them in order
        withdrawals = self.get_pending_withdrawals(limit=BATCH_SIZE)

        if not withdrawals:
            return 0

        logger.info(f"Processing batch of {len(withdrawals)} locked withdrawals")

        processed = 0
        for withdrawal in withdrawals:
            if self.process_withdrawal(withdrawal):
                processed += 1
            
            # Small adaptive delay between transactions to prevent network/node congestion
            time.sleep(0.2) 

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
                # FIX: Explicitly fetch rows for archiving within a managed context
                rows = conn.execute("""
                    SELECT withdrawal_id, miner_pk, amount, destination, tx_hash, processed_at
                    FROM withdrawals
                    WHERE status = 'completed' AND processed_at < ?
                """, (cutoff,)).fetchall()

                # Archive to file securely
                archive_dir = "archives"
                os.makedirs(archive_dir, exist_ok=True, mode=0o700)
                
                archive_file = os.path.join(archive_dir, f"withdrawal_archive_{datetime.now().strftime('%Y%m%d')}.json")
                
                with open(archive_file, 'a') as f:
                    os.chmod(archive_file, 0o600) 
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
