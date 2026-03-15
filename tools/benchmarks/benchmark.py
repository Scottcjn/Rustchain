#!/usr/bin/env python3
"""
RustChain Node Performance Benchmarking Suite
==============================================

Comprehensive benchmarks for RustChain node performance covering:
  - API endpoint latency (p50/p95/p99)
  - Block verification throughput
  - Attestation processing speed
  - Database query performance
  - Concurrent connection handling

Usage:
    python benchmark.py --host http://localhost:5000
    python benchmark.py --host http://localhost:5000 --output results/
    python benchmark.py --compare results/before.json results/after.json

Requires: requests, numpy (optional for faster percentile calc)
"""

import argparse
import concurrent.futures
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import statistics
import sys
import tempfile
import threading
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_HOST = "http://localhost:5000"
DEFAULT_ITERATIONS = 100
DEFAULT_WARMUP = 5
DEFAULT_CONCURRENCY_LEVELS = [1, 5, 10, 25, 50]
TIMEOUT_SEC = 10

# Endpoints to benchmark grouped by category
ENDPOINT_SPEC: List[Dict[str, Any]] = [
    # --- Health / status ---
    {"path": "/health", "method": "GET", "category": "health"},
    {"path": "/ready", "method": "GET", "category": "health"},
    {"path": "/metrics", "method": "GET", "category": "health"},
    {"path": "/ops/readiness", "method": "GET", "category": "health"},
    # --- Chain state ---
    {"path": "/epoch", "method": "GET", "category": "chain"},
    {"path": "/api/stats", "method": "GET", "category": "chain"},
    {"path": "/api/nodes", "method": "GET", "category": "chain"},
    {"path": "/api/miners", "method": "GET", "category": "chain"},
    {"path": "/api/balances", "method": "GET", "category": "chain"},
    {"path": "/headers/tip", "method": "GET", "category": "chain"},
    {"path": "/api/fee_pool", "method": "GET", "category": "chain"},
    # --- Wallet ---
    {"path": "/wallet/balances/all", "method": "GET", "category": "wallet"},
    {"path": "/wallet/ledger", "method": "GET", "category": "wallet"},
    # --- Governance ---
    {"path": "/governance/proposals", "method": "GET", "category": "governance"},
    # --- Beacon ---
    {"path": "/beacon/digest", "method": "GET", "category": "beacon"},
    {"path": "/beacon/envelopes", "method": "GET", "category": "beacon"},
    # --- Attestation (POST with empty/mock body) ---
    {
        "path": "/attest/challenge",
        "method": "POST",
        "category": "attestation",
        "json_body": {"miner_id": "bench_miner_000"},
    },
    # --- OpenAPI spec ---
    {"path": "/openapi.json", "method": "GET", "category": "meta"},
    # --- Download page ---
    {"path": "/downloads", "method": "GET", "category": "meta"},
    # --- P2P ---
    {"path": "/p2p/stats", "method": "GET", "category": "p2p"},
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LatencyResult:
    """Latency measurements for a single endpoint."""
    endpoint: str
    method: str
    category: str
    samples: List[float] = field(default_factory=list)
    errors: int = 0
    status_codes: Dict[int, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def count(self) -> int:
        return len(self.samples)

    def percentile(self, p: float) -> float:
        if not self.samples:
            return 0.0
        s = sorted(self.samples)
        k = (len(s) - 1) * (p / 100.0)
        f = int(k)
        c = f + 1 if f + 1 < len(s) else f
        d = k - f
        return s[f] + d * (s[c] - s[f])

    @property
    def p50(self) -> float:
        return self.percentile(50)

    @property
    def p95(self) -> float:
        return self.percentile(95)

    @property
    def p99(self) -> float:
        return self.percentile(99)

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.samples) if len(self.samples) > 1 else 0.0

    @property
    def min_ms(self) -> float:
        return min(self.samples) if self.samples else 0.0

    @property
    def max_ms(self) -> float:
        return max(self.samples) if self.samples else 0.0

    def to_dict(self) -> Dict:
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "category": self.category,
            "count": self.count,
            "errors": self.errors,
            "p50_ms": round(self.p50, 3),
            "p95_ms": round(self.p95, 3),
            "p99_ms": round(self.p99, 3),
            "mean_ms": round(self.mean, 3),
            "stdev_ms": round(self.stdev, 3),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "status_codes": dict(self.status_codes),
        }


@dataclass
class ThroughputResult:
    """Throughput measurements for a benchmark category."""
    name: str
    ops_per_sec: float
    total_ops: int
    duration_sec: float
    errors: int = 0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "ops_per_sec": round(self.ops_per_sec, 2),
            "total_ops": self.total_ops,
            "duration_sec": round(self.duration_sec, 3),
            "errors": self.errors,
            "details": self.details,
        }


@dataclass
class ConcurrencyResult:
    """Results for concurrent connection benchmark."""
    concurrency_level: int
    total_requests: int
    successful: int
    failed: int
    duration_sec: float
    rps: float
    mean_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float

    def to_dict(self) -> Dict:
        return {
            "concurrency": self.concurrency_level,
            "total_requests": self.total_requests,
            "successful": self.successful,
            "failed": self.failed,
            "duration_sec": round(self.duration_sec, 3),
            "rps": round(self.rps, 2),
            "mean_latency_ms": round(self.mean_latency_ms, 3),
            "p95_latency_ms": round(self.p95_latency_ms, 3),
            "p99_latency_ms": round(self.p99_latency_ms, 3),
        }


@dataclass
class BenchmarkReport:
    """Full benchmark report."""
    timestamp: str
    host: str
    iterations: int
    node_version: Optional[str] = None
    latency: List[Dict] = field(default_factory=list)
    throughput: List[Dict] = field(default_factory=list)
    concurrency: List[Dict] = field(default_factory=list)
    database: List[Dict] = field(default_factory=list)
    system_info: Dict[str, Any] = field(default_factory=dict)
    duration_sec: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ms(seconds: float) -> float:
    return seconds * 1000.0


def _pct(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (k - f) * (s[c] - s[f])


class ProgressBar:
    """Minimal CLI progress bar."""

    def __init__(self, total: int, prefix: str = "", width: int = 40):
        self.total = total
        self.prefix = prefix
        self.width = width
        self.current = 0
        self._lock = threading.Lock()

    def update(self, n: int = 1):
        with self._lock:
            self.current = min(self.current + n, self.total)
            pct = self.current / self.total if self.total else 1
            filled = int(self.width * pct)
            bar = "#" * filled + "-" * (self.width - filled)
            sys.stderr.write(f"\r  {self.prefix} [{bar}] {self.current}/{self.total}")
            sys.stderr.flush()

    def finish(self):
        self.current = self.total
        self.update(0)
        sys.stderr.write("\n")
        sys.stderr.flush()


# ---------------------------------------------------------------------------
# Benchmark runners
# ---------------------------------------------------------------------------

class RustChainBenchmark:
    """Main benchmark driver."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        iterations: int = DEFAULT_ITERATIONS,
        warmup: int = DEFAULT_WARMUP,
        concurrency_levels: Optional[List[int]] = None,
        db_path: Optional[str] = None,
        admin_key: Optional[str] = None,
        verbose: bool = False,
    ):
        self.host = host.rstrip("/")
        self.iterations = iterations
        self.warmup = warmup
        self.concurrency_levels = concurrency_levels or DEFAULT_CONCURRENCY_LEVELS
        self.db_path = db_path
        self.admin_key = admin_key or os.getenv("RC_ADMIN_KEY", "")
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "RustChain-Bench/1.0"})

    # ---- single-request helpers ----

    def _request(self, method: str, path: str, **kwargs) -> Tuple[float, int]:
        """Issue a single request, return (elapsed_ms, status_code). Raises on network error."""
        url = urljoin(self.host + "/", path.lstrip("/"))
        kwargs.setdefault("timeout", TIMEOUT_SEC)
        t0 = time.perf_counter()
        resp = self.session.request(method, url, **kwargs)
        elapsed = _ms(time.perf_counter() - t0)
        return elapsed, resp.status_code

    # ---- endpoint latency ----

    def bench_endpoint_latency(self) -> List[LatencyResult]:
        results: List[LatencyResult] = []
        total_work = len(ENDPOINT_SPEC) * (self.warmup + self.iterations)
        bar = ProgressBar(total_work, "Endpoint latency")

        for spec in ENDPOINT_SPEC:
            lr = LatencyResult(
                endpoint=spec["path"],
                method=spec["method"],
                category=spec["category"],
            )
            kwargs: Dict[str, Any] = {}
            if "json_body" in spec:
                kwargs["json"] = spec["json_body"]

            # Warmup
            for _ in range(self.warmup):
                try:
                    self._request(spec["method"], spec["path"], **kwargs)
                except Exception:
                    pass
                bar.update()

            # Measured runs
            for _ in range(self.iterations):
                try:
                    elapsed, status = self._request(spec["method"], spec["path"], **kwargs)
                    lr.samples.append(elapsed)
                    lr.status_codes[status] += 1
                except Exception:
                    lr.errors += 1
                bar.update()

            results.append(lr)

        bar.finish()
        return results

    # ---- block verification throughput ----

    def bench_block_verification(self, block_count: int = 200) -> ThroughputResult:
        """Simulate block verification by hashing synthetic block headers."""
        sys.stderr.write("  Block verification throughput...")
        sys.stderr.flush()

        blocks = []
        for i in range(block_count):
            header = {
                "height": i,
                "prev_hash": hashlib.sha256(str(i).encode()).hexdigest(),
                "timestamp": int(time.time()) - (block_count - i) * 600,
                "miner": f"miner_{i % 10:03d}",
                "nonce": secrets.token_hex(8),
                "tx_root": hashlib.sha256(f"txroot_{i}".encode()).hexdigest(),
                "attestation_count": i % 5,
            }
            blocks.append(header)

        errors = 0
        t0 = time.perf_counter()
        for blk in blocks:
            try:
                raw = json.dumps(blk, sort_keys=True).encode()
                h = hashlib.blake2b(raw, digest_size=32).hexdigest()
                # Verify by re-hashing
                h2 = hashlib.blake2b(raw, digest_size=32).hexdigest()
                if h != h2:
                    errors += 1
                # Simulate prev_hash linkage check
                _ = hashlib.sha256(h.encode()).hexdigest()
            except Exception:
                errors += 1
        elapsed = time.perf_counter() - t0

        sys.stderr.write(f" {block_count / elapsed:.0f} blocks/sec\n")
        sys.stderr.flush()

        return ThroughputResult(
            name="block_verification",
            ops_per_sec=block_count / elapsed if elapsed > 0 else 0,
            total_ops=block_count,
            duration_sec=elapsed,
            errors=errors,
            details={"digest": "blake2b-256", "block_count": block_count},
        )

    # ---- attestation processing ----

    def bench_attestation_processing(self, count: int = 500) -> ThroughputResult:
        """Benchmark attestation challenge/response processing throughput."""
        sys.stderr.write("  Attestation processing throughput...")
        sys.stderr.flush()

        attestations = []
        for i in range(count):
            att = {
                "miner_id": f"bench_miner_{i:04d}",
                "hardware_hash": hashlib.sha256(f"hw_{i}".encode()).hexdigest(),
                "nonce": secrets.token_hex(16),
                "timestamp": int(time.time()),
                "cpu_model": f"Vintage_CPU_{i % 20}",
                "epoch": 100 + (i % 50),
            }
            att["signature"] = hmac.new(
                b"benchkey", json.dumps(att, sort_keys=True).encode(), hashlib.sha256
            ).hexdigest()
            attestations.append(att)

        errors = 0
        t0 = time.perf_counter()
        for att in attestations:
            try:
                payload = json.dumps(att, sort_keys=True).encode()
                expected = hmac.new(b"benchkey", payload, hashlib.sha256).hexdigest()
                if not hmac.compare_digest(att["signature"], expected):
                    errors += 1
                # Simulate hardware hash verification
                _ = hashlib.blake2b(att["hardware_hash"].encode(), digest_size=32).hexdigest()
                # Simulate epoch eligibility check
                _ = att["epoch"] >= 100
            except Exception:
                errors += 1
        elapsed = time.perf_counter() - t0

        sys.stderr.write(f" {count / elapsed:.0f} att/sec\n")
        sys.stderr.flush()

        return ThroughputResult(
            name="attestation_processing",
            ops_per_sec=count / elapsed if elapsed > 0 else 0,
            total_ops=count,
            duration_sec=elapsed,
            errors=errors,
            details={"attestation_count": count},
        )

    # ---- database query performance ----

    def bench_database_queries(self, query_count: int = 1000) -> List[ThroughputResult]:
        """Benchmark SQLite query patterns used by the node."""
        results: List[ThroughputResult] = []

        db_path = self.db_path
        temp_db = False
        if not db_path or not os.path.exists(db_path):
            # Create a temporary DB with realistic schema and seed data
            db_path = _create_bench_db()
            temp_db = True

        sys.stderr.write("  Database query benchmarks...\n")

        queries = [
            (
                "balance_lookup",
                "SELECT miner_pk, balance FROM miners WHERE miner_pk = ?",
                lambda i: (f"miner_{i % 100:04d}",),
            ),
            (
                "epoch_attestations",
                "SELECT * FROM attestations WHERE epoch = ? ORDER BY ts DESC LIMIT 50",
                lambda i: (100 + i % 50,),
            ),
            (
                "miner_list",
                "SELECT miner_pk, balance, last_seen FROM miners ORDER BY balance DESC LIMIT 100",
                lambda _: (),
            ),
            (
                "withdrawal_history",
                "SELECT * FROM withdrawals WHERE miner_pk = ? ORDER BY ts DESC LIMIT 20",
                lambda i: (f"miner_{i % 100:04d}",),
            ),
            (
                "block_by_height",
                "SELECT * FROM blocks WHERE height = ?",
                lambda i: (i % 500,),
            ),
            (
                "recent_transactions",
                "SELECT * FROM transactions ORDER BY ts DESC LIMIT 50",
                lambda _: (),
            ),
        ]

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row

            for name, sql, param_fn in queries:
                errors = 0
                sys.stderr.write(f"    {name}...")
                sys.stderr.flush()

                t0 = time.perf_counter()
                for i in range(query_count):
                    try:
                        conn.execute(sql, param_fn(i)).fetchall()
                    except Exception:
                        errors += 1
                elapsed = time.perf_counter() - t0

                qps = query_count / elapsed if elapsed > 0 else 0
                sys.stderr.write(f" {qps:.0f} qps\n")
                sys.stderr.flush()

                results.append(
                    ThroughputResult(
                        name=f"db_{name}",
                        ops_per_sec=qps,
                        total_ops=query_count,
                        duration_sec=elapsed,
                        errors=errors,
                        details={"query": sql},
                    )
                )

            conn.close()
        finally:
            if temp_db and db_path and os.path.exists(db_path):
                os.unlink(db_path)

        return results

    # ---- concurrent connections ----

    def bench_concurrency(self, requests_per_level: int = 200) -> List[ConcurrencyResult]:
        """Benchmark concurrent connection handling at various levels."""
        results: List[ConcurrencyResult] = []
        endpoint = "/health"

        bar = ProgressBar(
            sum(requests_per_level for _ in self.concurrency_levels),
            "Concurrency",
        )

        for level in self.concurrency_levels:
            latencies: List[float] = []
            failed = 0
            lock = threading.Lock()

            def _worker():
                nonlocal failed
                try:
                    el, status = self._request("GET", endpoint)
                    with lock:
                        latencies.append(el)
                        if status >= 500:
                            failed += 1
                except Exception:
                    with lock:
                        failed += 1
                bar.update()

            t0 = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=level) as pool:
                futures = [pool.submit(_worker) for _ in range(requests_per_level)]
                concurrent.futures.wait(futures)
            elapsed = time.perf_counter() - t0

            results.append(
                ConcurrencyResult(
                    concurrency_level=level,
                    total_requests=requests_per_level,
                    successful=len(latencies),
                    failed=failed,
                    duration_sec=elapsed,
                    rps=len(latencies) / elapsed if elapsed > 0 else 0,
                    mean_latency_ms=statistics.mean(latencies) if latencies else 0,
                    p95_latency_ms=_pct(latencies, 95),
                    p99_latency_ms=_pct(latencies, 99),
                )
            )

        bar.finish()
        return results

    # ---- full run ----

    def run(self) -> BenchmarkReport:
        """Execute the full benchmark suite and return a report."""
        suite_start = time.perf_counter()
        report = BenchmarkReport(
            timestamp=_ts(),
            host=self.host,
            iterations=self.iterations,
        )

        # Detect node version
        try:
            _, status = self._request("GET", "/api/stats")
            if status == 200:
                resp = self.session.get(urljoin(self.host + "/", "/api/stats"), timeout=5)
                data = resp.json()
                report.node_version = data.get("version", "unknown")
        except Exception:
            report.node_version = "unreachable"

        # Collect system info
        report.system_info = _collect_system_info()

        print(f"\nRustChain Benchmark Suite")
        print(f"{'=' * 50}")
        print(f"Host:       {self.host}")
        print(f"Iterations: {self.iterations}")
        print(f"Warmup:     {self.warmup}")
        print(f"Timestamp:  {report.timestamp}")
        print(f"Node:       {report.node_version}")
        print()

        # 1) Endpoint latency
        print("[1/5] Endpoint latency benchmarks")
        latency_results = self.bench_endpoint_latency()
        report.latency = [lr.to_dict() for lr in latency_results]

        # 2) Block verification
        print("[2/5] Block verification throughput")
        block_result = self.bench_block_verification()
        report.throughput.append(block_result.to_dict())

        # 3) Attestation processing
        print("[3/5] Attestation processing throughput")
        att_result = self.bench_attestation_processing()
        report.throughput.append(att_result.to_dict())

        # 4) Database queries
        print("[4/5] Database query performance")
        db_results = self.bench_database_queries()
        report.database = [r.to_dict() for r in db_results]

        # 5) Concurrency
        print("[5/5] Concurrent connection handling")
        conc_results = self.bench_concurrency()
        report.concurrency = [c.to_dict() for c in conc_results]

        report.duration_sec = time.perf_counter() - suite_start
        print(f"\nBenchmark complete in {report.duration_sec:.1f}s")
        return report


# ---------------------------------------------------------------------------
# Temporary benchmark database
# ---------------------------------------------------------------------------

def _create_bench_db() -> str:
    """Create a temporary SQLite database with realistic schema and seed data."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="rustchain_bench_")
    os.close(fd)
    conn = sqlite3.connect(path)

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS miners (
            miner_pk TEXT PRIMARY KEY,
            balance REAL DEFAULT 0,
            last_seen INTEGER,
            cpu_model TEXT,
            hw_hash TEXT,
            enrolled_epoch INTEGER
        );
        CREATE TABLE IF NOT EXISTS attestations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            miner_pk TEXT,
            epoch INTEGER,
            hw_hash TEXT,
            nonce TEXT,
            ts INTEGER,
            valid INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            miner_pk TEXT,
            amount REAL,
            status TEXT DEFAULT 'pending',
            ts INTEGER,
            tx_hash TEXT
        );
        CREATE TABLE IF NOT EXISTS blocks (
            height INTEGER PRIMARY KEY,
            hash TEXT,
            prev_hash TEXT,
            miner TEXT,
            ts INTEGER,
            tx_count INTEGER
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_pk TEXT,
            to_pk TEXT,
            amount REAL,
            ts INTEGER,
            block_height INTEGER,
            tx_hash TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_att_epoch ON attestations(epoch);
        CREATE INDEX IF NOT EXISTS idx_att_miner ON attestations(miner_pk);
        CREATE INDEX IF NOT EXISTS idx_wd_miner ON withdrawals(miner_pk);
        CREATE INDEX IF NOT EXISTS idx_tx_ts ON transactions(ts);
        CREATE INDEX IF NOT EXISTS idx_blocks_hash ON blocks(hash);
    """)

    now = int(time.time())
    # Seed miners
    miners = [(f"miner_{i:04d}", 100.0 + i * 0.5, now - i * 60, f"CPU_{i % 20}", hashlib.sha256(f"hw{i}".encode()).hexdigest(), 100 + i % 50) for i in range(200)]
    conn.executemany("INSERT OR IGNORE INTO miners VALUES (?,?,?,?,?,?)", miners)

    # Seed attestations
    atts = [(f"miner_{i % 200:04d}", 100 + (i % 50), hashlib.sha256(f"hw{i}".encode()).hexdigest(), secrets.token_hex(8), now - i * 30, 1) for i in range(2000)]
    conn.executemany("INSERT INTO attestations (miner_pk, epoch, hw_hash, nonce, ts, valid) VALUES (?,?,?,?,?,?)", atts)

    # Seed blocks
    blocks = [(i, hashlib.sha256(f"block{i}".encode()).hexdigest(), hashlib.sha256(f"block{i-1}".encode()).hexdigest(), f"miner_{i % 200:04d}", now - (500 - i) * 600, i % 10) for i in range(500)]
    conn.executemany("INSERT OR IGNORE INTO blocks VALUES (?,?,?,?,?,?)", blocks)

    # Seed withdrawals
    wds = [(f"miner_{i % 200:04d}", 0.5 + (i % 10) * 0.1, "completed" if i % 3 else "pending", now - i * 120, hashlib.sha256(f"wd{i}".encode()).hexdigest()) for i in range(500)]
    conn.executemany("INSERT INTO withdrawals (miner_pk, amount, status, ts, tx_hash) VALUES (?,?,?,?,?)", wds)

    # Seed transactions
    txs = [(f"miner_{i % 200:04d}", f"miner_{(i + 1) % 200:04d}", 0.1 + (i % 100) * 0.01, now - i * 60, i % 500, hashlib.sha256(f"tx{i}".encode()).hexdigest()) for i in range(2000)]
    conn.executemany("INSERT INTO transactions (from_pk, to_pk, amount, ts, block_height, tx_hash) VALUES (?,?,?,?,?,?)", txs)

    conn.commit()
    conn.close()
    return path


# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------

def _collect_system_info() -> Dict[str, Any]:
    import platform
    info: Dict[str, Any] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor(),
        "machine": platform.machine(),
    }
    try:
        info["cpu_count"] = os.cpu_count()
    except Exception:
        pass
    return info


# ---------------------------------------------------------------------------
# Comparison mode
# ---------------------------------------------------------------------------

def compare_results(before_path: str, after_path: str) -> Dict[str, Any]:
    """Compare two benchmark result files and produce a delta report."""
    with open(before_path) as f:
        before = json.load(f)
    with open(after_path) as f:
        after = json.load(f)

    comparison: Dict[str, Any] = {
        "before": {"file": before_path, "timestamp": before.get("timestamp")},
        "after": {"file": after_path, "timestamp": after.get("timestamp")},
        "latency_deltas": [],
        "throughput_deltas": [],
        "concurrency_deltas": [],
        "database_deltas": [],
    }

    # Build lookup maps
    before_lat = {e["endpoint"]: e for e in before.get("latency", [])}
    after_lat = {e["endpoint"]: e for e in after.get("latency", [])}

    for ep in sorted(set(before_lat) | set(after_lat)):
        b = before_lat.get(ep, {})
        a = after_lat.get(ep, {})
        delta: Dict[str, Any] = {"endpoint": ep}
        for metric in ("p50_ms", "p95_ms", "p99_ms", "mean_ms"):
            bv = b.get(metric, 0)
            av = a.get(metric, 0)
            change_pct = ((av - bv) / bv * 100) if bv else 0
            delta[metric] = {"before": bv, "after": av, "change_pct": round(change_pct, 2)}
        comparison["latency_deltas"].append(delta)

    before_tp = {e["name"]: e for e in before.get("throughput", [])}
    after_tp = {e["name"]: e for e in after.get("throughput", [])}
    for name in sorted(set(before_tp) | set(after_tp)):
        b = before_tp.get(name, {})
        a = after_tp.get(name, {})
        bv = b.get("ops_per_sec", 0)
        av = a.get("ops_per_sec", 0)
        change_pct = ((av - bv) / bv * 100) if bv else 0
        comparison["throughput_deltas"].append({
            "name": name,
            "before_ops": bv,
            "after_ops": av,
            "change_pct": round(change_pct, 2),
        })

    before_conc = {e["concurrency"]: e for e in before.get("concurrency", [])}
    after_conc = {e["concurrency"]: e for e in after.get("concurrency", [])}
    for level in sorted(set(before_conc) | set(after_conc)):
        b = before_conc.get(level, {})
        a = after_conc.get(level, {})
        bv = b.get("rps", 0)
        av = a.get("rps", 0)
        change_pct = ((av - bv) / bv * 100) if bv else 0
        comparison["concurrency_deltas"].append({
            "concurrency": level,
            "before_rps": bv,
            "after_rps": av,
            "change_pct": round(change_pct, 2),
        })

    before_db = {e["name"]: e for e in before.get("database", [])}
    after_db = {e["name"]: e for e in after.get("database", [])}
    for name in sorted(set(before_db) | set(after_db)):
        b = before_db.get(name, {})
        a = after_db.get(name, {})
        bv = b.get("ops_per_sec", 0)
        av = a.get("ops_per_sec", 0)
        change_pct = ((av - bv) / bv * 100) if bv else 0
        comparison["database_deltas"].append({
            "name": name,
            "before_qps": bv,
            "after_qps": av,
            "change_pct": round(change_pct, 2),
        })

    return comparison


# ---------------------------------------------------------------------------
# HTML report generation
# ---------------------------------------------------------------------------

def generate_html_report(report_data: Dict, comparison_data: Optional[Dict] = None) -> str:
    """Generate an HTML report with embedded Chart.js visualizations."""

    latency = report_data.get("latency", [])
    throughput = report_data.get("throughput", [])
    concurrency = report_data.get("concurrency", [])
    database = report_data.get("database", [])

    # Prepare chart data
    lat_labels = json.dumps([e["endpoint"] for e in latency])
    lat_p50 = json.dumps([e["p50_ms"] for e in latency])
    lat_p95 = json.dumps([e["p95_ms"] for e in latency])
    lat_p99 = json.dumps([e["p99_ms"] for e in latency])

    tp_labels = json.dumps([e["name"] for e in throughput])
    tp_values = json.dumps([e["ops_per_sec"] for e in throughput])

    conc_labels = json.dumps([e["concurrency"] for e in concurrency])
    conc_rps = json.dumps([e["rps"] for e in concurrency])
    conc_p95 = json.dumps([e["p95_latency_ms"] for e in concurrency])

    db_labels = json.dumps([e["name"].replace("db_", "") for e in database])
    db_qps = json.dumps([e["ops_per_sec"] for e in database])

    # Build latency table rows
    lat_rows = ""
    for e in latency:
        error_badge = f'<span class="badge error">{e["errors"]}</span>' if e["errors"] else ""
        lat_rows += f"""
        <tr>
            <td><code>{e["method"]}</code></td>
            <td><code>{e["endpoint"]}</code></td>
            <td>{e["category"]}</td>
            <td>{e["p50_ms"]:.2f}</td>
            <td>{e["p95_ms"]:.2f}</td>
            <td>{e["p99_ms"]:.2f}</td>
            <td>{e["mean_ms"]:.2f}</td>
            <td>{e["count"]}</td>
            <td>{error_badge}</td>
        </tr>"""

    # Throughput table
    tp_rows = ""
    for e in throughput:
        tp_rows += f"""
        <tr>
            <td>{e["name"]}</td>
            <td>{e["ops_per_sec"]:.1f}</td>
            <td>{e["total_ops"]}</td>
            <td>{e["duration_sec"]:.3f}</td>
            <td>{e["errors"]}</td>
        </tr>"""

    # Concurrency table
    conc_rows = ""
    for e in concurrency:
        conc_rows += f"""
        <tr>
            <td>{e["concurrency"]}</td>
            <td>{e["rps"]:.1f}</td>
            <td>{e["successful"]}</td>
            <td>{e["failed"]}</td>
            <td>{e["mean_latency_ms"]:.2f}</td>
            <td>{e["p95_latency_ms"]:.2f}</td>
            <td>{e["p99_latency_ms"]:.2f}</td>
        </tr>"""

    # Database table
    db_rows = ""
    for e in database:
        db_rows += f"""
        <tr>
            <td>{e["name"]}</td>
            <td>{e["ops_per_sec"]:.1f}</td>
            <td>{e["total_ops"]}</td>
            <td>{e["duration_sec"]:.4f}</td>
            <td>{e["errors"]}</td>
        </tr>"""

    # Comparison section
    comparison_html = ""
    if comparison_data:
        comparison_html = _build_comparison_html(comparison_data)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RustChain Benchmark Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #c9d1d9; --text-muted: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --red: #f85149; --yellow: #d29922;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
         background: var(--bg); color: var(--text); padding: 2rem; }}
  h1 {{ color: var(--accent); margin-bottom: 0.5rem; }}
  h2 {{ color: var(--text); margin: 2rem 0 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
  .meta {{ color: var(--text-muted); margin-bottom: 2rem; font-size: 0.9rem; }}
  .meta span {{ margin-right: 2rem; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; }}
  .card-full {{ grid-column: 1 / -1; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 0.75rem; }}
  code {{ background: #1c2128; padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }}
  .badge {{ padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }}
  .badge.error {{ background: #f8514922; color: var(--red); }}
  .badge.improved {{ background: #3fb95022; color: var(--green); }}
  .badge.regressed {{ background: #f8514922; color: var(--red); }}
  canvas {{ max-height: 400px; }}
  @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>

<h1>RustChain Benchmark Report</h1>
<div class="meta">
  <span>Timestamp: {report_data.get("timestamp", "N/A")}</span>
  <span>Host: {report_data.get("host", "N/A")}</span>
  <span>Node: {report_data.get("node_version", "N/A")}</span>
  <span>Iterations: {report_data.get("iterations", "N/A")}</span>
  <span>Duration: {report_data.get("duration_sec", 0):.1f}s</span>
</div>

<h2>API Endpoint Latency</h2>
<div class="grid">
  <div class="card card-full">
    <canvas id="latencyChart"></canvas>
  </div>
  <div class="card card-full">
    <table>
      <thead>
        <tr><th>Method</th><th>Endpoint</th><th>Category</th><th>p50 (ms)</th><th>p95 (ms)</th><th>p99 (ms)</th><th>Mean (ms)</th><th>Count</th><th>Errors</th></tr>
      </thead>
      <tbody>{lat_rows}</tbody>
    </table>
  </div>
</div>

<h2>Throughput</h2>
<div class="grid">
  <div class="card">
    <canvas id="throughputChart"></canvas>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>Benchmark</th><th>Ops/sec</th><th>Total</th><th>Duration (s)</th><th>Errors</th></tr></thead>
      <tbody>{tp_rows}</tbody>
    </table>
  </div>
</div>

<h2>Concurrent Connections</h2>
<div class="grid">
  <div class="card">
    <canvas id="concurrencyChart"></canvas>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>Concurrency</th><th>RPS</th><th>OK</th><th>Failed</th><th>Mean (ms)</th><th>p95 (ms)</th><th>p99 (ms)</th></tr></thead>
      <tbody>{conc_rows}</tbody>
    </table>
  </div>
</div>

<h2>Database Query Performance</h2>
<div class="grid">
  <div class="card">
    <canvas id="dbChart"></canvas>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>Query</th><th>QPS</th><th>Total</th><th>Duration (s)</th><th>Errors</th></tr></thead>
      <tbody>{db_rows}</tbody>
    </table>
  </div>
</div>

{comparison_html}

<script>
const chartDefaults = {{
  responsive: true,
  maintainAspectRatio: true,
  plugins: {{ legend: {{ labels: {{ color: '#c9d1d9' }} }} }},
  scales: {{
    x: {{ ticks: {{ color: '#8b949e', maxRotation: 45 }}, grid: {{ color: '#30363d' }} }},
    y: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#30363d' }} }}
  }}
}};

// Latency chart
new Chart(document.getElementById('latencyChart'), {{
  type: 'bar',
  data: {{
    labels: {lat_labels},
    datasets: [
      {{ label: 'p50 (ms)', data: {lat_p50}, backgroundColor: '#58a6ff88' }},
      {{ label: 'p95 (ms)', data: {lat_p95}, backgroundColor: '#d2992288' }},
      {{ label: 'p99 (ms)', data: {lat_p99}, backgroundColor: '#f8514988' }},
    ]
  }},
  options: {{ ...chartDefaults, plugins: {{ ...chartDefaults.plugins, title: {{ display: true, text: 'Endpoint Latency Distribution', color: '#c9d1d9' }} }} }}
}});

// Throughput chart
new Chart(document.getElementById('throughputChart'), {{
  type: 'bar',
  data: {{
    labels: {tp_labels},
    datasets: [{{ label: 'Ops/sec', data: {tp_values}, backgroundColor: '#3fb95088' }}]
  }},
  options: {{ ...chartDefaults, indexAxis: 'y' }}
}});

// Concurrency chart (dual axis)
new Chart(document.getElementById('concurrencyChart'), {{
  type: 'line',
  data: {{
    labels: {conc_labels},
    datasets: [
      {{ label: 'RPS', data: {conc_rps}, borderColor: '#58a6ff', yAxisID: 'y' }},
      {{ label: 'p95 Latency (ms)', data: {conc_p95}, borderColor: '#d29922', yAxisID: 'y1' }},
    ]
  }},
  options: {{
    ...chartDefaults,
    scales: {{
      ...chartDefaults.scales,
      y: {{ ...chartDefaults.scales.y, position: 'left', title: {{ display: true, text: 'RPS', color: '#8b949e' }} }},
      y1: {{ position: 'right', ticks: {{ color: '#8b949e' }}, grid: {{ drawOnChartArea: false }}, title: {{ display: true, text: 'Latency (ms)', color: '#8b949e' }} }}
    }}
  }}
}});

// Database chart
new Chart(document.getElementById('dbChart'), {{
  type: 'bar',
  data: {{
    labels: {db_labels},
    datasets: [{{ label: 'Queries/sec', data: {db_qps}, backgroundColor: '#a371f788' }}]
  }},
  options: chartDefaults
}});
</script>
</body>
</html>"""
    return html


def _build_comparison_html(comp: Dict) -> str:
    """Build the comparison section of the HTML report."""
    rows = ""
    for d in comp.get("latency_deltas", []):
        for metric in ("p50_ms", "p95_ms", "p99_ms", "mean_ms"):
            info = d.get(metric, {})
            pct = info.get("change_pct", 0)
            cls = "improved" if pct < -2 else ("regressed" if pct > 2 else "")
            badge = f'<span class="badge {cls}">{pct:+.1f}%</span>' if cls else f"{pct:+.1f}%"
            rows += f"""
            <tr>
                <td><code>{d["endpoint"]}</code></td>
                <td>{metric.replace("_ms","")}</td>
                <td>{info.get("before", 0):.2f}</td>
                <td>{info.get("after", 0):.2f}</td>
                <td>{badge}</td>
            </tr>"""

    return f"""
    <h2>Comparison: Before vs After</h2>
    <div class="grid">
      <div class="card card-full">
        <table>
          <thead><tr><th>Endpoint</th><th>Metric</th><th>Before (ms)</th><th>After (ms)</th><th>Change</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="RustChain Node Performance Benchmarking Suite"
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Node base URL")
    parser.add_argument("--iterations", "-n", type=int, default=DEFAULT_ITERATIONS, help="Requests per endpoint")
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP, help="Warmup requests per endpoint")
    parser.add_argument("--output", "-o", default=".", help="Output directory for results")
    parser.add_argument("--db", default=None, help="Path to node SQLite database (optional)")
    parser.add_argument("--admin-key", default=None, help="Admin API key (or RC_ADMIN_KEY env var)")
    parser.add_argument("--concurrency", type=str, default=None, help="Comma-separated concurrency levels (e.g. 1,5,10,25)")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"), help="Compare two result JSON files")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    # Comparison mode
    if args.compare:
        comp = compare_results(args.compare[0], args.compare[1])
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        comp_json = out_dir / "comparison.json"
        comp_json.write_text(json.dumps(comp, indent=2))
        print(f"Comparison JSON: {comp_json}")

        # Generate comparison HTML
        # Load the 'after' data as base report
        with open(args.compare[1]) as f:
            after_data = json.load(f)
        html = generate_html_report(after_data, comparison_data=comp)
        comp_html = out_dir / "comparison.html"
        comp_html.write_text(html)
        print(f"Comparison HTML: {comp_html}")
        return

    conc_levels = None
    if args.concurrency:
        conc_levels = [int(x.strip()) for x in args.concurrency.split(",")]

    bench = RustChainBenchmark(
        host=args.host,
        iterations=args.iterations,
        warmup=args.warmup,
        concurrency_levels=conc_levels,
        db_path=args.db,
        admin_key=args.admin_key,
        verbose=args.verbose,
    )

    report = bench.run()
    report_dict = report.to_dict()

    # Write outputs
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"bench_{ts_slug}.json"
    html_path = out_dir / f"bench_{ts_slug}.html"

    json_path.write_text(json.dumps(report_dict, indent=2))
    print(f"\nJSON results: {json_path}")

    html_content = generate_html_report(report_dict)
    html_path.write_text(html_content)
    print(f"HTML report:  {html_path}")

    # Print summary table
    print(f"\n{'Endpoint':<35} {'p50':>8} {'p95':>8} {'p99':>8} {'Err':>5}")
    print("-" * 70)
    for e in report_dict["latency"]:
        err_str = str(e["errors"]) if e["errors"] else ""
        print(f"{e['endpoint']:<35} {e['p50_ms']:>7.1f}ms {e['p95_ms']:>7.1f}ms {e['p99_ms']:>7.1f}ms {err_str:>5}")


if __name__ == "__main__":
    main()
