#!/usr/bin/env python3
"""
RustChain Postman Collection Validation Script
Issue #1617 - Postman Collection for RustChain API

This script validates the Postman collection files and provides a checklist
for testing all API endpoints.

Usage:
    python validate_postman_collection.py [--live-test]
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Any

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


def validate_json_file(filepath: str) -> bool:
    """Validate that a file is valid JSON."""
    try:
        with open(filepath, 'r') as f:
            json.load(f)
        return True
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
        return False
    except FileNotFoundError:
        print_error(f"File not found: {filepath}")
        return False


def validate_collection_structure(collection: Dict[str, Any]) -> List[str]:
    """Validate the Postman collection structure."""
    errors = []
    
    # Check required fields
    if 'info' not in collection:
        errors.append("Missing 'info' section")
    else:
        if 'name' not in collection['info']:
            errors.append("Missing collection name")
        if 'schema' not in collection['info']:
            errors.append("Missing schema URL")
    
    if 'item' not in collection:
        errors.append("Missing 'item' array")
        return errors
    
    # Check for expected folders
    expected_folders = [
        '01_Health_Status',
        '02_Epoch_Network',
        '03_Fee_Pool',
        '04_Wallet_Balance',
        '06_Attestation',
        '07_Wallet_Transfers',
        '08_Withdrawals'
    ]
    
    folder_names = [item.get('name', '') for item in collection['item']]
    
    for expected in expected_folders:
        if expected not in folder_names:
            errors.append(f"Missing expected folder: {expected}")
    
    # Count total requests
    request_count = 0
    response_count = 0
    
    def count_items(items):
        nonlocal request_count, response_count
        for item in items:
            if 'request' in item:
                request_count += 1
                if 'response' in item:
                    response_count += len(item['response'])
            if 'item' in item:
                count_items(item['item'])
    
    count_items(collection['item'])
    
    print_info(f"Total requests: {request_count}")
    print_info(f"Total example responses: {response_count}")
    
    if request_count < 10:
        errors.append(f"Too few requests ({request_count}), expected at least 10")
    
    if response_count < 15:
        print_warning(f"Only {response_count} example responses, consider adding more")
    
    return errors


def validate_environment_structure(environment: Dict[str, Any]) -> List[str]:
    """Validate the Postman environment structure."""
    errors = []
    
    if 'name' not in environment:
        errors.append("Missing environment name")
    
    if 'values' not in environment:
        errors.append("Missing 'values' array")
        return errors
    
    expected_vars = ['base_url', 'miner_id', 'admin_key']
    var_names = [v.get('key', '') for v in environment['values']]
    
    for expected in expected_vars:
        if expected not in var_names:
            errors.append(f"Missing expected variable: {expected}")
    
    # Check that admin_key is marked as secret
    for var in environment['values']:
        if var.get('key') == 'admin_key' and var.get('type') != 'secret':
            print_warning("admin_key should be marked as 'secret' type")
    
    return errors


def validate_collection_references(collection: Dict[str, Any], environment: Dict[str, Any]) -> List[str]:
    """Validate that collection variables match environment variables."""
    errors = []
    
    env_vars = {v.get('key') for v in environment.get('values', [])}
    collection_vars = {v.get('key') for v in collection.get('variable', [])}
    
    # Check for collection vars not in environment
    missing_in_env = collection_vars - env_vars - {None}
    if missing_in_env:
        print_warning(f"Collection variables not in environment: {missing_in_env}")
    
    return errors


def generate_checklist(collection: Dict[str, Any]) -> str:
    """Generate a validation checklist from the collection."""
    checklist = []
    
    def process_items(items, folder_name=""):
        for item in items:
            if 'request' in item:
                request = item['request']
                method = request.get('method', 'GET')
                name = item.get('name', 'Unknown')
                url = request.get('url', {})
                
                if isinstance(url, dict):
                    path = '/'.join(url.get('path', []))
                    full_url = f"{{{{base_url}}}}/{path}" if path else "N/A"
                else:
                    full_url = url
                
                checklist.append({
                    'folder': folder_name,
                    'name': name,
                    'method': method,
                    'url': full_url,
                    'has_examples': 'response' in item and len(item['response']) > 0
                })
            elif 'item' in item:
                process_items(item['item'], item.get('name', ''))
    
    process_items(collection['item'])
    return checklist


def print_checklist(checklist: List[Dict]):
    """Print the validation checklist."""
    print_header("ENDPOINT VALIDATION CHECKLIST")
    
    current_folder = None
    for item in checklist:
        if item['folder'] != current_folder:
            current_folder = item['folder']
            print(f"\n{Colors.BOLD}{current_folder}{Colors.RESET}")
        
        status = "✓" if item['has_examples'] else "⚠"
        color = Colors.GREEN if item['has_examples'] else Colors.YELLOW
        
        print(f"  {color}{status}{Colors.RESET} [{item['method']}] {item['name']}")
        print(f"      {item['url']}")


def run_live_tests(collection: Dict[str, Any], base_url: str = None) -> None:
    """Run live tests against the API (optional)."""
    print_header("LIVE API TESTS (Optional)")
    print_warning("These tests will make real API calls to the RustChain node")
    
    try:
        import requests
    except ImportError:
        print_error("requests library not installed. Run: pip install requests")
        return
    
    # Get base URL from environment or use default
    if not base_url:
        for var in collection.get('variable', []):
            if var.get('key') == 'base_url':
                base_url = var.get('value', 'https://rustchain.org')
                break
    
    print_info(f"Testing against: {base_url}")
    
    # Test public endpoints
    public_endpoints = [
        ('GET', '/health'),
        ('GET', '/ready'),
        ('GET', '/epoch'),
        ('GET', '/api/stats'),
        ('GET', '/api/miners'),
        ('GET', '/api/fee_pool'),
    ]
    
    for method, path in public_endpoints:
        url = f"{base_url}{path}"
        try:
            if method == 'GET':
                response = requests.get(url, timeout=10, verify=False)
            
            if response.status_code == 200:
                print_success(f"{method} {path} - {response.status_code}")
            else:
                print_warning(f"{method} {path} - {response.status_code}")
        except requests.exceptions.RequestException as e:
            print_error(f"{method} {path} - Error: {e}")


def main():
    """Main validation function."""
    print_header("RUSTCHAIN POSTMAN COLLECTION VALIDATION")
    print_info("Issue #1617 - Complete Postman Collection for RustChain API")
    
    # Determine paths
    script_dir = Path(__file__).parent
    collection_path = script_dir / "RustChain_API.postman_collection.json"
    environment_path = script_dir / "RustChain_Environment.postman_environment.json"
    
    # Check for alternative paths (if running from different directory)
    if not collection_path.exists():
        collection_path = Path("docs/postman/RustChain_API.postman_collection.json")
    if not environment_path.exists():
        environment_path = Path("docs/postman/RustChain_Environment.postman_environment.json")
    
    print_info(f"Collection path: {collection_path}")
    print_info(f"Environment path: {environment_path}")
    
    # Validate collection file
    print_header("VALIDATING COLLECTION FILE")
    if not validate_json_file(str(collection_path)):
        print_error("Collection file is not valid JSON")
        sys.exit(1)
    print_success("Collection file is valid JSON")
    
    with open(collection_path, 'r') as f:
        collection = json.load(f)
    
    errors = validate_collection_structure(collection)
    if errors:
        for error in errors:
            print_error(error)
        sys.exit(1)
    else:
        print_success("Collection structure is valid")
    
    # Validate environment file
    print_header("VALIDATING ENVIRONMENT FILE")
    if not validate_json_file(str(environment_path)):
        print_error("Environment file is not valid JSON")
        sys.exit(1)
    print_success("Environment file is valid JSON")
    
    with open(environment_path, 'r') as f:
        environment = json.load(f)
    
    errors = validate_environment_structure(environment)
    if errors:
        for error in errors:
            print_error(error)
        sys.exit(1)
    else:
        print_success("Environment structure is valid")
    
    # Cross-validate
    print_header("CROSS-VALIDATION")
    errors = validate_collection_references(collection, environment)
    if errors:
        for error in errors:
            print_warning(error)
    else:
        print_success("Collection and environment are consistent")
    
    # Generate and print checklist
    checklist = generate_checklist(collection)
    print_checklist(checklist)
    
    # Summary
    print_header("VALIDATION SUMMARY")
    print_success("All validation checks passed!")
    print_info(f"Collection: {collection['info'].get('name', 'Unknown')}")
    print_info(f"Version: {collection['info'].get('version', 'Unknown')}")
    print_info(f"Total folders: {len(collection['item'])}")
    print_info(f"Total example responses: {sum(len(item.get('response', [])) for folder in collection['item'] for item in folder.get('item', []) if 'response' in item)}")
    
    # Check for --live-test flag
    if len(sys.argv) > 1 and sys.argv[1] == '--live-test':
        run_live_tests(collection)
    
    print("\n" + "="*60)
    print("Next Steps:")
    print("1. Import collection into Postman: File → Import → Select RustChain_API.postman_collection.json")
    print("2. Import environment: File → Import → Select RustChain_Environment.postman_environment.json")
    print("3. Configure environment variables (miner_id, admin_key, etc.)")
    print("4. Test public endpoints first (no authentication required)")
    print("5. Test authenticated endpoints with valid admin key")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
