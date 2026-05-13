"""
sophia_scheduler.py -- Batch processing scheduler for SophiaCore.
RIP-306 implementation for Rustchain bounty #2261.

Features:
  - Run inspection batch every 24h (configurable)
  - Anomaly-triggered re-inspection (confidence < 0.5 or verdict changed)
  - Ollama failover chain: localhost -> 100.75.100.89 -> VPS
  - Queue CAUTIOUS/SUSPICIOUS cases for human review
"""

import logging
import os
import time
import threading

from sophia_core import SophiaCoreInspector, OLLAMA_FAILOVER_CHAIN
from sophia_db import (
    get_connection, init_db, get_low_confidence_miners,
    get_verdict_changed_miners, get_all_miner_ids,
    get_latest_inspection, DB_PATH
)

logger = logging.getLogger("sophia_scheduler")

DEFAULT_INTERVAL_HOURS = 24
DEFAULT_MAX_TASKS_PER_MINUTE = 10


class TokenBucketRateLimiter:
    """Thread-safe token bucket for scheduler task throughput."""

    def __init__(self, rate, per=60, time_fn=None, sleep_fn=None):
        if rate <= 0:
            raise ValueError("rate must be positive")
        if per <= 0:
            raise ValueError("per must be positive")

        self.rate = float(rate)
        self.per = float(per)
        self.capacity = float(rate)
        self.tokens = float(rate)
        self.time_fn = time.monotonic if time_fn is None else time_fn
        self.sleep_fn = time.sleep if sleep_fn is None else sleep_fn
        self.last_check = self.time_fn()
        self.lock = threading.Lock()

    def _refill(self, now):
        elapsed = max(0.0, now - self.last_check)
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * (self.rate / self.per),
        )
        self.last_check = now

    def acquire(self):
        """Block until one task token is available."""
        while True:
            with self.lock:
                self._refill(self.time_fn())
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait_seconds = (1.0 - self.tokens) / (self.rate / self.per)

            self.sleep_fn(wait_seconds)


class SophiaScheduler:
    """Periodic batch inspector with anomaly re-inspection."""

    def __init__(self, db_path=None, interval_hours=DEFAULT_INTERVAL_HOURS,
                 ollama_endpoints=None, fingerprint_fetcher=None,
                 max_tasks_per_minute=None, rate_limiter=None):
        """
        Args:
            db_path: SQLite database path
            interval_hours: Hours between batch runs
            ollama_endpoints: Ollama failover chain (defaults to OLLAMA_FAILOVER_CHAIN)
            fingerprint_fetcher: callable(miner_id) -> fingerprint dict.
                Must be provided for real operation; can be None for testing.
            max_tasks_per_minute: global task throttle. Defaults to
                SOPHIA_MAX_TASKS_PER_MINUTE or 10.
            rate_limiter: optional test hook implementing acquire().
        """
        self.db_path = db_path or DB_PATH
        self.interval_seconds = interval_hours * 3600
        if max_tasks_per_minute is None:
            max_tasks_per_minute = int(os.getenv(
                "SOPHIA_MAX_TASKS_PER_MINUTE",
                str(DEFAULT_MAX_TASKS_PER_MINUTE),
            ))
        self.rate_limiter = rate_limiter or TokenBucketRateLimiter(
            max_tasks_per_minute,
            per=60,
        )
        self.inspector = SophiaCoreInspector(
            db_path=self.db_path,
            ollama_endpoints=list(OLLAMA_FAILOVER_CHAIN) if ollama_endpoints is None else ollama_endpoints,
        )
        self.fingerprint_fetcher = fingerprint_fetcher
        self._stop_event = threading.Event()
        self._thread = None

    def _fetch_fingerprint(self, miner_id):
        """Fetch the latest fingerprint for a miner."""
        if self.fingerprint_fetcher is None:
            raise RuntimeError("No fingerprint_fetcher configured")
        return self.fingerprint_fetcher(miner_id)

    def _acquire_task_slot(self):
        """Throttle each inspection task before it reaches downstream services."""
        self.rate_limiter.acquire()

    def run_batch(self):
        """Run a full batch inspection of all known miners."""
        logger.info("Starting batch inspection run")
        conn = get_connection(self.db_path)
        try:
            miner_ids = get_all_miner_ids(conn)
        finally:
            conn.close()

        results = []
        for miner_id in miner_ids:
            try:
                self._acquire_task_slot()
                fp = self._fetch_fingerprint(miner_id)
                result = self.inspector.inspect(
                    miner_id, fp, inspection_type="batch"
                )
                results.append(result)
                logger.info(
                    "Batch: miner=%s verdict=%s confidence=%.2f",
                    miner_id, result["verdict"], result["confidence"],
                )
            except Exception as exc:
                logger.error("Batch inspection failed for %s: %s", miner_id, exc)

        logger.info("Batch complete: %d/%d inspected", len(results), len(miner_ids))
        return results

    def run_anomaly_reinspection(self):
        """Re-inspect miners with low confidence or changed verdicts."""
        logger.info("Starting anomaly re-inspection")
        conn = get_connection(self.db_path)
        try:
            low_conf = get_low_confidence_miners(conn, threshold=0.5)
            changed = get_verdict_changed_miners(conn)
        finally:
            conn.close()

        # Collect unique miner IDs needing re-inspection
        reinspect_ids = set()
        for row in low_conf:
            reinspect_ids.add(row["miner_id"])
            logger.info(
                "Anomaly trigger: miner=%s confidence=%.2f (below 0.5)",
                row["miner_id"], row["confidence"],
            )
        for row in changed:
            reinspect_ids.add(row["miner_id"])
            logger.info(
                "Anomaly trigger: miner=%s verdict changed %s -> %s",
                row["miner_id"], row["previous_verdict"], row["current_verdict"],
            )

        results = []
        for miner_id in reinspect_ids:
            try:
                self._acquire_task_slot()
                fp = self._fetch_fingerprint(miner_id)
                result = self.inspector.inspect(
                    miner_id, fp, inspection_type="anomaly"
                )
                results.append(result)
            except Exception as exc:
                logger.error("Anomaly re-inspection failed for %s: %s", miner_id, exc)

        logger.info("Anomaly re-inspection complete: %d miners", len(results))
        return results

    def _loop(self):
        """Main scheduler loop."""
        init_db(self.db_path)
        while not self._stop_event.is_set():
            try:
                self.run_batch()
                self.run_anomaly_reinspection()
            except Exception as exc:
                logger.error("Scheduler loop error: %s", exc)

            self._stop_event.wait(timeout=self.interval_seconds)

    def start(self):
        """Start the scheduler in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Scheduler already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Scheduler started (interval=%ds)", self.interval_seconds)

    def stop(self):
        """Stop the scheduler."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Scheduler stopped")

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()
