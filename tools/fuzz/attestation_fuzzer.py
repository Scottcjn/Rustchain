# SPDX-License-Identifier: MIT
#
# RustChain Attestation Fuzz Harness
#
# Mutation strategies and corpus design originally by LaphoqueRC (PR #1629).
# Adapted to RustChain attestation format, correct DB path, and endpoint.

import argparse
import json
import hashlib
import random
import requests
import sqlite3
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NODE_URL = "http://localhost:8099/attest/submit"
DB_PATH = "rustchain_v2.db"
CORPUS_DIR = "fuzz_corpus"
CRASH_DIR = "crash_corpus"

# ---------------------------------------------------------------------------
# Base attestation template (matches RustChain /attest/submit schema)
# ---------------------------------------------------------------------------

BASE_ATTESTATION: Dict[str, Any] = {
    "miner": "fuzz-test-wallet",
    "miner_id": "fuzz-test-miner-001",
    "nonce": 12345,
    "report": {
        "cpu_model": "Fuzz Test CPU",
        "platform": "linux",
        "python_version": "3.11.0",
    },
    "device": {
        "model": "Fuzz Test Device",
        "arch": "modern",
        "family": "x86_64",
        "device_id": "fuzz-device-001",
    },
    "signals": {
        "macs": ["AA:BB:CC:DD:EE:FF"],
    },
    "fingerprint": {
        "all_passed": True,
        "checks": {
            "clock_drift": {"passed": True, "data": {"cv": 0.05, "samples": 1000}},
            "cache_timing": {"passed": True, "data": {"l1_latency": 1.2, "l2_latency": 4.5}},
            "simd_identity": {"passed": True, "data": {"has_altivec": False, "has_sse": True}},
            "thermal_drift": {"passed": True, "data": {"delta_c": 2.3}},
            "instruction_jitter": {"passed": True, "data": {"jitter_ns": 15.2}},
            "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
        },
    },
}


@dataclass
class FuzzResult:
    payload: Dict[Any, Any]
    crashed: bool
    status_code: Optional[int]
    exception: Optional[str]
    duration: float
    payload_hash: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_string(length: int) -> str:
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choice(chars) for _ in range(length))


def _random_hex(length: int) -> str:
    return "".join(random.choice("0123456789abcdef") for _ in range(length))


def _deep_copy(d: Any) -> Any:
    """JSON round-trip deep copy (handles non-serialisable gracefully)."""
    try:
        return json.loads(json.dumps(d, default=str))
    except (TypeError, ValueError):
        if isinstance(d, dict):
            return {k: _deep_copy(v) for k, v in d.items()}
        if isinstance(d, list):
            return [_deep_copy(v) for v in d]
        return d


# ---------------------------------------------------------------------------
# Template generators
# ---------------------------------------------------------------------------

def generate_valid_attestation() -> Dict[str, Any]:
    """Return a well-formed attestation payload with randomised identifiers."""
    payload = _deep_copy(BASE_ATTESTATION)
    payload["miner"] = "fuzz-wallet-" + _random_string(8)
    payload["miner_id"] = "fuzz-miner-" + _random_string(8)
    payload["nonce"] = random.randint(1, 2**32)
    payload["device"]["device_id"] = "fuzz-dev-" + _random_hex(12)
    payload["signals"]["macs"] = [
        ":".join(_random_hex(2) for _ in range(6))
    ]
    return payload


def generate_minimal_attestation() -> Dict[str, Any]:
    """Return a bare-minimum payload (miner + miner_id + nonce only)."""
    return {
        "miner": "fuzz-minimal",
        "miner_id": "fuzz-minimal-001",
        "nonce": int(time.time()),
    }


def generate_complex_attestation() -> Dict[str, Any]:
    """Return an attestation with extra metadata fields."""
    base = generate_valid_attestation()
    base["report"]["extra_cpu_info"] = {
        "cores": random.randint(1, 128),
        "threads": random.randint(1, 256),
        "brand": "Fuzz " + _random_string(12),
    }
    base["fingerprint"]["checks"]["rom_fingerprint"] = {
        "passed": True,
        "data": {"rom_hash": _random_hex(64), "platform": "fuzz"},
    }
    return base


_TEMPLATE_FUNCS = [
    generate_valid_attestation,
    generate_minimal_attestation,
    generate_complex_attestation,
]


# ---------------------------------------------------------------------------
# 8 mutation strategies (originally by LaphoqueRC)
# ---------------------------------------------------------------------------

def mutate_type_confusion(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Swap types: strings to ints, dicts to lists/strings."""
    m = _deep_copy(payload)
    if "nonce" in m and isinstance(m["nonce"], int):
        m["nonce"] = str(m["nonce"])
    if "miner" in m and isinstance(m["miner"], str):
        m["miner"] = hash(m["miner"]) % 2**32
    if "device" in m and isinstance(m["device"], dict):
        if random.choice([True, False]):
            m["device"] = str(m["device"])
        else:
            m["device"] = list(m["device"].values())
    return m


def mutate_missing_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Remove one or more critical fields."""
    m = _deep_copy(payload)
    critical = ["miner", "miner_id", "nonce", "device", "fingerprint"]
    field = random.choice(critical)
    m.pop(field, None)

    if "device" in m and isinstance(m["device"], dict) and m["device"]:
        key = random.choice(list(m["device"].keys()))
        m["device"].pop(key, None)
    return m


def mutate_oversized_values(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Inject very large strings / numbers / arrays."""
    m = _deep_copy(payload)
    if "miner" in m:
        m["miner"] = "x" * random.randint(10_000, 100_000)
    if "nonce" in m:
        m["nonce"] = 2 ** random.randint(32, 128)
    if "signals" in m:
        m["signals"]["macs"] = [_random_hex(12) for _ in range(random.randint(500, 5000))]
    return m


def mutate_boundary_conditions(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Replace numeric fields with boundary values."""
    m = _deep_copy(payload)
    boundaries = [
        0, -1, 1, 2**31 - 1, 2**31, 2**32 - 1, 2**32,
        2**63 - 1, 2**63, -2**31, -2**63,
    ]
    if "nonce" in m:
        m["nonce"] = random.choice(boundaries)

    fp = m.get("fingerprint", {}).get("checks", {}).get("clock_drift", {}).get("data", {})
    if "cv" in fp:
        fp["cv"] = random.choice([0, -1, 1e308, float("inf"), float("-inf")])
    return m


def mutate_nested_structures(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create deeply nested dicts to stress JSON parsing."""
    m = _deep_copy(payload)
    nest = m
    for i in range(random.randint(100, 500)):
        nest[f"level_{i}"] = {}
        nest = nest[f"level_{i}"]
    return m


def mutate_boolean_dict_mismatch(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Replace dicts with booleans / None and vice versa."""
    m = _deep_copy(payload)
    if "fingerprint" in m:
        m["fingerprint"] = random.choice([True, False, None])
    if "device" in m:
        m["device"] = random.choice([True, False, None])
    m["unexpected_field"] = {"should_be": "boolean"}
    return m


def mutate_timestamp_edge_cases(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Supply extreme timestamp-like values in the nonce / report fields."""
    m = _deep_copy(payload)
    edges = [
        -1, 0, 1,
        253402300799, 253402300800,
        -2147483648, 2147483647,
        int(time.time()) + 86400 * 365 * 100,
        int(time.time()) - 86400 * 365 * 100,
    ]
    m["nonce"] = random.choice(edges)
    return m


def mutate_encoding_corruption(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Inject control characters and invalid byte sequences."""
    m = _deep_copy(payload)
    corrupted = [
        "\x00\x01\x02\x03",
        "\xff\xfe\xfd",
        "valid_start\x00null_byte",
        "emoji_\U0001f480_corruption",
        "\n\r\t\x08\x0c",
    ]
    if "miner" in m:
        m["miner"] = random.choice(corrupted)
    if "miner_id" in m:
        m["miner_id"] = random.choice(corrupted)
    return m


MUTATION_STRATEGIES = [
    mutate_type_confusion,
    mutate_missing_fields,
    mutate_oversized_values,
    mutate_boundary_conditions,
    mutate_nested_structures,
    mutate_boolean_dict_mismatch,
    mutate_timestamp_edge_cases,
    mutate_encoding_corruption,
]


# ---------------------------------------------------------------------------
# Fuzz harness
# ---------------------------------------------------------------------------

class AttestationFuzzHarness:
    def __init__(self, node_url: str = NODE_URL, offline: bool = False):
        self.node_url = node_url
        self.offline = offline
        self.corpus_path = Path(CORPUS_DIR)
        self.crash_path = Path(CRASH_DIR)
        self.corpus_path.mkdir(exist_ok=True)
        self.crash_path.mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Payload submission
    # ------------------------------------------------------------------

    def submit_payload(self, payload: Dict[str, Any], timeout: int = 10) -> FuzzResult:
        """Send *payload* to the attestation endpoint and record the result."""
        payload_str = json.dumps(payload, default=str, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()
        start = time.time()
        crashed = False
        status_code = None
        exception_info = None

        if self.offline:
            # Offline mode: just validate serialisation round-trip
            try:
                json.loads(payload_str)
            except Exception as exc:
                crashed = True
                exception_info = f"{type(exc).__name__}: {exc}"
        else:
            try:
                resp = requests.post(
                    self.node_url,
                    json=payload,
                    timeout=timeout,
                    verify=True,  # Enforce TLS validation (use CA bundle for test env)
                )
                status_code = resp.status_code
                if status_code >= 500:
                    crashed = True
                    exception_info = f"HTTP {status_code}: {resp.text[:200]}"
            except requests.exceptions.Timeout:
                crashed = True
                exception_info = "Request timed out"
            except Exception as exc:
                crashed = True
                exception_info = f"{type(exc).__name__}: {exc}"

        duration = time.time() - start
        result = FuzzResult(
            payload=payload,
            crashed=crashed,
            status_code=status_code,
            exception=exception_info,
            duration=duration,
            payload_hash=payload_hash,
        )
        self._save(payload, crashed, exception_info, payload_hash)
        return result

    # ------------------------------------------------------------------
    # Corpus persistence
    # ------------------------------------------------------------------

    def _save(self, payload: Dict, crashed: bool, exception: Optional[str], phash: str):
        directory = self.crash_path if crashed else self.corpus_path
        filepath = directory / f"{phash}.json"
        if filepath.exists():
            return
        entry = {
            "payload": payload,
            "crashed": crashed,
            "exception": exception,
            "timestamp": time.time(),
            "hash": phash,
        }
        try:
            with open(filepath, "w") as fh:
                json.dump(entry, fh, indent=2, default=str)
        except OSError:
            pass

    def load_crash_corpus(self) -> List[Dict[str, Any]]:
        payloads = []
        for fp in self.crash_path.glob("*.json"):
            try:
                with open(fp) as fh:
                    payloads.append(json.load(fh)["payload"])
            except Exception:
                pass
        return payloads

    # ------------------------------------------------------------------
    # Campaign runners
    # ------------------------------------------------------------------

    def run_campaign(self, iterations: int = 1000, workers: int = 1) -> List[FuzzResult]:
        """Generate *iterations* fuzzed payloads and submit them."""
        print(f"[fuzz] Starting campaign: {iterations} iterations, {workers} workers")

        def _one_iteration(_i: int) -> FuzzResult:
            tmpl = random.choice(_TEMPLATE_FUNCS)
            payload = tmpl()
            for _ in range(random.randint(1, 3)):
                strategy = random.choice(MUTATION_STRATEGIES)
                try:
                    payload = strategy(payload)
                except Exception:
                    pass
            return self.submit_payload(payload)

        results: List[FuzzResult] = []
        crashes = 0

        if workers <= 1:
            for i in range(iterations):
                r = _one_iteration(i)
                results.append(r)
                if r.crashed:
                    crashes += 1
                if (i + 1) % 100 == 0:
                    print(f"[fuzz] {i + 1}/{iterations}  crashes={crashes}")
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_one_iteration, i): i for i in range(iterations)}
                done = 0
                for fut in as_completed(futures):
                    r = fut.result()
                    results.append(r)
                    if r.crashed:
                        crashes += 1
                    done += 1
                    if done % 100 == 0:
                        print(f"[fuzz] {done}/{iterations}  crashes={crashes}")

        print(f"[fuzz] Done. {len(results)} payloads, {crashes} crashes "
              f"({crashes / max(len(results), 1) * 100:.1f}%)")
        return results

    def run_regression(self) -> List[FuzzResult]:
        """Re-submit every payload in the crash corpus."""
        payloads = self.load_crash_corpus()
        if not payloads:
            print("[fuzz] No crash corpus found.")
            return []
        print(f"[fuzz] Regression: {len(payloads)} saved crash cases")
        results = []
        regressions = 0
        for p in payloads:
            r = self.submit_payload(p)
            results.append(r)
            if not r.crashed:
                regressions += 1
        print(f"[fuzz] Regression done. {regressions} previously-crashing payloads "
              f"no longer crash.")
        return results

    def minimize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Simple field-removal minimisation of a crashing payload."""
        if not self.submit_payload(payload).crashed:
            return payload
        minimal = _deep_copy(payload)
        for key in list(minimal.keys()):
            candidate = _deep_copy(minimal)
            del candidate[key]
            if self.submit_payload(candidate).crashed:
                minimal = candidate
        for key, val in list(minimal.items()):
            if isinstance(val, dict):
                for nested_key in list(val.keys()):
                    candidate = _deep_copy(minimal)
                    del candidate[key][nested_key]
                    if self.submit_payload(candidate).crashed:
                        minimal = candidate
        return minimal


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="RustChain Attestation Fuzz Harness",
    )
    parser.add_argument(
        "--mode",
        choices=["campaign", "regression", "minimize"],
        default="campaign",
    )
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--url", default=NODE_URL, help="Attestation endpoint URL")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip HTTP; only test JSON serialisation round-trips",
    )
    args = parser.parse_args()

    harness = AttestationFuzzHarness(node_url=args.url, offline=args.offline)

    if args.mode == "campaign":
        results = harness.run_campaign(args.iterations, args.workers)
        crashes = [r for r in results if r.crashed]
        if crashes:
            print(f"\n[fuzz] Minimising up to 5 crash cases...")
            for i, c in enumerate(crashes[:5]):
                print(f"  [{i + 1}/5] {c.payload_hash[:16]}...")
                harness.minimize(c.payload)

    elif args.mode == "regression":
        harness.run_regression()

    elif args.mode == "minimize":
        payloads = harness.load_crash_corpus()
        if not payloads:
            print("[fuzz] No crash corpus to minimise.")
            return 1
        for i, p in enumerate(payloads[:10]):
            print(f"[fuzz] Minimising crash {i + 1}/{min(10, len(payloads))}...")
            harness.minimize(p)

    return 0


if __name__ == "__main__":
    sys.exit(main())
