#!/usr/bin/env python3
"""
RustChain Attestation Endpoint Fuzzer
Sends malformed payloads to /attest/submit and documents responses.
"""

import json
import random
import string
import sys
import time
from datetime import datetime
from typing import Dict, List, Any

import requests


# Attestation nodes to test
NODES = [
    {"name": "Node 1", "host": "50.28.86.131", "port": 8099},
    {"name": "Node 2", "host": "50.28.86.153", "port": 8099},
    {"name": "Node 3", "host": "76.8.228.245", "port": 8099},
]

# Attestation submit endpoint
ATTEST_SUBMIT_ENDPOINT = "/attest/submit"


def generate_random_string(length: int = 10) -> str:
    """Generate random string."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_malformed_payloads() -> List[Dict[str, Any]]:
    """Generate various malformed payloads for fuzzing."""
    payloads = []
    
    # 1. Missing fields
    payloads.append({"name": "missing_all_fields", "payload": {}})
    payloads.append({"name": "missing_data", "payload": {"timestamp": int(time.time())}})
    payloads.append({"name": "missing_timestamp", "payload": {"data": "test"}})
    
    # 2. Wrong types
    payloads.append({"name": "timestamp_string", "payload": {"data": "test", "timestamp": "not_a_number"}})
    payload_id = generate_random_string(16)
    payloads.append({"name": "data_number", "payload": {"data": 12345, "timestamp": int(time.time()), "id": payload_id}})
    payloads.append({"name": "timestamp_float", "payload": {"data": "test", "timestamp": 1234567890.5}})
    payloads.append({"name": "data_null", "payload": {"data": None, "timestamp": int(time.time())}})
    payloads.append({"name": "data_bool", "payload": {"data": True, "timestamp": int(time.time())}})
    
    # 3. Oversized data
    large_data = generate_random_string(10000)  # 10KB
    payloads.append({"name": "oversized_data_10kb", "payload": {"data": large_data, "timestamp": int(time.time())}})
    large_data = generate_random_string(100000)  # 100KB
    payloads.append({"name": "oversized_data_100kb", "payload": {"data": large_data, "timestamp": int(time.time())}})
    
    # 4. Injection attempts
    injection_payloads = [
        ("sql_injection", "'; DROP TABLE attestations; --"),
        ("xss_payload", "<script>alert('xss')</script>"),
        ("path_traversal", "../../../etc/passwd"),
        ("null_byte", "test\x00string"),
        ("format_string", "{__import__('os').system('ls')"),
        ("unicode_overflow", "\u0000" * 100),
    ]
    for name, value in injection_payloads:
        payloads.append({
            "name": name,
            "payload": {"data": value, "timestamp": int(time.time())}
        })
    
    # 5. Empty values
    payloads.append({"name": "empty_data", "payload": {"data": "", "timestamp": int(time.time())}})
    payloads.append({"name": "empty_object", "payload": {"data": {}, "timestamp": int(time.time())}})
    payloads.append({"name": "empty_array", "payload": {"data": [], "timestamp": int(time.time())}})
    
    # 6. Invalid JSON structures
    payloads.append({"name": "nested_empty", "payload": {"data": {"nested": {}}, "timestamp": int(time.time())}})
    payloads.append({"name": "array_of_arrays", "payload": {"data": [[1, 2], [3, 4]], "timestamp": int(time.time())}})
    
    # 7. Special characters
    special_chars = ["\n", "\r", "\t", "\\", "\\\\", "\"", "'", "`"]
    for char in special_chars:
        payloads.append({
            "name": f"special_char_{repr(char)}",
            "payload": {"data": f"test{char}value", "timestamp": int(time.time())}
        })
    
    return payloads


def send_payload(node: Dict, payload: Dict) -> Dict:
    """Send a payload to a node and get the response."""
    url = f"http://{node['host']}:{node['port']}{ATTEST_SUBMIT_ENDPOINT}"
    result = {
        "node": node["name"],
        "payload_name": payload["name"],
        "payload": payload["payload"],
    }
    
    try:
        response = requests.post(
            url,
            json=payload["payload"],
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        result["status_code"] = response.status_code
        result["response"] = response.text[:500]  # Truncate response
        
        # Determine category
        if response.status_code == 500:
            result["category"] = "BUG (500)"
            result["is_bug"] = True
        elif response.status_code == 400:
            result["category"] = "VALIDATION_ERROR (400)"
            result["is_bug"] = False
        elif response.status_code == 422:
            result["category"] = "UNPROCESSABLE (422)"
            result["is_bug"] = False
        elif response.status_code == 200:
            result["category"] = "SUCCESS (200)"
            result["is_bug"] = False
        else:
            result["category"] = f"OTHER ({response.status_code})"
            result["is_bug"] = False
            
    except requests.exceptions.Timeout:
        result["status_code"] = 0
        result["category"] = "TIMEOUT"
        result["response"] = "Request timed out"
        result["is_bug"] = False
    except requests.exceptions.ConnectionError:
        result["status_code"] = 0
        result["category"] = "CONNECTION_ERROR"
        result["response"] = "Could not connect to node"
        result["is_bug"] = False
    except Exception as e:
        result["status_code"] = 0
        result["category"] = "ERROR"
        result["response"] = str(e)
        result["is_bug"] = False
    
    return result


def print_results_table(results: List[Dict]):
    """Print fuzzing results in table format."""
    print("\n" + "=" * 120)
    print(f"RustChain Attestation Endpoint Fuzzing Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 120)
    print()
    print(f"{'Payload Name':<35} {'Node':<10} {'Status':<8} {'Category':<25} {'Bug?':<6}")
    print("-" * 120)
    
    bugs_found = []
    for result in results:
        name = result["payload_name"][:34]
        node = result["node"]
        status = str(result.get("status_code", "N/A"))
        category = result.get("category", "UNKNOWN")[:24]
        bug = "YES!" if result.get("is_bug") else "-"
        
        print(f"{name:<35} {node:<10} {status:<8} {category:<25} {bug:<6}")
        
        if result.get("is_bug"):
            bugs_found.append(result)
    
    print("-" * 120)
    
    # Summary
    total = len(results)
    bugs = len(bugs_found)
    validation_errors = sum(1 for r in results if r.get("category") == "VALIDATION_ERROR (400)")
    
    print(f"\nSummary:")
    print(f"  Total payloads tested: {total}")
    print(f"  Potential bugs (500 errors): {bugs}")
    print(f"  Proper validation (400): {validation_errors}")
    print(f"  Other responses: {total - bugs - validation_errors}")
    
    if bugs_found:
        print(f"\n🐛 BUGS FOUND ({bugs}):")
        for bug in bugs_found:
            print(f"  - {bug['payload_name']} on {bug['node']}: {bug.get('response', '')[:100]}")
    
    print()


def save_results_json(results: List[Dict], filename: str = "fuzz_results.json"):
    """Save results to JSON file."""
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_payloads": len(results),
        "bugs_found": sum(1 for r in results if r.get("is_bug")),
        "results": results
    }
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results saved to {filename}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="RustChain Attestation Endpoint Fuzzer"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=100,
        help="Maximum number of payloads to test (default: 100)"
    )
    parser.add_argument(
        "--node", "-n",
        type=int,
        choices=[1, 2, 3],
        help="Test specific node only (1, 2, or 3)"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="Save results to JSON file"
    )
    
    args = parser.parse_args()
    
    # Generate payloads
    payloads = generate_malformed_payloads()
    if len(payloads) > args.limit:
        payloads = payloads[:args.limit]
    
    print(f"Generated {len(payloads)} test payloads")
    
    # Determine which nodes to test
    if args.node:
        nodes_to_test = [NODES[args.node - 1]]
    else:
        nodes_to_test = NODES
    
    print(f"Testing {len(nodes_to_test)} node(s)")
    
    # Run fuzzing
    results = []
    for node in nodes_to_test:
        print(f"\nTesting {node['name']} ({node['host']}:{node['port']})...")
        for i, payload in enumerate(payloads):
            print(f"  [{i+1}/{len(payloads)}] Testing: {payload['name']}...", end=" ", flush=True)
            result = send_payload(node, payload)
            results.append(result)
            print(f"→ {result.get('category', 'ERROR')}")
            time.sleep(0.1)  # Small delay between requests
    
    # Output results
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_results_table(results)
    
    if args.save:
        save_results_json(results)
    
    # Exit code: 1 if bugs found, 0 otherwise
    bugs_found = sum(1 for r in results if r.get("is_bug"))
    sys.exit(1 if bugs_found > 0 else 0)


if __name__ == "__main__":
    main()
