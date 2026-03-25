#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Validation Script for Issue #2312: Rent-a-Relic Market

This script validates the complete implementation of the
Rent-a-Relic Market bounty.
"""

import os
import sys
import json
import subprocess
import hashlib
from datetime import datetime


def print_header(text):
    print("\n" + "=" * 70)
    print(f" {text}")
    print("=" * 70)


def print_check(passed, message):
    status = "✓ PASS" if passed else "✗ FAIL"
    symbol = "✓" if passed else "✗"
    print(f"  [{symbol}] {message}")
    return passed


class ValidationResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.checks = []
    
    def add(self, passed, message):
        self.checks.append((passed, message))
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        print_check(passed, message)
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*70}")
        print(f" Validation Summary: {self.passed}/{total} checks passed")
        if self.failed == 0:
            print(" Status: ✓ ALL VALIDATIONS PASSED")
        else:
            print(f" Status: ✗ {self.failed} VALIDATIONS FAILED")
        print(f"{'='*70}\n")
        return self.failed == 0


def validate_directory_structure(results):
    """Validate all required files exist"""
    print_header("1. Directory Structure Validation")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    required_files = [
        "README.md",
        "src/relic_market_api.py",
        "src/relic_market_sdk.py",
        "src/marketplace.html",
        "src/requirements.txt",
        "tests/test_relic_market.py",
        "docs/API_REFERENCE.md",
        "docs/RUNBOOK.md",
        "examples/agent_booking.py",
        "examples/mcp_integration.py",
        "evidence/proof.json"
    ]
    
    for file_path in required_files:
        full_path = os.path.join(base_dir, file_path)
        exists = os.path.exists(full_path)
        results.add(exists, f"File exists: {file_path}")
    
    return results


def validate_api_implementation(results):
    """Validate API implementation"""
    print_header("2. API Implementation Validation")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    api_file = os.path.join(base_dir, "src/relic_market_api.py")
    
    with open(api_file, 'r') as f:
        content = f.read()
    
    # Check required endpoints
    required_endpoints = [
        ("/health", "Health check endpoint"),
        ("/relic/available", "List available machines"),
        ("/relic/reserve", "Reserve machine endpoint"),
        ("/relic/receipt/", "Get receipt endpoint"),
        ("/relic/leaderboard", "Leaderboard endpoint"),
        ("/mcp/manifest", "MCP manifest endpoint"),
        ("/mcp/tool", "MCP tool endpoint"),
        ("/beacon/message", "Beacon message endpoint"),
        ("/bottube/badge/", "BoTTube badge endpoint"),
    ]
    
    for endpoint, description in required_endpoints:
        exists = endpoint in content
        results.add(exists, f"API endpoint: {description} ({endpoint})")
    
    # Check core classes
    required_classes = [
        "MachineRegistry",
        "EscrowManager",
        "ReceiptSigner",
        "ReservationManager",
        "MCPIntegration",
        "BeaconIntegration"
    ]
    
    for class_name in required_classes:
        exists = f"class {class_name}" in content
        results.add(exists, f"Core class: {class_name}")
    
    # Check Ed25519 signing
    has_signing = "nacl.signing" in content and "Ed25519" in content
    results.add(has_signing, "Ed25519 cryptographic signing")
    
    # Check escrow
    has_escrow = "lock_funds" in content and "release_funds" in content
    results.add(has_escrow, "Escrow management (lock/release)")
    
    return results


def validate_sdk_implementation(results):
    """Validate SDK implementation"""
    print_header("3. SDK Implementation Validation")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sdk_file = os.path.join(base_dir, "src/relic_market_sdk.py")
    
    with open(sdk_file, 'r') as f:
        content = f.read()
    
    required_methods = [
        "list_machines",
        "reserve_machine",
        "get_reservation",
        "start_session",
        "complete_session",
        "get_receipt",
        "get_leaderboard",
        "call_mcp_tool",
        "send_beacon_message"
    ]
    
    for method in required_methods:
        exists = f"def {method}" in content
        results.add(exists, f"SDK method: {method}")
    
    # Check RelicComputeSession class
    has_session = "class RelicComputeSession" in content
    results.add(has_session, "High-level session manager")
    
    return results


def validate_ui_implementation(results):
    """Validate Marketplace UI"""
    print_header("4. Marketplace UI Validation")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ui_file = os.path.join(base_dir, "src/marketplace.html")
    
    with open(ui_file, 'r') as f:
        content = f.read()
    
    # Check UI components
    ui_checks = [
        ("machines-grid", "Machine grid display"),
        ("filter-architecture", "Architecture filter"),
        ("filter-price", "Price filter"),
        ("booking-modal", "Booking modal"),
        ("leaderboard", "Leaderboard display"),
        ("receipt-modal", "Receipt viewer"),
        ("/relic/available", "API integration"),
        ("/relic/reserve", "Reservation API call"),
        ("/relic/receipt/", "Receipt API call"),
    ]
    
    for check, description in ui_checks:
        exists = check in content
        results.add(exists, f"UI component: {description}")
    
    # Check styling
    has_styling = "<style>" in content and "var(--primary)" in content
    results.add(has_styling, "Fossil-punk themed styling")
    
    return results


def validate_tests(results):
    """Validate test suite"""
    print_header("5. Test Suite Validation")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_file = os.path.join(base_dir, "tests/test_relic_market.py")
    
    with open(test_file, 'r') as f:
        content = f.read()
    
    # Check test classes
    test_classes = [
        "TestVintageMachine",
        "TestMachineRegistry",
        "TestEscrowManager",
        "TestReceiptSigner",
        "TestReservationManager",
        "TestMCPIntegration",
        "TestBeaconIntegration",
        "TestAPIEndpoints"
    ]
    
    for class_name in test_classes:
        exists = f"class {class_name}" in content
        results.add(exists, f"Test class: {class_name}")
    
    # Check test can be run
    has_main = "if __name__ == '__main__'" in content
    results.add(has_main, "Test runner configured")
    
    return results


def validate_documentation(results):
    """Validate documentation"""
    print_header("6. Documentation Validation")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Check README
    readme_file = os.path.join(base_dir, "README.md")
    with open(readme_file, 'r') as f:
        readme = f.read()
    
    readme_checks = [
        ("Overview", "Overview section"),
        ("Features", "Features section"),
        ("Quick Start", "Quick start guide"),
        ("API Endpoints", "API documentation"),
        ("MCP", "MCP integration docs"),
        ("Beacon", "Beacon integration docs"),
        ("Testing", "Testing instructions"),
    ]
    
    for check, description in readme_checks:
        exists = check in readme
        results.add(exists, f"README: {description}")
    
    # Check API Reference
    api_ref = os.path.join(base_dir, "docs/API_REFERENCE.md")
    with open(api_ref, 'r') as f:
        api_content = f.read()
    
    results.add("GET /relic/available" in api_content, "API Reference: Endpoint docs")
    results.add("POST /relic/reserve" in api_content, "API Reference: Request examples")
    
    return results


def validate_examples(results):
    """Validate example code"""
    print_header("7. Example Code Validation")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Agent booking example
    booking_file = os.path.join(base_dir, "examples/agent_booking.py")
    with open(booking_file, 'r') as f:
        booking = f.read()
    
    results.add("RelicMarketClient" in booking, "Example: SDK client usage")
    results.add("RelicComputeSession" in booking, "Example: Session management")
    results.add("session.book" in booking, "Example: Booking flow")
    results.add("session.complete" in booking, "Example: Completion flow")
    
    # MCP example
    mcp_file = os.path.join(base_dir, "examples/mcp_integration.py")
    with open(mcp_file, 'r') as f:
        mcp = f.read()
    
    results.add("MCPClient" in mcp, "Example: MCP client")
    results.add("call_tool" in mcp, "Example: Tool calling")
    results.add("list_machines" in mcp, "Example: list_machines tool")
    results.add("reserve_machine" in mcp, "Example: reserve_machine tool")
    
    return results


def validate_proof(results):
    """Validate proof.json"""
    print_header("8. Evidence/Proof Validation")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proof_file = os.path.join(base_dir, "evidence/proof.json")
    
    with open(proof_file, 'r') as f:
        proof = json.load(f)
    
    # Check required fields
    required_fields = [
        "bounty_id",
        "title",
        "status",
        "implementation_summary",
        "files_created",
        "requirements_met",
        "bonus_objectives",
        "commit_message"
    ]
    
    for field in required_fields:
        exists = field in proof
        results.add(exists, f"Proof.json: {field}")
    
    # Validate requirements
    reqs = proof.get("requirements_met", {})
    results.add(reqs.get("machine_registry", {}).get("implemented"), "Requirement: Machine Registry")
    results.add(reqs.get("reservation_system", {}).get("implemented"), "Requirement: Reservation System")
    results.add(reqs.get("provenance_receipt", {}).get("implemented"), "Requirement: Provenance Receipt")
    results.add(reqs.get("marketplace_ui", {}).get("implemented"), "Requirement: Marketplace UI")
    results.add(reqs.get("api_endpoints", {}).get("implemented"), "Requirement: API Endpoints")
    
    # Validate bonus
    bonus = proof.get("bonus_objectives", {})
    results.add(bonus.get("bottube_integration", {}).get("status") == "completed", "Bonus: BoTTube Integration")
    results.add(bonus.get("leaderboard", {}).get("status") == "completed", "Bonus: Leaderboard")
    
    # Check commit message
    commit_msg = proof.get("commit_message", "")
    correct_msg = commit_msg == "feat: implement issue #2312 rent-a-relic market"
    results.add(correct_msg, f"Commit message: {commit_msg}")
    
    return results


def run_unit_tests(results):
    """Run unit tests"""
    print_header("9. Unit Test Execution")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_file = os.path.join(base_dir, "tests/test_relic_market.py")

    try:
        result = subprocess.run(
            [sys.executable, test_file],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=60
        )

        success = result.returncode == 0
        results.add(success, "Unit tests execute successfully")

        # Parse test output - check for "OK" at the end (unittest success message)
        output = result.stdout + result.stderr
        if result.returncode == 0 and "OK" in output:
            results.add(True, "All test cases passed")
        else:
            results.add(False, "Some test cases failed")

    except subprocess.TimeoutExpired:
        results.add(False, "Unit tests timed out (>60s)")
    except Exception as e:
        results.add(False, f"Unit test execution error: {str(e)}")

    return results


def validate_requirements(results):
    """Validate Python dependencies"""
    print_header("10. Dependencies Validation")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    req_file = os.path.join(base_dir, "src/requirements.txt")
    
    with open(req_file, 'r') as f:
        content = f.read()
    
    required_deps = [
        ("Flask", "Flask web framework"),
        ("PyNaCl", "NaCl cryptography library"),
    ]
    
    for dep, description in required_deps:
        exists = dep in content
        results.add(exists, f"Dependency: {description} ({dep})")
    
    return results


def main():
    print("\n" + "█" * 70)
    print("█" + " " * 68 + "█")
    print("█  Issue #2312: Rent-a-Relic Market - Validation Script    █")
    print("█" + " " * 68 + "█")
    print("█" * 70)
    print(f"\n  Timestamp: {datetime.now().isoformat()}")
    print(f"  Python: {sys.version.split()[0]}")
    
    results = ValidationResults()
    
    # Run all validations
    validate_directory_structure(results)
    validate_api_implementation(results)
    validate_sdk_implementation(results)
    validate_ui_implementation(results)
    validate_tests(results)
    validate_documentation(results)
    validate_examples(results)
    validate_proof(results)
    run_unit_tests(results)
    validate_requirements(results)
    
    # Print summary
    all_passed = results.summary()
    
    if all_passed:
        print("✓ Implementation is COMPLETE and VALIDATED")
        print("✓ Ready for bounty submission")
        print("\nCommit with message:")
        print("  feat: implement issue #2312 rent-a-relic market")
        return 0
    else:
        print("✗ Some validations failed")
        print("✗ Please review and fix the issues above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
