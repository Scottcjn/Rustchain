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
            # Make request to endpoint
            url = urljoin(self.base_url, path)
            start_time = time.time()

            if method.lower() == 'get':
                response = requests.get(url, timeout=10)
            elif method.lower() == 'post':
                response = requests.post(url, json={}, timeout=10)
            else:
                result["errors"].append(f"Unsupported method: {method}")
                return result

            result["response_time"] = time.time() - start_time
            result["status_code"] = response.status_code

            # Check if response is successful
            if response.status_code < 400:
                result["success"] = True

                # Try to validate response schema if available
                try:
                    response_data = response.json()
                    result["schema_valid"] = True
                except json.JSONDecodeError:
                    result["errors"].append("Invalid JSON response")
            else:
                result["errors"].append(f"HTTP {response.status_code}: {response.text}")

        except requests.RequestException as e:
            result["errors"].append(f"Request failed: {str(e)}")
        except Exception as e:
            result["errors"].append(f"Validation error: {str(e)}")

        return result

    def validate_all_endpoints(self) -> List[Dict[str, Any]]:
        """Validate all endpoints defined in OpenAPI spec"""
        if not self.spec:
            if not self.load_openapi_spec():
                return []

        results = []
        paths = self.spec.get('paths', {})

        for path, methods in paths.items():
            for method, spec_info in methods.items():
                if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                    result = self.validate_endpoint(path, method.upper(), spec_info)
                    results.append(result)
                    self.validation_results.append(result)

        return results

    def generate_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report"""
        if not self.validation_results:
            self.validate_all_endpoints()

        total_endpoints = len(self.validation_results)
        successful_endpoints = len([r for r in self.validation_results if r['success']])
        failed_endpoints = total_endpoints - successful_endpoints

        return {
            "summary": {
                "total_endpoints": total_endpoints,
                "successful": successful_endpoints,
                "failed": failed_endpoints,
                "success_rate": (successful_endpoints / total_endpoints * 100) if total_endpoints > 0 else 0
            },
            "node_status": self.get_node_status(),
            "endpoint_results": self.validation_results,
            "timestamp": time.time()
        }

    def save_report_to_db(self, report: Dict[str, Any]) -> bool:
        """Save validation report to database"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                # Create table if not exists
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS api_validation_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL,
                        total_endpoints INTEGER,
                        successful_endpoints INTEGER,
                        failed_endpoints INTEGER,
                        success_rate REAL,
                        node_accessible BOOLEAN,
                        report_data TEXT
                    )
                ''')

                # Insert report
                cursor.execute('''
                    INSERT INTO api_validation_reports (
                        timestamp, total_endpoints, successful_endpoints,
                        failed_endpoints, success_rate, node_accessible, report_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    report['timestamp'],
                    report['summary']['total_endpoints'],
                    report['summary']['successful'],
                    report['summary']['failed'],
                    report['summary']['success_rate'],
                    report['node_status']['accessible'],
                    json.dumps(report)
                ))

                conn.commit()
                return True

        except Exception as e:
            print(f"Failed to save report to database: {e}")
            return False

    def get_latest_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get latest validation reports from database"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT report_data FROM api_validation_reports
                    ORDER BY timestamp DESC LIMIT ?
                ''', (limit,))

                reports = []
                for row in cursor.fetchall():
                    reports.append(json.loads(row[0]))

                return reports

        except Exception as e:
            print(f"Failed to retrieve reports from database: {e}")
            return []

def main():
    """Main function for running API validation"""
    validator = APIValidator('openapi.yaml')

    print("Loading OpenAPI specification...")
    if not validator.load_openapi_spec():
        print("Failed to load OpenAPI spec. Exiting.")
        return

    print("Validating API endpoints...")
    results = validator.validate_all_endpoints()

    print("Generating validation report...")
    report = validator.generate_validation_report()

    print(f"\nValidation Report:")
    print(f"Total endpoints: {report['summary']['total_endpoints']}")
    print(f"Successful: {report['summary']['successful']}")
    print(f"Failed: {report['summary']['failed']}")
    print(f"Success rate: {report['summary']['success_rate']:.2f}%")
    print(f"Node accessible: {report['node_status']['accessible']}")

    # Save report to database
    if validator.save_report_to_db(report):
        print("\nReport saved to database.")
    else:
        print("\nFailed to save report to database.")

    # Print detailed results
    print("\nDetailed Results:")
    for result in results:
        status = "✓" if result['success'] else "✗"
        print(f"{status} {result['method']} {result['path']} - {result['status_code']}")
        if result['errors']:
            for error in result['errors']:
                print(f"    Error: {error}")

if __name__ == "__main__":
    main()
