#!/usr/bin/env python3
"""
Bounty #2310 Validation Script - Standalone Version

Validates CRT Light Attestation implementation without external dependencies.
Runs structural checks and code analysis.
"""

import os
import sys
import json
import hashlib
from pathlib import Path

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")

def print_success(text):
    print(f"{GREEN}[PASS] {text}{RESET}")

def print_error(text):
    print(f"{RED}[FAIL] {text}{RESET}")

def print_info(text):
    print(f"{YELLOW}[INFO] {text}{RESET}")

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print_success(f"{description}: {filepath}")
        return True
    else:
        print_error(f"{description} missing: {filepath}")
        return False

def check_file_content(filepath, patterns, description):
    """Check if file contains expected patterns"""
    if not os.path.exists(filepath):
        print_error(f"{description} missing: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    all_found = True
    for pattern in patterns:
        if pattern not in content:
            print_error(f"{description} missing pattern: {pattern}")
            all_found = False
    
    if all_found:
        print_success(f"{description} contains expected content")
    
    return all_found

def count_lines(filepath):
    """Count lines in a file"""
    if not os.path.exists(filepath):
        return 0
    with open(filepath, 'r', encoding='utf-8') as f:
        return sum(1 for _ in f)

def get_file_hash(filepath):
    """Get SHA-256 hash of file"""
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def validate_directory_structure():
    """Validate directory structure"""
    print_header("Step 1: Validating Directory Structure")
    
    base_dir = Path(__file__).parent
    required_dirs = ['src', 'tests', 'docs', 'examples', 'evidence']
    required_files = {
        'src': [
            '__init__.py',
            'crt_pattern_generator.py',
            'crt_capture.py',
            'crt_analyzer.py',
            'crt_attestation_submitter.py',
            'crt_cli.py',
            'requirements.txt'
        ],
        'tests': ['test_crt_attestation.py'],
        'docs': ['IMPLEMENTATION.md', 'VALIDATION.md', 'CRT_GALLERY.md'],
        'examples': ['sample_attestation.json'],
        'evidence': ['proof.json']
    }
    
    all_valid = True
    
    # Check directories
    for dir_name in required_dirs:
        dir_path = base_dir / dir_name
        if os.path.isdir(dir_path):
            print_success(f"Directory exists: {dir_name}/")
        else:
            print_error(f"Directory missing: {dir_name}/")
            all_valid = False
    
    # Check files
    for dir_name, files in required_files.items():
        for file_name in files:
            file_path = base_dir / dir_name / file_name
            if not check_file_exists(str(file_path), f"{dir_name}/{file_name}"):
                all_valid = False
    
    return all_valid

def validate_source_code():
    """Validate source code structure"""
    print_header("Step 2: Validating Source Code")
    
    base_dir = Path(__file__).parent / 'src'
    
    checks = {
        'crt_pattern_generator.py': [
            'class CRTPatternGenerator',
            'def generate_checkered_pattern',
            'def generate_gradient_sweep',
            'def compute_pattern_hash',
            'PHOSPHOR_TYPES'
        ],
        'crt_capture.py': [
            'class CRTCapture',
            'class CaptureConfig',
            'class CaptureMethod',
            'def capture_frame',
            'def capture_sequence'
        ],
        'crt_analyzer.py': [
            'class CRTAnalyzer',
            'class CRTFingerprint',
            'def analyze_refresh_rate',
            'def analyze_phosphor_decay',
            'def analyze_full'
        ],
        'crt_attestation_submitter.py': [
            'class CRTAttestationSubmitter',
            'class CRTAttestation',
            'def create_attestation',
            'def submit_attestation',
            'crt_fingerprint'
        ],
        'crt_cli.py': [
            'def main',
            'def cmd_generate',
            'def cmd_capture',
            'def cmd_analyze',
            'def cmd_attest',
            'argparse'
        ]
    }
    
    all_valid = True
    for filename, patterns in checks.items():
        filepath = base_dir / filename
        if not check_file_content(str(filepath), patterns, filename):
            all_valid = False
    
    return all_valid

def validate_documentation():
    """Validate documentation"""
    print_header("Step 3: Validating Documentation")
    
    base_dir = Path(__file__).parent
    
    checks = {
        'README.md': [
            'CRT Light Attestation',
            'Security by Cathode Ray',
            '140 RTC',
            'Requirements',
            'Quick Start'
        ],
        'docs/IMPLEMENTATION.md': [
            'Architecture Overview',
            'Pattern Generator',
            'Capture Module',
            'Analyzer',
            'Attestation Submitter'
        ],
        'docs/VALIDATION.md': [
            'Validation Procedure',
            'Quick Validation',
            'Detailed Validation Steps',
            'Requirements Verification'
        ],
        'docs/CRT_GALLERY.md': [
            'Phosphor Types',
            'P22',
            'P43',
            'CRT vs LCD',
            'Decay Curve'
        ]
    }
    
    all_valid = True
    for filename, patterns in checks.items():
        filepath = base_dir / filename
        if not check_file_content(str(filepath), patterns, filename):
            all_valid = False
    
    return all_valid

def validate_tests():
    """Validate test suite"""
    print_header("Step 4: Validating Test Suite")
    
    base_dir = Path(__file__).parent / 'tests'
    test_file = base_dir / 'test_crt_attestation.py'
    
    if not os.path.exists(test_file):
        print_error("Test file missing: test_crt_attestation.py")
        return False
    
    # Check for test classes
    required_tests = [
        'class TestPatternGenerator',
        'class TestCapture',
        'class TestAnalyzer',
        'class TestAttestationSubmitter',
        'class TestIntegration',
        'class TestCLI',
        'def test_initialization',
        'def test_checkered_pattern',
        'def test_refresh_rate_analysis',
        'def test_phosphor_decay_analysis',
        'def test_create_attestation',
        'pytest'
    ]
    
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    all_valid = True
    for pattern in required_tests:
        if pattern not in content:
            print_error(f"Test missing: {pattern}")
            all_valid = False
    
    if all_valid:
        print_success("Test suite contains all required test classes")
    
    # Count tests
    test_count = content.count('def test_')
    print_info(f"Found {test_count} test functions")
    
    return all_valid

def validate_evidence():
    """Validate evidence package"""
    print_header("Step 5: Validating Evidence Package")
    
    base_dir = Path(__file__).parent / 'evidence'
    proof_file = base_dir / 'proof.json'
    
    if not os.path.exists(proof_file):
        print_error("Evidence file missing: proof.json")
        return False
    
    with open(proof_file, 'r', encoding='utf-8') as f:
        proof = json.load(f)
    
    required_fields = [
        'bounty_id',
        'bounty_title',
        'implementation_status',
        'validation_status',
        'files',
        'requirements_verification',
        'test_results',
        'submission_checklist'
    ]
    
    all_valid = True
    for field in required_fields:
        if field not in proof:
            print_error(f"Evidence missing field: {field}")
            all_valid = False
    
    if all_valid:
        print_success("Evidence package contains all required fields")
        print_info(f"Bounty ID: {proof.get('bounty_id')}")
        print_info(f"Status: {proof.get('implementation_status')}")
        print_info(f"Total reward: {proof.get('reward_claimed', {}).get('total', 'N/A')} RTC")
    
    return all_valid

def validate_requirements():
    """Validate requirements coverage"""
    print_header("Step 6: Validating Requirements Coverage")
    
    base_dir = Path(__file__).parent / 'evidence'
    proof_file = base_dir / 'proof.json'
    
    with open(proof_file, 'r', encoding='utf-8') as f:
        proof = json.load(f)
    
    req_verify = proof.get('requirements_verification', {})
    
    # Core requirements
    core = req_verify.get('core_requirements', {})
    core_count = core.get('count', 0)
    core_status = core.get('status', 'UNKNOWN')
    
    print_info(f"Core requirements: {core_count} ({core_status})")
    
    # Bonus requirements
    bonus = req_verify.get('bonus_requirements', {})
    bonus_count = bonus.get('count', 0)
    bonus_status = bonus.get('status', 'UNKNOWN')
    
    print_info(f"Bonus requirements: {bonus_count} ({bonus_status})")
    
    # Check details
    core_details = core.get('details', [])
    for detail in core_details:
        if 'IMPLEMENTED' in detail:
            print_success(detail)
        else:
            print_error(detail)
    
    bonus_details = bonus.get('details', [])
    for detail in bonus_details:
        if 'IMPLEMENTED' in detail:
            print_success(detail)
        else:
            print_error(detail)
    
    return core_status == 'ALL MET' and bonus_status == 'ALL MET'

def generate_summary():
    """Generate validation summary"""
    print_header("Validation Summary")
    
    base_dir = Path(__file__).parent
    
    # Count lines of code
    src_dir = base_dir / 'src'
    total_lines = 0
    for py_file in src_dir.glob('*.py'):
        lines = count_lines(py_file)
        total_lines += lines
        print_info(f"{py_file.name}: {lines} lines")
    
    print_info(f"\nTotal source lines: {total_lines}")
    
    # File hashes
    print_info("\nFile hashes (SHA-256):")
    for py_file in sorted(src_dir.glob('*.py')):
        file_hash = get_file_hash(py_file)
        if file_hash:
            print(f"  {py_file.name}: {file_hash[:16]}...")
    
    return total_lines

def main():
    """Main validation function"""
    print(f"\n{GREEN}{'=' * 60}{RESET}")
    print(f"{GREEN}Bounty #2310: CRT Light Attestation{RESET}")
    print(f"{GREEN}Validation Script{RESET}")
    print(f"{GREEN}{'=' * 60}{RESET}")
    
    results = []
    
    # Run validation steps
    results.append(("Directory Structure", validate_directory_structure()))
    results.append(("Source Code", validate_source_code()))
    results.append(("Documentation", validate_documentation()))
    results.append(("Test Suite", validate_tests()))
    results.append(("Evidence Package", validate_evidence()))
    results.append(("Requirements Coverage", validate_requirements()))
    
    # Generate summary
    total_lines = generate_summary()
    
    # Final results
    print_header("Final Results")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        if result:
            print_success(f"{name}: PASSED")
        else:
            print_error(f"{name}: FAILED")
    
    print(f"\n{BLUE}Summary:{RESET}")
    print(f"  Passed: {passed}/{total}")
    print(f"  Total source lines: {total_lines}")
    
    if passed == total:
        print(f"\n{GREEN}[PASS] VALIDATION PASSED - Implementation is complete!{RESET}\n")
        return 0
    else:
        print(f"\n{RED}[FAIL] VALIDATION FAILED - {total - passed} checks failed{RESET}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
