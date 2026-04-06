#!/usr/bin/env python3
"""
Tests for PPA Compliance Checker
"""

import subprocess
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ppa_compliance_check import (
    run_compliance_check,
    evaluate_sub_check,
    ComplianceLevel,
    COMPLIANCE_CHECKS
)


def test_compliance_check_runs():
    """Test that compliance check runs without errors."""
    report = run_compliance_check(verbose=False)
    
    assert report.total_checks == 16  # RIP-0308 Appendix A has 16 checks
    assert report.overall_status in ["PPA-COMPLIANT", "PPA-PARTIAL", "NON-COMPLIANT"]
    assert report.exit_code in [0, 1, 2]
    assert len(report.checks) == 16
    print("✅ Compliance check runs successfully")


def test_exit_codes():
    """Test that exit codes match ComplianceLevel enum."""
    assert ComplianceLevel.COMPLIANT.value == 0
    assert ComplianceLevel.PARTIAL.value == 1
    assert ComplianceLevel.NON_COMPLIANT.value == 2
    print("✅ Exit codes are correct")


def test_compliance_checks_defined():
    """Test that all 16 compliance checks are defined."""
    assert len(COMPLIANCE_CHECKS) == 16
    
    # Check for required groups
    critical_checks = [k for k, v in COMPLIANCE_CHECKS.items() if v['severity'] == 'critical']
    important_checks = [k for k, v in COMPLIANCE_CHECKS.items() if v['severity'] == 'important']
    
    assert len(critical_checks) >= 4  # At least 4 critical checks
    assert len(important_checks) >= 4  # At least 4 important checks
    print(f"✅ All 16 checks defined ({len(critical_checks)} critical, {len(important_checks)} important)")


def test_cli_help():
    """Test CLI help output."""
    result = subprocess.run(
        [sys.executable, 'ppa_compliance_check.py', '--help'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "RIP-0308 Appendix A" in result.stdout
    assert "--json" in result.stdout
    assert "--verbose" in result.stdout
    print("✅ CLI help works")


def test_cli_json_output():
    """Test JSON output format."""
    result = subprocess.run(
        [sys.executable, 'ppa_compliance_check.py', '--json'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    import json
    output = json.loads(result.stdout)
    
    assert "status" in output
    assert "exit_code" in output
    assert "checks" in output
    assert output["checks"]["total"] == 16
    print("✅ JSON output format is valid")


def test_cli_quiet_output():
    """Test quiet mode output."""
    result = subprocess.run(
        [sys.executable, 'ppa_compliance_check.py', '--quiet'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    assert result.stdout.strip() in ["PPA-COMPLIANT", "PPA-PARTIAL", "NON-COMPLIANT"]
    print("✅ Quiet mode works")


def test_evaluate_sub_check():
    """Test individual sub-check evaluation."""
    config = {
        'description': 'Test check',
        'severity': 'important',
        'check_fn': 'clock_drift'
    }
    
    fingerprint_results = {}
    result = evaluate_sub_check('test_check', config, fingerprint_results)
    
    assert result.name == 'test_check'
    assert result.severity == 'important'
    assert isinstance(result.passed, bool)
    print("✅ Sub-check evaluation works")


if __name__ == '__main__':
    print("Running PPA Compliance Checker Tests...\n")
    
    test_compliance_checks_defined()
    test_exit_codes()
    test_evaluate_sub_check()
    test_compliance_check_runs()
    test_cli_help()
    test_cli_json_output()
    test_cli_quiet_output()
    
    print("\n🎉 All tests passed!")
    print(f"   Total checks: 16 (per RIP-0308 Appendix A)")
    print(f"   Exit codes: 0=compliant, 1=partial, 2=non-compliant")
