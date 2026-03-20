// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import random
import sqlite3
import time
import traceback
import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pathlib import Path

DB_PATH = "rustchain.db"
CORPUS_DIR = "fuzz_corpus"
CRASH_DIR = "crash_corpus"

@dataclass
class FuzzResult:
    payload: Dict[Any, Any]
    crashed: bool
    exception: Optional[str]
    duration: float
    payload_hash: str

class AttestationFuzzHarness:
    def __init__(self):
        self.corpus_path = Path(CORPUS_DIR)
        self.crash_path = Path(CRASH_DIR)
        self.corpus_path.mkdir(exist_ok=True)
        self.crash_path.mkdir(exist_ok=True)

        self.mutation_strategies = [
            self.mutate_type_confusion,
            self.mutate_missing_fields,
            self.mutate_oversized_values,
            self.mutate_boundary_conditions,
            self.mutate_nested_structures,
            self.mutate_boolean_dict_mismatch,
            self.mutate_timestamp_edge_cases,
            self.mutate_encoding_corruption
        ]

        self.base_templates = [
            self.generate_valid_attestation,
            self.generate_minimal_attestation,
            self.generate_complex_attestation
        ]

    def generate_valid_attestation(self) -> Dict[str, Any]:
        return {
            "node_id": "node_" + self.random_string(8),
            "timestamp": int(time.time()),
            "block_hash": self.random_hex(64),
            "signature": self.random_hex(128),
            "validator_pubkey": self.random_hex(66),
            "attestation_data": {
                "slot": random.randint(1, 1000000),
                "committee_index": random.randint(0, 63),
                "beacon_block_root": self.random_hex(64),
                "source": {
                    "epoch": random.randint(1, 10000),
                    "root": self.random_hex(64)
                },
                "target": {
                    "epoch": random.randint(1, 10000),
                    "root": self.random_hex(64)
                }
            }
        }

    def generate_minimal_attestation(self) -> Dict[str, Any]:
        return {
            "node_id": "minimal_node",
            "timestamp": int(time.time()),
            "block_hash": "0x" + "a" * 62
        }

    def generate_complex_attestation(self) -> Dict[str, Any]:
        base = self.generate_valid_attestation()
        base["metadata"] = {
            "version": "2.1.0",
            "consensus_layer": "ethereum2",
            "network_id": random.randint(1, 65535),
            "peers": [self.random_string(16) for _ in range(random.randint(0, 20))],
            "sync_status": random.choice(["synced", "syncing", "not_synced"]),
            "chain_head": {
                "slot": random.randint(1000000, 2000000),
                "block_root": self.random_hex(64),
                "state_root": self.random_hex(64)
            }
        }
        return base

    def mutate_type_confusion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mutated = payload.copy()

        # Convert strings to numbers and vice versa
        if "timestamp" in mutated and isinstance(mutated["timestamp"], int):
            mutated["timestamp"] = str(mutated["timestamp"])

        if "node_id" in mutated and isinstance(mutated["node_id"], str):
            mutated["node_id"] = hash(mutated["node_id"]) % 2**32

        # Convert dicts to lists/strings
        if "attestation_data" in mutated and isinstance(mutated["attestation_data"], dict):
            if random.choice([True, False]):
                mutated["attestation_data"] = str(mutated["attestation_data"])
            else:
                mutated["attestation_data"] = list(mutated["attestation_data"].values())

        return mutated

    def mutate_missing_fields(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mutated = payload.copy()

        # Remove critical fields
        critical_fields = ["node_id", "timestamp", "block_hash", "signature"]
        if critical_fields:
            field_to_remove = random.choice(critical_fields)
            mutated.pop(field_to_remove, None)

        # Remove nested fields
        if "attestation_data" in mutated and isinstance(mutated["attestation_data"], dict):
            nested_data = mutated["attestation_data"].copy()
            if nested_data:
                key_to_remove = random.choice(list(nested_data.keys()))
                nested_data.pop(key_to_remove)
                mutated["attestation_data"] = nested_data

        return mutated

    def mutate_oversized_values(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mutated = payload.copy()

        # Oversized strings
        if "node_id" in mutated:
            mutated["node_id"] = "x" * random.randint(10000, 100000)

        if "block_hash" in mutated:
            mutated["block_hash"] = "0x" + "f" * random.randint(1000, 10000)

        # Oversized numbers
        if "timestamp" in mutated:
            mutated["timestamp"] = 2**random.randint(32, 128)

        # Oversized nested structures
        if "attestation_data" in mutated:
            mutated["attestation_data"] = {
                "massive_array": list(range(random.randint(50000, 200000)))
            }

        return mutated

    def mutate_boundary_conditions(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mutated = payload.copy()

        boundary_values = [
            0, -1, 1, 2**31-1, 2**31, 2**32-1, 2**32, 2**63-1, 2**63,
            -2**31, -2**63, float('inf'), -float('inf'), float('nan')
        ]

        if "timestamp" in mutated:
            mutated["timestamp"] = random.choice(boundary_values)

        if "attestation_data" in mutated and isinstance(mutated["attestation_data"], dict):
            for key in mutated["attestation_data"]:
                if isinstance(mutated["attestation_data"][key], (int, float)):
                    mutated["attestation_data"][key] = random.choice(boundary_values)

        return mutated

    def mutate_nested_structures(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mutated = payload.copy()

        # Create deeply nested structures
        deep_nest = mutated
        for i in range(random.randint(100, 1000)):
            deep_nest[f"level_{i}"] = {}
            deep_nest = deep_nest[f"level_{i}"]

        # Circular references (will cause JSON serialization issues)
        if "attestation_data" in mutated:
            mutated["circular_ref"] = mutated

        return mutated

    def mutate_boolean_dict_mismatch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mutated = payload.copy()

        # Replace expected dicts with booleans
        if "attestation_data" in mutated:
            mutated["attestation_data"] = random.choice([True, False, None])

        # Replace expected booleans with dicts
        mutated["is_valid"] = {"unexpected": "dict structure"}
        mutated["finalized"] = [1, 2, 3, "not_boolean"]

        return mutated

    def mutate_timestamp_edge_cases(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mutated = payload.copy()

        edge_timestamps = [
            -1, 0, 1,
            253402300799,  # Max 32-bit timestamp
            253402300800,  # Just over max
            -2147483648,   # Min 32-bit signed int
            2147483647,    # Max 32-bit signed int
            int(time.time()) + 86400*365*100,  # 100 years in future
            int(time.time()) - 86400*365*100   # 100 years in past
        ]

        mutated["timestamp"] = random.choice(edge_timestamps)

        if "attestation_data" in mutated and isinstance(mutated["attestation_data"], dict):
            if "source" in mutated["attestation_data"]:
                mutated["attestation_data"]["source"]["epoch"] = random.choice(edge_timestamps)

        return mutated

    def mutate_encoding_corruption(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mutated = payload.copy()

        # Invalid UTF-8 sequences (as strings that would break JSON)
        corrupted_strings = [
            "\x00\x01\x02\x03",
            "\xff\xfe\xfd",
            "valid_start\x00null_byte",
            "\ud800\udc00",  # Surrogate pairs
            "emoji_💀_corruption",
            "\n\r\t\x08\x0c",  # Control characters
        ]

        if "node_id" in mutated:
            mutated["node_id"] = random.choice(corrupted_strings)

        if "block_hash" in mutated:
            mutated["block_hash"] = "0x" + random.choice(corrupted_strings)

        return mutated

    def random_string(self, length: int) -> str:
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return ''.join(random.choice(chars) for _ in range(length))

    def random_hex(self, length: int) -> str:
        chars = "0123456789abcdef"
        return ''.join(random.choice(chars) for _ in range(length))

    def validate_attestation(self, payload: Dict[str, Any]) -> bool:
        # Simulate attestation validation logic
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Basic field validation
            required_fields = ["node_id", "timestamp", "block_hash"]
            for field in required_fields:
                if field not in payload:
                    raise ValueError(f"Missing required field: {field}")

            # Type validation
            if not isinstance(payload.get("timestamp"), (int, float)):
                raise TypeError("timestamp must be numeric")

            if not isinstance(payload.get("node_id"), str):
                raise TypeError("node_id must be string")

            # Simulate database operations that could crash
            cursor.execute("SELECT COUNT(*) FROM nodes WHERE id = ?", (payload["node_id"],))

            # Complex nested validation
            if "attestation_data" in payload:
                data = payload["attestation_data"]
                if isinstance(data, dict):
                    if "source" in data and "epoch" in data["source"]:
                        epoch = data["source"]["epoch"]
                        if epoch < 0 or epoch > 2**32:
                            raise ValueError("Invalid epoch range")

        return True

    def save_payload(self, payload: Dict[str, Any], crashed: bool, exception: str = None):
        payload_str = json.dumps(payload, default=str, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()

        directory = self.crash_path if crashed else self.corpus_path
        filename = f"{payload_hash}.json"

        file_path = directory / filename
        if not file_path.exists():
            with open(file_path, 'w') as f:
                corpus_entry = {
                    "payload": payload,
                    "crashed": crashed,
                    "exception": exception,
                    "timestamp": time.time(),
                    "hash": payload_hash
                }
                json.dump(corpus_entry, f, indent=2, default=str)

    def run_single_test(self, payload: Dict[str, Any]) -> FuzzResult:
        payload_str = json.dumps(payload, default=str, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()

        start_time = time.time()
        crashed = False
        exception_info = None

        try:
            self.validate_attestation(payload)
        except Exception as e:
            crashed = True
            exception_info = f"{type(e).__name__}: {str(e)}"
            print(f"CRASH: {exception_info[:100]}...")

        duration = time.time() - start_time

        result = FuzzResult(
            payload=payload,
            crashed=crashed,
            exception=exception_info,
            duration=duration,
            payload_hash=payload_hash
        )

        self.save_payload(payload, crashed, exception_info)
        return result

    def generate_corpus(self, num_payloads: int = 1000):
        print(f"Generating corpus of {num_payloads} test cases...")

        results = []
        crashes = 0

        for i in range(num_payloads):
            # Choose base template
            template_func = random.choice(self.base_templates)
            payload = template_func()

            # Apply random mutations
            num_mutations = random.randint(1, 3)
            for _ in range(num_mutations):
                strategy = random.choice(self.mutation_strategies)
                try:
                    payload = strategy(payload)
                except Exception:
                    # Some mutations may fail, that's ok
                    pass

            result = self.run_single_test(payload)
            results.append(result)

            if result.crashed:
                crashes += 1
                print(f"Crash #{crashes}: {result.exception[:80]}...")

            if (i + 1) % 100 == 0:
                print(f"Processed {i + 1}/{num_payloads} payloads, {crashes} crashes")

        return results

    def load_regression_corpus(self) -> List[Dict[str, Any]]:
        regression_payloads = []

        for crash_file in self.crash_path.glob("*.json"):
            try:
                with open(crash_file, 'r') as f:
                    corpus_entry = json.load(f)
                    regression_payloads.append(corpus_entry["payload"])
            except Exception as e:
                print(f"Failed to load {crash_file}: {e}")

        return regression_payloads

    def run_regression_tests(self):
        print("Running regression tests on known crash cases...")

        crash_payloads = self.load_regression_corpus()
        if not crash_payloads:
            print("No regression corpus found")
            return

        regressions = 0
        for i, payload in enumerate(crash_payloads):
            result = self.run_single_test(payload)
            if not result.crashed:
                regressions += 1
                print(f"REGRESSION: Previously crashing payload no longer crashes")
                print(f"Payload hash: {result.payload_hash}")

        print(f"Regression test complete: {regressions} regressions out of {len(crash_payloads)} cases")

    def minimize_crashing_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Simple minimization - remove fields one by one
        if not self.run_single_test(payload).crashed:
            return payload

        minimal = payload.copy()

        for key in list(minimal.keys()):
            temp = minimal.copy()
            del temp[key]

            if self.run_single_test(temp).crashed:
                minimal = temp

        # Minimize nested structures
        for key, value in minimal.items():
            if isinstance(value, dict):
                for nested_key in list(value.keys()):
                    temp = minimal.copy()
                    temp_nested = temp[key].copy()
                    del temp_nested[nested_key]
                    temp[key] = temp_nested

                    if self.run_single_test(temp).crashed:
                        minimal = temp

        return minimal

def main():
    harness = AttestationFuzzHarness()

    print("=== Attestation Fuzz Harness ===")
    print("Generating fuzz corpus...")

    # Generate main corpus
    results = harness.generate_corpus(2000)

    crashes = [r for r in results if r.crashed]
    print(f"\nFuzz testing complete:")
    print(f"Total payloads: {len(results)}")
    print(f"Crashes found: {len(crashes)}")
    print(f"Crash rate: {len(crashes)/len(results)*100:.2f}%")

    # Minimize a few crash cases
    print("\nMinimizing crash cases...")
    for i, crash in enumerate(crashes[:5]):
        print(f"Minimizing crash {i+1}/{min(5, len(crashes))}...")
        minimal = harness.minimize_crashing_payload(crash.payload)
        harness.save_payload(minimal, True, f"minimized_{crash.exception}")

    # Run regression tests
    harness.run_regression_tests()

    print(f"\nCorpus saved to: {harness.corpus_path}")
    print(f"Crash cases saved to: {harness.crash_path}")

if __name__ == "__main__":
    main()
