// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import sqlite3
import requests
import yaml
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin
import time
import os

DB_PATH = "node/blockchain.db"

class APIValidator:
    def __init__(self, openapi_spec_path: str, base_url: str = "http://localhost:5000"):
        self.openapi_spec_path = openapi_spec_path
        self.base_url = base_url
        self.spec = None
        self.validation_results = []

    def load_openapi_spec(self) -> bool:
        """Load and validate OpenAPI specification"""
        try:
            with open(self.openapi_spec_path, 'r') as f:
                if self.openapi_spec_path.endswith('.yaml') or self.openapi_spec_path.endswith('.yml'):
                    self.spec = yaml.safe_load(f)
                else:
                    self.spec = json.load(f)
            return True
        except Exception as e:
            print(f"Failed to load OpenAPI spec: {e}")
            return False

    def get_node_status(self) -> Dict[str, Any]:
        """Check if node is running and accessible"""
        try:
            response = requests.get(f"{self.base_url}/api/stats", timeout=5)
            return {
                "accessible": response.status_code == 200,
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds()
            }
        except requests.RequestException as e:
            return {
                "accessible": False,
                "error": str(e),
                "response_time": None
            }

    def validate_endpoint(self, path: str, method: str, spec_info: Dict) -> Dict[str, Any]:
        """Validate single endpoint against live node"""
        result = {
            "path": path,
            "method": method,
            "success": False,
            "status_code": None,
            "response_time": None,
            "schema_valid": False,
            "errors": []
        }

        try:
            url = urljoin(self.base_url, path)
            start_time = time.time()

            if method.upper() == "GET":
                response = requests.get(url, timeout=10)
            elif method.upper() == "POST":
                # Use sample data if available in spec
                sample_data = self._get_sample_request_data(spec_info)
                response = requests.post(url, json=sample_data, timeout=10)
            else:
                result["errors"].append(f"Method {method} not implemented in validator")
                return result

            result["status_code"] = response.status_code
            result["response_time"] = time.time() - start_time

            # Check if response matches expected status codes
            expected_codes = list(spec_info.get("responses", {}).keys())
            if str(response.status_code) in expected_codes:
                result["success"] = True

                # Validate response schema if available
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        schema_valid = self._validate_response_schema(
                            response_data,
                            spec_info.get("responses", {}).get("200", {})
                        )
                        result["schema_valid"] = schema_valid
                    except json.JSONDecodeError:
                        result["errors"].append("Response is not valid JSON")
            else:
                result["errors"].append(f"Unexpected status code. Expected: {expected_codes}")

        except requests.RequestException as e:
            result["errors"].append(f"Request failed: {str(e)}")
        except Exception as e:
            result["errors"].append(f"Validation error: {str(e)}")

        return result

    def _get_sample_request_data(self, spec_info: Dict) -> Dict:
        """Extract sample request data from OpenAPI spec"""
        request_body = spec_info.get("requestBody", {})
        content = request_body.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema", {})

        # Generate basic sample data based on schema
        if "properties" in schema:
            sample = {}
            for prop, prop_info in schema["properties"].items():
                if prop_info.get("type") == "string":
                    sample[prop] = "test_value"
                elif prop_info.get("type") == "integer":
                    sample[prop] = 1
                elif prop_info.get("type") == "number":
                    sample[prop] = 1.0
                elif prop_info.get("type") == "boolean":
                    sample[prop] = True
            return sample

        return {}

    def _validate_response_schema(self, response_data: Any, response_spec: Dict) -> bool:
        """Basic schema validation for response data"""
        try:
            content = response_spec.get("content", {})
            json_content = content.get("application/json", {})
            schema = json_content.get("schema", {})

            if not schema:
                return True  # No schema to validate against

            # Basic type checking
            if "type" in schema:
                expected_type = schema["type"]
                if expected_type == "object" and not isinstance(response_data, dict):
                    return False
                elif expected_type == "array" and not isinstance(response_data, list):
                    return False
                elif expected_type == "string" and not isinstance(response_data, str):
                    return False
                elif expected_type in ["integer", "number"] and not isinstance(response_data, (int, float)):
                    return False

            # Check required properties for objects
            if isinstance(response_data, dict) and "properties" in schema:
                required = schema.get("required", [])
                for req_field in required:
                    if req_field not in response_data:
                        return False

            return True

        except Exception:
            return False

    def validate_all_endpoints(self) -> List[Dict[str, Any]]:
        """Validate all endpoints defined in OpenAPI spec"""
        if not self.spec:
            return []

        paths = self.spec.get("paths", {})
        results = []

        for path, path_info in paths.items():
            for method, method_info in path_info.items():
                if method.lower() in ["get", "post", "put", "delete", "patch"]:
                    result = self.validate_endpoint(path, method, method_info)
                    results.append(result)

        self.validation_results = results
        return results

    def get_blockchain_data(self) -> Dict[str, Any]:
        """Get current blockchain state for validation context"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                # Get basic stats
                cursor.execute("SELECT COUNT(*) FROM blocks")
                block_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM transactions")
                tx_count = cursor.fetchone()[0]

                # Get latest block
                cursor.execute("SELECT * FROM blocks ORDER BY block_number DESC LIMIT 1")
                latest_block = cursor.fetchone()

                return {
                    "block_count": block_count,
                    "transaction_count": tx_count,
                    "latest_block_number": latest_block[1] if latest_block else 0,
                    "database_accessible": True
                }
        except Exception as e:
            return {
                "database_accessible": False,
                "error": str(e)
            }

    def generate_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report"""
        if not self.validation_results:
            self.validate_all_endpoints()

        total_endpoints = len(self.validation_results)
        successful = sum(1 for r in self.validation_results if r["success"])
        schema_valid = sum(1 for r in self.validation_results if r["schema_valid"])

        node_status = self.get_node_status()
        blockchain_data = self.get_blockchain_data()

        return {
            "timestamp": time.time(),
            "node_status": node_status,
            "blockchain_data": blockchain_data,
            "validation_summary": {
                "total_endpoints": total_endpoints,
                "successful_endpoints": successful,
                "schema_valid_endpoints": schema_valid,
                "success_rate": (successful / total_endpoints * 100) if total_endpoints > 0 else 0,
                "schema_validity_rate": (schema_valid / total_endpoints * 100) if total_endpoints > 0 else 0
            },
            "endpoint_results": self.validation_results,
            "spec_info": {
                "openapi_version": self.spec.get("openapi") if self.spec else None,
                "title": self.spec.get("info", {}).get("title") if self.spec else None,
                "version": self.spec.get("info", {}).get("version") if self.spec else None
            }
        }

    def save_report(self, filename: str = "api_validation_report.json"):
        """Save validation report to file"""
        report = self.generate_validation_report()
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Validation report saved to {filename}")

def main():
    """Run API validation against OpenAPI spec"""
    spec_path = "openapi.yaml"

    if not os.path.exists(spec_path):
        print(f"OpenAPI spec not found at {spec_path}")
        print("Please create the OpenAPI specification first")
        return

    validator = APIValidator(spec_path)

    print("Loading OpenAPI specification...")
    if not validator.load_openapi_spec():
        return

    print("Checking node status...")
    node_status = validator.get_node_status()
    if not node_status["accessible"]:
        print(f"Node is not accessible: {node_status.get('error', 'Unknown error')}")
        print("Please ensure the RustChain node is running on localhost:5000")
        return

    print(f"Node is accessible (response time: {node_status['response_time']:.3f}s)")

    print("Validating API endpoints...")
    results = validator.validate_all_endpoints()

    print(f"\nValidation Results:")
    print(f"Total endpoints tested: {len(results)}")
    successful = sum(1 for r in results if r["success"])
    print(f"Successful: {successful}/{len(results)}")

    for result in results:
        status = "✓" if result["success"] else "✗"
        print(f"{status} {result['method'].upper()} {result['path']} - {result['status_code']}")
        if result["errors"]:
            for error in result["errors"]:
                print(f"    Error: {error}")

    validator.save_report()

if __name__ == "__main__":
    main()
