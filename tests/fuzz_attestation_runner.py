#!/usr/bin/env python3
"""
RustChain Attestation Fuzz Runner
==================================
Practical fuzz testing harness for POST /attest/submit endpoint.
Generates adversarial payloads, manages regression corpus, and verifies crash fixes.

Features:
- Property-based fuzzing with multiple mutation strategies
- Corpus management (save, load, replay, deduplicate)
- Regression testing against known crash cases
- CI/CD integration with exit codes
- Coverage-guided corpus minimization

Usage:
    python3 fuzz_attestation_runner.py              # Run 1000 iterations
    python3 fuzz_attestation_runner.py --count 5000 # Run 5000 iterations
    python3 fuzz_attestation_runner.py --ci         # CI mode (exit 1 on crash)
    python3 fuzz_attestation_runner.py --save-corpus # Save interesting cases
    python3 fuzz_attestation_runner.py --replay     # Replay saved corpus
    python3 fuzz_attestation_runner.py --minimize   # Minimize corpus size
    python3 fuzz_attestation_runner.py --report     # Show crash report

Bounty: https://github.com/Scottcjn/rustchain-bounties/issues/475
"""

import argparse
import hashlib
import json
import os
import random
import ssl
import string
import sys
import time
import urllib.request
import urllib.error
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_TARGET_URL = os.environ.get("RUSTCHAIN_URL", "http://localhost:5000")
CORPUS_DIR = Path(__file__).parent / "attestation_corpus"
CRASH_CORPUS_DIR = Path(__file__).parent / "attestation_crash_corpus"
CRASH_REPORT = Path(__file__).parent / "fuzz_crashes.json"
FUZZ_STATS_FILE = Path(__file__).parent / "fuzz_stats.json"

TIMEOUT = 10
DEFAULT_ITERATIONS = 1000

# Known test values for realistic payloads
KNOWN_WALLETS = [
    "nox-ventures", "test-miner", "alice", "bob",
    "founder_community", "fuzz-miner", "power8-miner",
    "x86_64-miner", "arm64-miner", "vintage-miner"
]

KNOWN_ARCHS = ["modern", "vintage", "ppc", "arm64", "x86_64", "power8", "power9"]
KNOWN_FAMILIES = ["x86_64", "aarch64", "ppc64", "arm64", "i686", "PowerPC"]
KNOWN_CPUS = [
    "AMD Ryzen 5 5600X", "Intel Core i7-9700K", "IBM POWER8",
    "ARM Cortex-A72", "Apple M1", "Vintage CPU"
]


# ---------------------------------------------------------------------------
# Baseline Valid Payload
# ---------------------------------------------------------------------------

def _make_nonce(wallet: str) -> str:
    """Generate a plausible attestation nonce."""
    data = f"{wallet}:{int(time.time())}:{random.randint(0, 1 << 32)}".encode()
    return hashlib.sha256(data).hexdigest()


def baseline_payload(wallet: str = "test-miner") -> dict:
    """Generate a structurally valid attestation payload."""
    return {
        "miner": wallet,
        "miner_id": hashlib.sha256(wallet.encode()).hexdigest()[:16],
        "nonce": _make_nonce(wallet),
        "device": {
            "model": random.choice(KNOWN_CPUS),
            "arch": random.choice(KNOWN_ARCHS),
            "family": random.choice(KNOWN_FAMILIES),
            "cores": random.randint(4, 16),
            "cpu_serial": hashlib.md5(wallet.encode(), usedforsecurity=False).hexdigest(),
            "device_id": f"{secrets.token_hex(8)}-{secrets.token_hex(4)}-{secrets.token_hex(4)}-{secrets.token_hex(4)}-{secrets.token_hex(12)}",
            "serial_number": f"SERIAL-{random.randint(1000, 9999)}",
        },
        "signals": {
            "macs": [f"aa:bb:cc:dd:ee:{random.randint(0, 255):02x}"],
            "hostname": f"{wallet}-host",
        },
        "report": {
            "nonce": _make_nonce(wallet),
            "commitment": hashlib.sha256(f"{wallet}:{time.time()}".encode()).hexdigest(),
        },
        "fingerprint": {
            "all_passed": True,
            "checks": {
                "clock_drift": {
                    "passed": True,
                    "data": {"cv": 0.092, "samples": 1000}
                },
                "cache_timing": {
                    "passed": True,
                    "data": {"profile": [1.2, 3.4, 5.6]}
                },
                "simd_identity": {
                    "passed": True,
                    "data": {}
                },
                "thermal_drift": {
                    "passed": True,
                    "data": {}
                },
                "instruction_jitter": {
                    "passed": True,
                    "data": {}
                },
                "anti_emulation": {
                    "passed": True,
                    "data": {"vm_indicators": []}
                },
            },
        },
    }


# Import secrets for UUID generation
import secrets


# ---------------------------------------------------------------------------
# Mutation Strategies
# ---------------------------------------------------------------------------

def rand_str(length: int, charset: str = string.printable) -> str:
    """Generate random string of specified length."""
    return "".join(random.choices(charset, k=length))


def rand_unicode() -> str:
    """Generate unicode edge cases."""
    edge_cases = [
        "\x00",                          # null byte
        "\u202e" + "malicious",           # RTL override
        "💀" * random.randint(1, 100),    # emoji
        "A" * random.randint(100, 1_000_000),  # long string
        "\uffff",                          # non-character
        "café",                            # unicode
        "日本語",                           # CJK
        "\r\n\r\n",                        # CRLF injection
        "../../../etc/passwd",             # path traversal
        "'; DROP TABLE miners; --",        # SQL injection
        "<script>alert(1)</script>",       # XSS
        "%00%00%00",                       # URL-encoded nulls
    ]
    return random.choice(edge_cases)


def mutate_value(v: Any) -> Any:
    """Randomly mutate a value to an unexpected type or value."""
    strategies = [
        lambda: None,
        lambda: "",
        lambda: 0,
        lambda: -1,
        lambda: 2**31 - 1,
        lambda: 2**63,
        lambda: -2**63,
        lambda: 3.14,
        lambda: float("inf"),
        lambda: float("nan"),
        lambda: True,
        lambda: False,
        lambda: [],
        lambda: {},
        lambda: [1, 2, 3],
        lambda: {"nested": {"deep": "value"}},
        lambda: rand_str(1),
        lambda: rand_str(1024),
        lambda: rand_str(65536),
        lambda: rand_unicode(),
        lambda: [rand_str(10) for _ in range(100)],
        lambda: "\x00" * 1000,
    ]
    return random.choice(strategies)()


def mutate_missing_field(payload: dict, key_path: List[str]) -> dict:
    """Remove a field from the payload."""
    p = deepcopy(payload)
    obj = p
    for k in key_path[:-1]:
        obj = obj.get(k, {})
        if not isinstance(obj, dict):
            return p
    obj.pop(key_path[-1], None)
    return p


def mutate_wrong_type(payload: dict, key_path: List[str]) -> dict:
    """Replace a field with a wrong type."""
    p = deepcopy(payload)
    obj = p
    for k in key_path[:-1]:
        if k not in obj:
            obj[k] = {}
        obj = obj[k]
        if not isinstance(obj, dict):
            return p
    obj[key_path[-1]] = mutate_value(obj.get(key_path[-1]))
    return p


def mutate_add_unknown_field(payload: dict) -> dict:
    """Add unexpected fields at various levels."""
    p = deepcopy(payload)
    injection_key = rand_str(random.randint(1, 50))
    injection_val = mutate_value(None)
    target = random.choice([p, p.get("device", {}), p.get("signals", {}), p.get("fingerprint", {}), p.get("report", {})])
    if isinstance(target, dict):
        target[injection_key] = injection_val
    return p


def mutate_nested_bomb(payload: dict) -> dict:
    """Create deeply nested structures (JSON bomb)."""
    p = deepcopy(payload)
    deep = {}
    current = deep
    for _ in range(random.randint(100, 500)):
        current["x"] = {}
        current = current["x"]
    if "device" in p and isinstance(p["device"], dict):
        p["device"]["model"] = deep
    return p


def mutate_array_overflow(payload: dict) -> dict:
    """Make arrays very large."""
    p = deepcopy(payload)
    if "signals" in p and isinstance(p["signals"], dict):
        p["signals"]["macs"] = [f"aa:bb:cc:dd:ee:{i:02x}" for i in range(random.randint(1000, 10000))]
    return p


def mutate_float_checks(payload: dict) -> dict:
    """Use edge-case float values in fingerprint data."""
    p = deepcopy(payload)
    edge_floats = [float("inf"), float("-inf"), float("nan"), 1e308, -1e308, 1e-308, 0.0, -0.0]
    
    if "fingerprint" in p and isinstance(p["fingerprint"], dict):
        checks = p["fingerprint"].get("checks", {})
        if isinstance(checks, dict):
            if "clock_drift" in checks and isinstance(checks["clock_drift"], dict):
                data = checks["clock_drift"].get("data", {})
                if isinstance(data, dict):
                    data["cv"] = random.choice(edge_floats)
            if "cache_timing" in checks and isinstance(checks["cache_timing"], dict):
                data = checks["cache_timing"].get("data", {})
                if isinstance(data, dict):
                    data["profile"] = [random.choice(edge_floats)] * random.randint(10, 100)
    return p


def mutate_unicode_fields(payload: dict) -> dict:
    """Inject unicode edge cases into string fields."""
    p = deepcopy(payload)
    field_targets = [
        (["miner"],),
        (["device", "model"],),
        (["device", "cpu_serial"],),
        (["signals", "hostname"],),
    ]
    for path in random.sample(field_targets, min(2, len(field_targets))):
        obj = p
        for k in path[:-1]:
            if k not in obj or not isinstance(obj[k], dict):
                break
            obj = obj[k]
        if path[-1] in obj and isinstance(obj[path[-1]], str):
            obj[path[-1]] = rand_unicode()
    return p


def mutate_size_extremes(payload: dict) -> dict:
    """Test size extremes - very large or empty strings."""
    p = deepcopy(payload)
    size_choice = random.choice(["empty", "huge", "max"])
    
    if size_choice == "empty":
        if "miner" in p:
            p["miner"] = ""
    elif size_choice == "huge":
        if "miner" in p:
            p["miner"] = "x" * random.randint(10_000, 1_000_000)
    elif size_choice == "max":
        if "miner" in p:
            p["miner"] = "x" * 128  # Right at the limit
    return p


def mutate_sql_injection(payload: dict) -> dict:
    """Inject SQL injection attempts."""
    p = deepcopy(payload)
    sql_payloads = [
        "'; DROP TABLE miners; --",
        "' OR '1'='1",
        "'; DELETE FROM balances; --",
        "1; SELECT * FROM miners",
        "admin'--",
    ]
    if "miner" in p:
        p["miner"] = random.choice(sql_payloads)
    return p


def mutate_xss_attempts(payload: dict) -> dict:
    """Inject XSS attempts."""
    p = deepcopy(payload)
    xss_payloads = [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(1)",
        "<svg onload=alert(1)>",
    ]
    field_targets = [["miner"], ["signals", "hostname"], ["device", "model"]]
    for path in random.sample(field_targets, 1):
        obj = p
        for k in path[:-1]:
            if k not in obj or not isinstance(obj[k], dict):
                break
            obj = obj[k]
        if path[-1] in obj:
            obj[path[-1]] = random.choice(xss_payloads)
    return p


# Key paths for targeted mutations
KEY_PATHS = [
    ["miner"],
    ["miner_id"],
    ["nonce"],
    ["device"],
    ["device", "model"],
    ["device", "arch"],
    ["device", "family"],
    ["device", "cores"],
    ["device", "cpu_serial"],
    ["device", "device_id"],
    ["device", "serial_number"],
    ["signals"],
    ["signals", "macs"],
    ["signals", "hostname"],
    ["report"],
    ["report", "nonce"],
    ["report", "commitment"],
    ["fingerprint"],
    ["fingerprint", "all_passed"],
    ["fingerprint", "checks"],
]

MUTATORS = [
    ("missing_field", lambda p: mutate_missing_field(p, random.choice(KEY_PATHS))),
    ("wrong_type", lambda p: mutate_wrong_type(p, random.choice(KEY_PATHS))),
    ("unknown_field", mutate_add_unknown_field),
    ("nested_bomb", mutate_nested_bomb),
    ("array_overflow", mutate_array_overflow),
    ("float_edge", mutate_float_checks),
    ("unicode_inject", mutate_unicode_fields),
    ("size_extremes", mutate_size_extremes),
    ("sql_injection", mutate_sql_injection),
    ("xss_attempt", mutate_xss_attempts),
    ("unicode_miner", lambda p: {**p, "miner": rand_unicode()}),
    ("huge_miner", lambda p: {**p, "miner": "x" * random.randint(10_000, 1_000_000)}),
    ("null_miner", lambda p: {**p, "miner": None}),
    ("empty_payload", lambda _: {}),
    ("not_json", None),  # handled specially
]


# ---------------------------------------------------------------------------
# HTTP Client
# ---------------------------------------------------------------------------

@dataclass
class FuzzResult:
    """Result of a single fuzz iteration."""
    iteration: int
    mutator: str
    payload: Any
    status_code: Optional[int]
    response_body: str
    elapsed_ms: float
    is_crash: bool
    is_interesting: bool
    crash_detail: str = ""
    coverage_hash: str = ""


def send_payload(payload: Any, target_url: str, is_raw: bool = False) -> Tuple[Optional[int], str, float]:
    """Send a payload to the attestation endpoint."""
    endpoint = f"{target_url}/attest/submit"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    if is_raw:
        body = rand_str(random.randint(1, 10000)).encode()
        content_type = random.choice(["text/plain", "application/xml", "multipart/form-data", ""])
    else:
        try:
            body = json.dumps(payload, default=str).encode()
        except (TypeError, ValueError, RecursionError):
            body = b"{}"
        content_type = "application/json"

    req = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": content_type,
            "User-Agent": "rustchain-fuzz/1.0",
        }
    )

    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:  # nosec B310
            elapsed = (time.monotonic() - start) * 1000
            return r.status, r.read().decode("utf-8", errors="replace")[:2000], elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.monotonic() - start) * 1000
        try:
            return e.code, e.read().decode("utf-8", errors="replace")[:2000], elapsed
        except:
            return e.code, str(e), elapsed
    except urllib.error.URLError as e:
        elapsed = (time.monotonic() - start) * 1000
        return None, str(e), elapsed
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return None, f"EXCEPTION: {type(e).__name__}: {e}", elapsed


def classify_crash(status_code: Optional[int], response: str, elapsed_ms: float) -> Tuple[bool, str]:
    """Determine if a response indicates a crash or vulnerability."""
    # 5xx = server error (potential crash)
    if status_code and status_code >= 500:
        return True, f"HTTP {status_code} server error"

    # Timeout = potential DoS
    if elapsed_ms > (TIMEOUT * 1000 * 0.9):
        return True, f"Timeout ({elapsed_ms:.0f}ms)"

    # Exception traceback in response
    if any(kw in response for kw in ["Traceback", "Exception", "Error at", "Internal Server Error"]):
        return True, "Traceback/exception in response body"

    # Connection error (unexpected — server should be up)
    if status_code is None and "Connection refused" in response:
        return True, "Connection refused (server crash?)"

    return False, ""


def compute_coverage_hash(status_code: Optional[int], response: str) -> str:
    """Compute a hash of the response for coverage tracking."""
    data = f"{status_code}:{response[:500]}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def is_interesting(payload: Any, status_code: Optional[int], coverage_hash: str, seen_hashes: set) -> bool:
    """Determine if this result is interesting (new coverage or crash)."""
    if status_code and status_code >= 500:
        return True
    if coverage_hash not in seen_hashes:
        return True
    return False


# ---------------------------------------------------------------------------
# Corpus Management
# ---------------------------------------------------------------------------

def save_to_corpus(result: FuzzResult, corpus_dir: Path) -> Optional[Path]:
    """Save an interesting result to the corpus."""
    corpus_dir.mkdir(exist_ok=True)
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mutator_safe = result.mutator.replace("/", "_").replace("\\", "_")
    filename = f"{timestamp}_{mutator_safe}_{result.iteration:06d}.json"
    filepath = corpus_dir / filename
    
    try:
        filepath.write_text(json.dumps({
            "iteration": result.iteration,
            "mutator": result.mutator,
            "payload": result.payload,
            "status_code": result.status_code,
            "response_preview": result.response_body[:500],
            "elapsed_ms": result.elapsed_ms,
            "is_crash": result.is_crash,
            "crash_detail": result.crash_detail,
            "coverage_hash": result.coverage_hash,
            "timestamp": timestamp,
        }, default=str, indent=2))
        return filepath
    except Exception:
        return None


def load_corpus(corpus_dir: Path) -> List[dict]:
    """Load all corpus entries."""
    entries = []
    if not corpus_dir.exists():
        return entries
    
    for filepath in sorted(corpus_dir.glob("*.json")):
        try:
            data = json.loads(filepath.read_text())
            entries.append(data)
        except Exception:
            pass
    return entries


def deduplicate_corpus(corpus_dir: Path) -> int:
    """Remove duplicate entries from corpus based on coverage hash."""
    entries = load_corpus(corpus_dir)
    seen_hashes = set()
    removed = 0
    
    for entry in entries:
        cov_hash = entry.get("coverage_hash", "")
        if cov_hash in seen_hashes:
            # Remove duplicate
            filepath = corpus_dir / f"{entry.get('timestamp', 'unknown')}_{entry.get('mutator', 'unknown')}_{entry.get('iteration', 0):06d}.json"
            if filepath.exists():
                filepath.unlink()
            removed += 1
        else:
            seen_hashes.add(cov_hash)
    
    return removed


def minimize_corpus(corpus_dir: Path, target_url: str, verbose: bool = False) -> int:
    """Minimize corpus by removing entries that don't trigger unique behavior."""
    entries = load_corpus(corpus_dir)
    if not entries:
        return 0
    
    seen_hashes = set()
    kept = 0
    removed = 0
    
    for entry in entries:
        payload = entry.get("payload")
        if payload is None:
            continue
        
        # Replay and check coverage
        status, response, elapsed = send_payload(payload, target_url)
        cov_hash = compute_coverage_hash(status, response)
        
        if cov_hash not in seen_hashes:
            seen_hashes.add(cov_hash)
            kept += 1
        else:
            # Remove redundant entry
            timestamp = entry.get("timestamp", "unknown")
            mutator = entry.get("mutator", "unknown")
            iteration = entry.get("iteration", 0)
            filepath = corpus_dir / f"{timestamp}_{mutator}_{iteration:06d}.json"
            if filepath.exists():
                filepath.unlink()
            removed += 1
            if verbose:
                print(f"  Removed redundant: {filepath.name}")
    
    return removed


def replay_corpus(corpus_dir: Path, target_url: str, verbose: bool = False) -> Tuple[int, int]:
    """Replay all corpus entries and verify behavior."""
    entries = load_corpus(corpus_dir)
    if not entries:
        print("No corpus entries to replay.")
        return 0, 0
    
    crashes = 0
    successes = 0
    
    print(f"Replaying {len(entries)} corpus entries...")
    
    for entry in entries:
        payload = entry.get("payload")
        expected_crash = entry.get("is_crash", False)
        
        if payload is None:
            continue
        
        status, response, elapsed = send_payload(payload, target_url)
        is_crash, crash_detail = classify_crash(status, response, elapsed)
        
        if is_crash:
            crashes += 1
            if verbose:
                print(f"  💥 CRASH: {entry.get('mutator', 'unknown')}: {crash_detail}")
        else:
            successes += 1
            if verbose:
                print(f"  ✓ OK: {entry.get('mutator', 'unknown')} → HTTP {status}")
    
    return crashes, successes


# ---------------------------------------------------------------------------
# Statistics Tracking
# ---------------------------------------------------------------------------

@dataclass
class FuzzStats:
    """Fuzzing statistics."""
    total_iterations: int = 0
    total_crashes: int = 0
    total_interesting: int = 0
    status_codes: Dict[str, int] = field(default_factory=dict)
    mutator_stats: Dict[str, int] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    coverage_hashes: set = field(default_factory=set)
    
    def to_dict(self) -> dict:
        return {
            "total_iterations": self.total_iterations,
            "total_crashes": self.total_crashes,
            "total_interesting": self.total_interesting,
            "status_codes": self.status_codes,
            "mutator_stats": self.mutator_stats,
            "duration_seconds": time.time() - self.start_time,
            "unique_coverage": len(self.coverage_hashes),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "FuzzStats":
        stats = cls()
        stats.total_iterations = data.get("total_iterations", 0)
        stats.total_crashes = data.get("total_crashes", 0)
        stats.total_interesting = data.get("total_interesting", 0)
        stats.status_codes = data.get("status_codes", {})
        stats.mutator_stats = data.get("mutator_stats", {})
        stats.coverage_hashes = set(data.get("coverage_hashes", []))
        return stats


def save_stats(stats: FuzzStats, filepath: Path) -> None:
    """Save fuzzing statistics to file."""
    data = stats.to_dict()
    data["coverage_hashes"] = list(stats.coverage_hashes)
    filepath.write_text(json.dumps(data, indent=2))


def load_stats(filepath: Path) -> FuzzStats:
    """Load fuzzing statistics from file."""
    if not filepath.exists():
        return FuzzStats()
    data = json.loads(filepath.read_text())
    data["coverage_hashes"] = set(data.get("coverage_hashes", []))
    return FuzzStats.from_dict(data)


# ---------------------------------------------------------------------------
# Main Fuzzing Loop
# ---------------------------------------------------------------------------

def run_fuzz(
    count: int = DEFAULT_ITERATIONS,
    target_url: str = DEFAULT_TARGET_URL,
    save_corpus: bool = False,
    replay_mode: bool = False,
    minimize_mode: bool = False,
    ci_mode: bool = False,
    verbose: bool = False,
    seed: Optional[int] = None,
) -> List[FuzzResult]:
    """Run the fuzzing loop."""
    
    # Set random seed for reproducibility
    if seed is not None:
        random.seed(seed)
    
    crashes: List[FuzzResult] = []
    stats = load_stats(FUZZ_STATS_FILE)
    seen_hashes = stats.coverage_hashes
    
    if replay_mode:
        # Replay existing corpus
        crash_count, success_count = replay_corpus(CORPUS_DIR, target_url, verbose)
        print(f"\nReplay complete: {success_count} OK, {crash_count} crashes")
        return crashes
    
    if minimize_mode:
        # Minimize corpus
        print("Minimizing corpus...")
        removed = minimize_corpus(CORPUS_DIR, target_url, verbose)
        print(f"Removed {removed} redundant entries")
        return crashes
    
    print(f"🔥 RustChain Attestation Fuzz Runner")
    print(f"   Target: {target_url}/attest/submit")
    print(f"   Iterations: {count}")
    print(f"   Save corpus: {save_corpus}")
    print(f"   Seed: {seed}")
    print()
    
    for i in range(count):
        base = baseline_payload(random.choice(KNOWN_WALLETS))
        
        # Pick mutator
        mutator_name, mutator_fn = random.choice(MUTATORS)
        
        if mutator_name == "not_json":
            payload = None
            status, response, elapsed = send_payload(None, target_url, is_raw=True)
        else:
            try:
                payload = mutator_fn(base)
            except Exception:
                payload = base
            status, response, elapsed = send_payload(payload, target_url)
        
        is_crash, crash_detail = classify_crash(status, response, elapsed)
        coverage_hash = compute_coverage_hash(status, response)
        interesting = is_interesting(payload, status, coverage_hash, seen_hashes)
        
        result = FuzzResult(
            iteration=i + 1,
            mutator=mutator_name,
            payload=payload,
            status_code=status,
            response_body=response[:500],
            elapsed_ms=elapsed,
            is_crash=is_crash,
            is_interesting=interesting,
            crash_detail=crash_detail,
            coverage_hash=coverage_hash,
        )
        
        # Update stats
        stats.total_iterations += 1
        status_key = str(status) if status else "network_err"
        stats.status_codes[status_key] = stats.status_codes.get(status_key, 0) + 1
        stats.mutator_stats[mutator_name] = stats.mutator_stats.get(mutator_name, 0) + 1
        
        if is_crash:
            stats.total_crashes += 1
            crashes.append(result)
            seen_hashes.add(coverage_hash)
            print(f"  💥 [{i+1:5d}] {mutator_name:<20} → CRASH: {crash_detail} ({elapsed:.0f}ms)")
        elif interesting:
            stats.total_interesting += 1
            seen_hashes.add(coverage_hash)
            if verbose:
                status_str = str(status) if status else "ERR"
                print(f"  ✨ [{i+1:5d}] {mutator_name:<20} → HTTP {status_str} (new coverage)")
        elif verbose or (i + 1) % 100 == 0:
            status_str = str(status) if status else "ERR"
            print(f"  ✓  [{i+1:5d}] {mutator_name:<20} → HTTP {status_str} ({elapsed:.0f}ms)")
        
        # Save interesting cases to corpus
        if save_corpus and interesting:
            saved_path = save_to_corpus(result, CORPUS_DIR)
            if saved_path and verbose:
                print(f"      Saved to corpus: {saved_path.name}")
        
        # Save crash cases to crash corpus
        if is_crash:
            save_to_corpus(result, CRASH_CORPUS_DIR)
        
        # Small delay to avoid hammering
        time.sleep(0.01)
    
    # Save stats
    save_stats(stats, FUZZ_STATS_FILE)
    
    # Summary
    print()
    print("=" * 60)
    print(f"  Fuzz Summary")
    print("=" * 60)
    print(f"  Total iterations: {stats.total_iterations}")
    print(f"  Crashes found: {stats.total_crashes}")
    print(f"  Interesting cases: {stats.total_interesting}")
    print(f"  Unique coverage: {len(stats.coverage_hashes)}")
    print(f"  Duration: {time.time() - stats.start_time:.1f}s")
    print(f"  Rate: {stats.total_iterations / (time.time() - stats.start_time):.1f} iter/s")
    
    print(f"  Response codes: {dict(sorted(stats.status_codes.items()))}")
    
    if crashes:
        print()
        print("  💥 Crashes:")
        for c in crashes[:10]:
            print(f"    [{c.iteration}] {c.mutator}: {c.crash_detail}")
        
        # Save crash report
        crash_data = [
            {
                "iteration": c.iteration,
                "mutator": c.mutator,
                "status_code": c.status_code,
                "crash_detail": c.crash_detail,
                "elapsed_ms": c.elapsed_ms,
                "payload_preview": str(c.payload)[:500],
                "response_preview": c.response_body[:500],
                "coverage_hash": c.coverage_hash,
            }
            for c in crashes
        ]
        CRASH_REPORT.write_text(json.dumps(crash_data, indent=2))
        print(f"\n  Crash report saved to: {CRASH_REPORT}")
        print(f"  Crash corpus saved to: {CRASH_CORPUS_DIR}")
    
    print("=" * 60)
    return crashes


def show_report() -> None:
    """Display saved crash report."""
    if not CRASH_REPORT.exists():
        print("No crash report found. Run the fuzzer first.")
        return
    
    crashes = json.loads(CRASH_REPORT.read_text())
    print(f"Crash Report — {len(crashes)} crashes found")
    print()
    for c in crashes:
        print(f"  [{c['iteration']}] {c['mutator']}: {c['crash_detail']}")
        print(f"    Status: {c['status_code']} | Elapsed: {c['elapsed_ms']:.0f}ms")
        print(f"    Coverage: {c['coverage_hash']}")
        print()


def show_stats() -> None:
    """Display fuzzing statistics."""
    if not FUZZ_STATS_FILE.exists():
        print("No stats found. Run the fuzzer first.")
        return
    
    stats = load_stats(FUZZ_STATS_FILE)
    data = stats.to_dict()
    
    print("Fuzz Statistics")
    print("=" * 60)
    print(f"  Total iterations: {data['total_iterations']}")
    print(f"  Total crashes: {data['total_crashes']}")
    print(f"  Interesting cases: {data['total_interesting']}")
    print(f"  Unique coverage: {data['unique_coverage']}")
    print(f"  Duration: {data['duration_seconds']:.1f}s")
    print()
    print("  Status codes:")
    for code, count in sorted(data['status_codes'].items()):
        print(f"    {code}: {count}")
    print()
    print("  Mutator stats:")
    for mutator, count in sorted(data['mutator_stats'].items(), key=lambda x: -x[1])[:10]:
        print(f"    {mutator}: {count}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="RustChain Attestation Fuzz Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          Run 1000 iterations
  %(prog)s --count 5000             Run 5000 iterations
  %(prog)s --ci                     CI mode (exit 1 on crash)
  %(prog)s --save-corpus            Save interesting cases
  %(prog)s --replay                 Replay saved corpus
  %(prog)s --minimize               Minimize corpus size
  %(prog)s --report                 Show crash report
  %(prog)s --stats                  Show fuzz statistics
  %(prog)s --seed 42                Use fixed random seed
  %(prog)s --url http://localhost   Target URL
        """
    )
    parser.add_argument("--count", type=int, default=DEFAULT_ITERATIONS, help="Number of fuzz iterations")
    parser.add_argument("--ci", action="store_true", help="Exit non-zero if any crash found")
    parser.add_argument("--save-corpus", action="store_true", help="Save interesting payloads to corpus")
    parser.add_argument("--verbose", action="store_true", help="Print every result")
    parser.add_argument("--report", action="store_true", help="Show saved crash report")
    parser.add_argument("--stats", action="store_true", help="Show fuzz statistics")
    parser.add_argument("--replay", action="store_true", help="Replay saved corpus")
    parser.add_argument("--minimize", action="store_true", help="Minimize corpus size")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--url", default=None, help="Override target URL")
    args = parser.parse_args()

    target_url = args.url or DEFAULT_TARGET_URL

    if args.report:
        show_report()
        return 0
    
    if args.stats:
        show_stats()
        return 0

    crashes = run_fuzz(
        count=args.count,
        target_url=target_url,
        save_corpus=args.save_corpus,
        replay_mode=args.replay,
        minimize_mode=args.minimize,
        ci_mode=args.ci,
        verbose=args.verbose,
        seed=args.seed,
    )

    if args.ci and crashes:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
