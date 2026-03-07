#!/usr/bin/env python3
"""
RustChain Attestation Fuzz Harness
====================================
Property-based fuzz testing for POST /attest/submit.
Generates thousands of malformed, oversized, and adversarial payloads
to find crashes, unhandled exceptions, and edge cases.

Usage:
    python3 attest_fuzz.py                   # Run 1000 fuzz iterations
    python3 attest_fuzz.py --count 10000     # Run 10000 iterations
    python3 attest_fuzz.py --ci              # Exit non-zero on crash found
    python3 attest_fuzz.py --save-corpus     # Save generated payloads
    python3 attest_fuzz.py --report          # Show saved crash report

Bounty: https://github.com/Scottcjn/rustchain-bounties/issues/762
Author: NOX Ventures (noxxxxybot-sketch)
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
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TARGET_URL = os.environ.get("RUSTCHAIN_URL", "https://50.28.86.131")
ATTEST_ENDPOINT = f"{TARGET_URL}/attest/submit"
CORPUS_DIR = Path("fuzz_corpus")
CRASH_REPORT = Path("fuzz_crashes.json")
TIMEOUT = 10

KNOWN_WALLETS = ["nox-ventures", "test-miner", "alice", "bob", "founder_community"]
KNOWN_ARCHS = ["modern", "vintage", "ppc", "arm64", "x86_64"]
KNOWN_FAMILIES = ["x86_64", "aarch64", "ppc64", "arm64", "i686"]


# ---------------------------------------------------------------------------
# Baseline valid payload
# ---------------------------------------------------------------------------

def _make_nonce(wallet: str) -> str:
    """Generate a plausible nonce."""
    data = f"{wallet}:{int(time.time())}:{random.randint(0, 1<<32)}".encode()
    return hashlib.sha256(data).hexdigest()


def baseline_payload(wallet: str = "nox-ventures") -> dict:
    """Generate a structurally valid attestation payload."""
    return {
        "miner": wallet,
        "miner_id": hashlib.sha256(wallet.encode()).hexdigest()[:16],
        "nonce": _make_nonce(wallet),
        "device": {
            "model": "AMD Ryzen 5 5600X",
            "arch": "modern",
            "family": "x86_64",
            "cpu_serial": hashlib.md5(wallet.encode()).hexdigest(),
            "device_id": "550e8400-e29b-41d4-a716-446655440000",
        },
        "signals": {
            "macs": ["aa:bb:cc:dd:ee:ff"],
            "hostname": "test-machine",
        },
        "fingerprint": {
            "all_passed": True,
            "checks": {
                "clock_drift": {"passed": True, "data": {"cv": 0.092, "samples": 1000}},
                "cache_timing": {"passed": True, "data": {"profile": [1.2, 3.4, 5.6]}},
                "simd_identity": {"passed": True, "data": {}},
                "thermal_drift": {"passed": True, "data": {}},
                "instruction_jitter": {"passed": True, "data": {}},
                "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
            },
        },
    }


# ---------------------------------------------------------------------------
# Mutation strategies
# ---------------------------------------------------------------------------

def rand_str(length: int, charset: str = string.printable) -> str:
    return "".join(random.choices(charset, k=length))


def rand_unicode() -> str:
    """Generate unicode edge cases: null bytes, RTL, emoji, surrogates."""
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
        "'; DROP TABLE miners; --",        # SQL injection attempt
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
    obj[key_path[-1]] = mutate_value(obj.get(key_path[-1]))
    return p


def mutate_add_unknown_field(payload: dict) -> dict:
    """Add unexpected fields at various levels."""
    p = deepcopy(payload)
    injection_key = rand_str(random.randint(1, 50))
    injection_val = mutate_value(None)
    target = random.choice([p, p.get("device", {}), p.get("signals", {}), p.get("fingerprint", {})])
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
    p["device"]["model"] = deep
    return p


def mutate_array_overflow(payload: dict) -> dict:
    """Make arrays very large."""
    p = deepcopy(payload)
    p["signals"]["macs"] = [f"aa:bb:cc:dd:ee:{i:02x}" for i in range(random.randint(1000, 10000))]
    return p


def mutate_float_checks(payload: dict) -> dict:
    """Use edge-case float values in fingerprint data."""
    p = deepcopy(payload)
    edge_floats = [float("inf"), float("-inf"), float("nan"), 1e308, -1e308, 1e-308, 0.0, -0.0]
    p["fingerprint"]["checks"]["clock_drift"]["data"]["cv"] = random.choice(edge_floats)
    p["fingerprint"]["checks"]["cache_timing"]["data"]["profile"] = [random.choice(edge_floats)] * 100
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
    ["device", "cpu_serial"],
    ["device", "device_id"],
    ["signals"],
    ["signals", "macs"],
    ["signals", "hostname"],
    ["fingerprint"],
    ["fingerprint", "all_passed"],
    ["fingerprint", "checks"],
    ["fingerprint", "checks", "clock_drift"],
]

MUTATORS = [
    ("missing_field", lambda p: mutate_missing_field(p, random.choice(KEY_PATHS))),
    ("wrong_type", lambda p: mutate_wrong_type(p, random.choice(KEY_PATHS))),
    ("unknown_field", mutate_add_unknown_field),
    ("nested_bomb", mutate_nested_bomb),
    ("array_overflow", mutate_array_overflow),
    ("float_edge", mutate_float_checks),
    ("unicode_miner", lambda p: {**p, "miner": rand_unicode()}),
    ("huge_miner", lambda p: {**p, "miner": "x" * random.randint(10_000, 1_000_000)}),
    ("null_miner", lambda p: {**p, "miner": None}),
    ("empty_payload", lambda _: {}),
    ("not_json", None),  # handled specially
]


# ---------------------------------------------------------------------------
# HTTP + result collection
# ---------------------------------------------------------------------------

@dataclass
class FuzzResult:
    iteration: int
    mutator: str
    payload: Any
    status_code: Optional[int]
    response_body: str
    elapsed_ms: float
    is_crash: bool
    crash_detail: str = ""


def send_payload(payload: Any, is_raw: bool = False) -> Tuple[Optional[int], str, float]:
    """Send a payload to the attestation endpoint."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    if is_raw:
        body = rand_str(random.randint(1, 10000)).encode()
        content_type = random.choice(["text/plain", "application/xml", "multipart/form-data", ""])
    else:
        try:
            body = json.dumps(payload).encode()
        except (TypeError, ValueError, RecursionError):
            body = b"{}"
        content_type = "application/json"

    req = urllib.request.Request(
        ATTEST_ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Content-Type": content_type,
            "User-Agent": "rustchain-fuzz/1.0",
        }
    )

    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
            elapsed = (time.monotonic() - start) * 1000
            return r.status, r.read().decode("utf-8", errors="replace")[:2000], elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.monotonic() - start) * 1000
        return e.code, e.read().decode("utf-8", errors="replace")[:2000], elapsed
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


# ---------------------------------------------------------------------------
# Main fuzzing loop
# ---------------------------------------------------------------------------

def run_fuzz(
    count: int = 1000,
    save_corpus: bool = False,
    ci_mode: bool = False,
    verbose: bool = False,
) -> List[FuzzResult]:
    crashes: List[FuzzResult] = []
    results: List[FuzzResult] = []

    if save_corpus:
        CORPUS_DIR.mkdir(exist_ok=True)

    print(f"🔥 RustChain Attestation Fuzz Harness")
    print(f"   Target: {ATTEST_ENDPOINT}")
    print(f"   Iterations: {count}")
    print(f"   Save corpus: {save_corpus}")
    print()

    for i in range(count):
        base = baseline_payload(random.choice(KNOWN_WALLETS))

        # Pick mutator
        mutator_name, mutator_fn = random.choice(MUTATORS)

        if mutator_name == "not_json":
            payload = None  # Will send raw garbage
            status, response, elapsed = send_payload(None, is_raw=True)
        else:
            try:
                payload = mutator_fn(base)
            except Exception:
                payload = base
            status, response, elapsed = send_payload(payload)

        is_crash, crash_detail = classify_crash(status, response, elapsed)

        result = FuzzResult(
            iteration=i + 1,
            mutator=mutator_name,
            payload=payload,
            status_code=status,
            response_body=response[:500],
            elapsed_ms=elapsed,
            is_crash=is_crash,
            crash_detail=crash_detail,
        )
        results.append(result)

        if is_crash:
            crashes.append(result)
            print(f"  💥 [{i+1:5d}] {mutator_name:<20} → CRASH: {crash_detail} ({elapsed:.0f}ms)")
        elif verbose or (i + 1) % 100 == 0:
            status_str = str(status) if status else "ERR"
            print(f"  ✓  [{i+1:5d}] {mutator_name:<20} → HTTP {status_str} ({elapsed:.0f}ms)")

        if save_corpus:
            corpus_file = CORPUS_DIR / f"iter_{i+1:06d}_{mutator_name}.json"
            try:
                corpus_file.write_text(json.dumps({
                    "mutator": mutator_name,
                    "payload": payload,
                    "status": status,
                    "elapsed_ms": elapsed,
                    "is_crash": is_crash,
                }, default=str))
            except Exception:
                pass

        # Small delay to avoid hammering
        time.sleep(0.01)

    # Summary
    print()
    print("=" * 60)
    print(f"  Fuzz Summary")
    print("=" * 60)
    print(f"  Total iterations: {count}")
    print(f"  Crashes found: {len(crashes)}")
    print(f"  Crash rate: {len(crashes)/count*100:.1f}%")

    status_counts = {}
    for r in results:
        k = str(r.status_code) if r.status_code else "network_err"
        status_counts[k] = status_counts.get(k, 0) + 1
    print(f"  Response codes: {dict(sorted(status_counts.items()))}")

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
            }
            for c in crashes
        ]
        CRASH_REPORT.write_text(json.dumps(crash_data, indent=2))
        print(f"\n  Crash report saved to: {CRASH_REPORT}")

    print("=" * 60)
    return crashes


def show_report():
    if not CRASH_REPORT.exists():
        print("No crash report found. Run the fuzzer first.")
        return
    crashes = json.loads(CRASH_REPORT.read_text())
    print(f"Crash Report — {len(crashes)} crashes found")
    print()
    for c in crashes:
        print(f"  [{c['iteration']}] {c['mutator']}: {c['crash_detail']}")
        print(f"    Status: {c['status_code']} | Elapsed: {c['elapsed_ms']:.0f}ms")
        print(f"    Payload: {c['payload_preview'][:100]}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="RustChain Attestation Fuzz Harness")
    parser.add_argument("--count", type=int, default=1000, help="Number of fuzz iterations")
    parser.add_argument("--ci", action="store_true", help="Exit non-zero if any crash found")
    parser.add_argument("--save-corpus", action="store_true", help="Save all generated payloads")
    parser.add_argument("--verbose", action="store_true", help="Print every result")
    parser.add_argument("--report", action="store_true", help="Show saved crash report")
    parser.add_argument("--url", default=None, help="Override target URL")
    args = parser.parse_args()

    if args.url:
        global ATTEST_ENDPOINT
        ATTEST_ENDPOINT = f"{args.url}/attest/submit"

    if args.report:
        show_report()
        return

    crashes = run_fuzz(
        count=args.count,
        save_corpus=args.save_corpus,
        ci_mode=args.ci,
        verbose=args.verbose,
    )

    if args.ci and crashes:
        sys.exit(1)


if __name__ == "__main__":
    main()
