#!/usr/bin/env python3
"""
RustChain Attestation Fuzz Harness

Generates malformed and adversarial payloads to test attestation parsing robustness.
"""

import random
import string
import json
import os
from typing import Dict, List, Any
from dataclasses import dataclass, asdict


@dataclass
class FuzzPayload:
    """Fuzz test payload."""
    name: str
    description: str
    payload: Dict[str, Any]
    expected_behavior: str


class AttestationFuzzer:
    """Generate fuzz payloads for attestation endpoint."""
    
    def __init__(self):
        self.corpus: List[FuzzPayload] = []
    
    def generate_type_confusion(self) -> List[FuzzPayload]:
        """Type confusion payloads."""
        payloads = []
        
        # Integer as string
        payloads.append(FuzzPayload(
            name="int_as_string",
            description="Pass integer field as string",
            payload={
                "miner_pubkey": 12345,  # Should be string
                "miner_id": "test_miner",
                "device": {"family": "x86", "arch": "modern"}
            },
            expected_behavior="reject"
        ))
        
        # String as integer
        payloads.append(FuzzPayload(
            name="string_as_int",
            description="Pass string field as integer",
            payload={
                "miner_pubkey": "RTC" + "0" * 60,
                "miner_id": 99999,  # Should be string
                "device": {"family": "x86", "arch": "modern"}
            },
            expected_behavior="reject"
        ))
        
        # Boolean as string
        payloads.append(FuzzPayload(
            name="bool_as_string",
            description="Pass boolean as string",
            payload={
                "miner_pubkey": "RTC" + "0" * 60,
                "miner_id": "test_miner",
                "device": {"family": "x86", "arch": "modern"},
                "enabled": "true"  # Should be boolean
            },
            expected_behavior="reject"
        ))
        
        return payloads
    
    def generate_missing_fields(self) -> List[FuzzPayload]:
        """Missing required field payloads."""
        payloads = []
        
        # Missing miner_pubkey
        payloads.append(FuzzPayload(
            name="missing_pubkey",
            description="Missing required miner_pubkey",
            payload={
                "miner_id": "test_miner",
                "device": {"family": "x86", "arch": "modern"}
            },
            expected_behavior="reject"
        ))
        
        # Missing miner_id
        payloads.append(FuzzPayload(
            name="missing_miner_id",
            description="Missing required miner_id",
            payload={
                "miner_pubkey": "RTC" + "0" * 60,
                "device": {"family": "x86", "arch": "modern"}
            },
            expected_behavior="reject"
        ))
        
        # Missing device
        payloads.append(FuzzPayload(
            name="missing_device",
            description="Missing device object",
            payload={
                "miner_pubkey": "RTC" + "0" * 60,
                "miner_id": "test_miner"
            },
            expected_behavior="reject"
        ))
        
        return payloads
    
    def generate_nested_structures(self) -> List[FuzzPayload]:
        """Nested structure payloads."""
        payloads = []
        
        # Nested dict in device
        payloads.append(FuzzPayload(
            name="nested_device",
            description="Deeply nested device object",
            payload={
                "miner_pubkey": "RTC" + "0" * 60,
                "miner_id": "test_miner",
                "device": {
                    "family": "x86",
                    "arch": "modern",
                    "nested": {"level2": {"level3": {"value": "deep"}}}
                }
            },
            expected_behavior="accept_or_strip"
        ))
        
        # Array in string field
        payloads.append(FuzzPayload(
            name="array_in_string",
            description="Array where string expected",
            payload={
                "miner_pubkey": ["RTC"] * 10,
                "miner_id": "test_miner",
                "device": {"family": "x86", "arch": "modern"}
            },
            expected_behavior="reject"
        ))
        
        return payloads
    
    def generate_oversized_values(self) -> List[FuzzPayload]:
        """Oversized value payloads."""
        payloads = []
        
        # Very long string
        long_string = "A" * 10000
        payloads.append(FuzzPayload(
            name="oversized_pubkey",
            description="Extremely long pubkey",
            payload={
                "miner_pubkey": long_string,
                "miner_id": "test_miner",
                "device": {"family": "x86", "arch": "modern"}
            },
            expected_behavior="reject"
        ))
        
        # Very long array
        long_array = [{"key": "value"}] * 1000
        payloads.append(FuzzPayload(
            name="oversized_array",
            description="Extremely large array",
            payload={
                "miner_pubkey": "RTC" + "0" * 60,
                "miner_id": long_array,
                "device": {"family": "x86", "arch": "modern"}
            },
            expected_behavior="reject"
        ))
        
        return payloads
    
    def generate_boundary_timestamps(self) -> List[FuzzPayload]:
        """Boundary timestamp payloads."""
        payloads = []
        
        # Zero timestamp
        payloads.append(FuzzPayload(
            name="zero_timestamp",
            description="Zero timestamp",
            payload={
                "miner_pubkey": "RTC" + "0" * 60,
                "miner_id": "test_miner",
                "device": {"family": "x86", "arch": "modern"},
                "timestamp": 0
            },
            expected_behavior="accept_or_reject"
        ))
        
        # Negative timestamp
        payloads.append(FuzzPayload(
            name="negative_timestamp",
            description="Negative timestamp",
            payload={
                "miner_pubkey": "RTC" + "0" * 60,
                "miner_id": "test_miner",
                "device": {"family": "x86", "arch": "modern"},
                "timestamp": -1000000
            },
            expected_behavior="reject"
        ))
        
        # Future timestamp
        payloads.append(FuzzPayload(
            name="future_timestamp",
            description="Timestamp far in future",
            payload={
                "miner_pubkey": "RTC" + "0" * 60,
                "miner_id": "test_miner",
                "device": {"family": "x86", "arch": "modern"},
                "timestamp": 2000000000
            },
            expected_behavior="accept_or_warn"
        ))
        
        return payloads
    
    def generate_special_characters(self) -> List[FuzzPayload]:
        """Special character payloads."""
        payloads = []
        
        # Null bytes
        payloads.append(FuzzPayload(
            name="null_bytes",
            description="Null bytes in strings",
            payload={
                "miner_pubkey": "RTC\x00" + "0" * 55,
                "miner_id": "test_miner",
                "device": {"family": "x86", "arch": "modern"}
            },
            expected_behavior="reject"
        ))
        
        # Newlines
        payloads.append(FuzzPayload(
            name="newlines",
            description="Newlines in strings",
            payload={
                "miner_pubkey": "RTC\n" + "0" * 58,
                "miner_id": "test_miner\n",
                "device": {"family": "x86\n", "arch": "modern"}
            },
            expected_behavior="reject"
        ))
        
        # Unicode
        payloads.append(FuzzPayload(
            name="unicode_injection",
            description="Unicode injection",
            payload={
                "miner_pubkey": "RTC\u0000\u0001\u0002" + "0" * 55,
                "miner_id": "test_\u4e2d\u6587_miner",
                "device": {"family": "x86", "arch": "modern"}
            },
            expected_behavior="accept_or_strip"
        ))
        
        return payloads
    
    def generate_sql_injection(self) -> List[FuzzPayload]:
        """SQL injection test payloads."""
        payloads = []
        
        sql_injection = "'; DROP TABLE miners;--"
        payloads.append(FuzzPayload(
            name="sql_injection",
            description="SQL injection attempt",
            payload={
                "miner_pubkey": "RTC" + "0" * 60,
                "miner_id": sql_injection,
                "device": {"family": "x86", "arch": "modern"}
            },
            expected_behavior="reject"
        ))
        
        return payloads
    
    def generate_all(self) -> List[FuzzPayload]:
        """Generate all fuzz payloads."""
        all_payloads = []
        all_payloads.extend(self.generate_type_confusion())
        all_payloads.extend(self.generate_missing_fields())
        all_payloads.extend(self.generate_nested_structures())
        all_payloads.extend(self.generate_oversized_values())
        all_payloads.extend(self.generate_boundary_timestamps())
        all_payloads.extend(self.generate_special_characters())
        all_payloads.extend(self.generate_sql_injection())
        
        self.corpus = all_payloads
        return all_payloads
    
    def save_corpus(self, directory: str):
        """Save corpus to files."""
        os.makedirs(directory, exist_ok=True)
        
        for i, fuzz in enumerate(self.corpus):
            filename = f"{i:03d}_{fuzz.name}.json"
            filepath = os.path.join(directory, filename)
            
            with open(filepath, 'w') as f:
                json.dump({
                    "name": fuzz.name,
                    "description": fuzz.description,
                    "expected_behavior": fuzz.expected_behavior,
                    "payload": fuzz.payload
                }, f, indent=2)
        
        # Save manifest
        manifest = {
            "total": len(self.corpus),
            "categories": [
                "type_confusion",
                "missing_fields", 
                "nested_structures",
                "oversized_values",
                "boundary_timestamps",
                "special_characters",
                "sql_injection"
            ]
        }
        
        with open(os.path.join(directory, "manifest.json"), 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"Saved {len(self.corpus)} fuzz payloads to {directory}")


def run_fuzz_tests(base_url: str = "http://localhost:8099"):
    """Run fuzz tests against attestation endpoint."""
    import requests
    
    fuzzer = AttestationFuzzer()
    payloads = fuzzer.generate_all()
    
    results = {
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    endpoint = f"{base_url}/attest/submit"
    
    for fuzz in payloads:
        try:
            response = requests.post(endpoint, json=fuzz.payload, timeout=5)
            
            # Check if handled gracefully
            if response.status_code in [200, 400, 422]:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({
                    "name": fuzz.name,
                    "status": response.status_code,
                    "behavior": fuzz.expected_behavior
                })
        except Exception as e:
            # Exception might indicate vulnerability
            results["errors"].append({
                "name": fuzz.name,
                "error": str(e),
                "behavior": fuzz.expected_behavior
            })
    
    return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Attestation Fuzz Harness")
    parser.add_argument("--save-corpus", action="store_true", help="Save fuzz corpus")
    parser.add_argument("--corpus-dir", default="tools/fuzz_harness/corpus", help="Corpus directory")
    parser.add_argument("--run", action="store_true", help="Run fuzz tests")
    parser.add_argument("--url", default="http://localhost:8099", help="Base URL")
    
    args = parser.parse_args()
    
    fuzzer = AttestationFuzzer()
    payloads = fuzzer.generate_all()
    
    print(f"Generated {len(payloads)} fuzz payloads:")
    for p in payloads:
        print(f"  - {p.name}: {p.description}")
    
    if args.save_corpus:
        fuzzer.save_corpus(args.corpus_dir)
    
    if args.run:
        results = run_fuzz_tests(args.url)
        print(f"\nResults: {results['passed']} passed, {results['failed']} failed")


if __name__ == "__main__":
    main()
