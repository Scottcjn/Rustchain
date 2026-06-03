# SPDX-License-Identifier: MIT
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sophia_db import get_connection, init_db, store_inspection
from sophia_scheduler import SophiaScheduler, TokenBucketRateLimiter


def _fingerprint():
    return {
        "cpu_brand": "PowerPC G4",
        "clock_variance": 0.03,
        "cache_latency_ns": 80,
        "simd_width": 128,
    }


class CountingLimiter:
    def __init__(self):
        self.calls = 0

    def acquire(self):
        self.calls += 1


def test_scheduler_acquires_rate_limit_slot_per_batch_task(tmp_path):
    db_path = str(tmp_path / "sophia.db")
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        for miner_id in ("m1", "m2", "m3"):
            store_inspection(conn, miner_id, "APPROVED", 0.9, "", "rb", {})
    finally:
        conn.close()

    limiter = CountingLimiter()
    scheduler = SophiaScheduler(
        db_path=db_path,
        ollama_endpoints=[],
        fingerprint_fetcher=lambda _miner_id: _fingerprint(),
        rate_limiter=limiter,
    )

    results = scheduler.run_batch()

    assert len(results) == 3
    assert limiter.calls == 3


def test_token_bucket_waits_when_burst_capacity_is_exhausted():
    now = [0.0]
    sleeps = []

    def fake_time():
        return now[0]

    def fake_sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    limiter = TokenBucketRateLimiter(
        rate=2,
        per=10,
        time_fn=fake_time,
        sleep_fn=fake_sleep,
    )

    limiter.acquire()
    limiter.acquire()
    limiter.acquire()

    assert sleeps == [5.0]
