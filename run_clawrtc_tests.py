# SPDX-License-Identifier: MIT
"""
Test runner for clawrtc integration test suite.
Executes tests, generates coverage reports, validates >80% coverage requirement.
"""
import os
import sys
import subprocess
import json
import sqlite3
from pathlib import Path


DB_PATH = "test_results.db"


def setup_test_db():
    """Initialize test results database."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_tests INTEGER,
                passed INTEGER,
                failed INTEGER,
                coverage_pct REAL,
                status TEXT,
                details TEXT
            )
        ''')
        conn.commit()


def run_command(cmd, cwd=None):
    """Execute shell command and return result."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=cwd
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def install_clawrtc():
    """Install clawrtc package if not present."""
    print("Checking clawrtc installation...")
    code, stdout, stderr = run_command("pip show clawrtc")

    if code != 0:
        print("Installing clawrtc...")
        code, stdout, stderr = run_command("pip install clawrtc")
        if code != 0:
            print(f"Failed to install clawrtc: {stderr}")
            return False

    print("clawrtc package ready")
    return True


def run_pytest_with_coverage():
    """Execute pytest with coverage reporting."""
    print("Running clawrtc integration tests...")

    test_dir = Path("tests/clawrtc")
    if not test_dir.exists():
        print(f"Test directory {test_dir} not found")
        return None

    cmd = (
        "python -m pytest tests/clawrtc/ "
        "--cov=clawrtc "
        "--cov-report=json:coverage.json "
        "--cov-report=html:htmlcov "
        "--cov-report=term "
        "-v --tb=short"
    )

    code, stdout, stderr = run_command(cmd)

    result = {
        "exit_code": code,
        "stdout": stdout,
        "stderr": stderr,
        "coverage_data": None
    }

    # Parse coverage results
    if Path("coverage.json").exists():
        try:
            with open("coverage.json", "r") as f:
                coverage_data = json.load(f)
                result["coverage_data"] = coverage_data
        except Exception as e:
            print(f"Failed to parse coverage.json: {e}")

    return result


def parse_test_results(test_output):
    """Extract test counts from pytest output."""
    total_tests = 0
    passed = 0
    failed = 0

    lines = test_output.split('\n')
    for line in lines:
        if "passed" in line and "failed" in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "passed":
                    try:
                        passed = int(parts[i-1])
                    except (IndexError, ValueError):
                        pass
                elif part == "failed":
                    try:
                        failed = int(parts[i-1])
                    except (IndexError, ValueError):
                        pass
        elif " passed in " in line:
            parts = line.split()
            for part in parts:
                try:
                    if part.isdigit():
                        passed = int(part)
                        break
                except ValueError:
                    pass

    total_tests = passed + failed
    return total_tests, passed, failed


def validate_coverage(coverage_data, threshold=80.0):
    """Check if coverage meets minimum requirement."""
    if not coverage_data:
        return False, 0.0

    # Get overall coverage percentage
    summary = coverage_data.get("totals", {})
    coverage_pct = summary.get("percent_covered", 0.0)

    return coverage_pct >= threshold, coverage_pct


def store_results(total_tests, passed, failed, coverage_pct, status, details):
    """Store test results in database."""
    from datetime import datetime

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO test_runs
            (timestamp, total_tests, passed, failed, coverage_pct, status, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            total_tests,
            passed,
            failed,
            coverage_pct,
            status,
            details
        ))
        conn.commit()


def generate_report(result_data):
    """Generate human-readable test report."""
    coverage_pct = result_data.get("coverage_pct", 0.0)
    total_tests = result_data.get("total_tests", 0)
    passed = result_data.get("passed", 0)
    failed = result_data.get("failed", 0)

    print("\n" + "="*60)
    print("CLAWRTC INTEGRATION TEST RESULTS")
    print("="*60)
    print(f"Total Tests:    {total_tests}")
    print(f"Passed:         {passed}")
    print(f"Failed:         {failed}")
    print(f"Coverage:       {coverage_pct:.1f}%")
    print(f"Threshold:      80.0%")

    if coverage_pct >= 80.0:
        print("✅ Coverage requirement MET")
        status = "PASSED"
    else:
        print("❌ Coverage requirement NOT MET")
        status = "FAILED"

    if failed > 0:
        print("❌ Some tests FAILED")
        status = "FAILED"
    elif passed > 0:
        print("✅ All tests PASSED")

    print("="*60)
    return status


def main():
    """Main test runner execution."""
    print("Starting clawrtc integration test suite...")

    setup_test_db()

    if not install_clawrtc():
        print("Failed to install clawrtc package")
        sys.exit(1)

    # Run tests with coverage
    result = run_pytest_with_coverage()
    if result is None:
        print("Failed to run tests")
        sys.exit(1)

    # Parse results
    total_tests, passed, failed = parse_test_results(result["stdout"])

    coverage_meets_req = False
    coverage_pct = 0.0

    if result["coverage_data"]:
        coverage_meets_req, coverage_pct = validate_coverage(result["coverage_data"])

    # Generate report
    result_summary = {
        "total_tests": total_tests,
        "passed": passed,
        "failed": failed,
        "coverage_pct": coverage_pct
    }

    final_status = generate_report(result_summary)

    # Store results
    details = {
        "stdout_snippet": result["stdout"][-500:] if result["stdout"] else "",
        "stderr_snippet": result["stderr"][-500:] if result["stderr"] else "",
        "exit_code": result["exit_code"]
    }

    store_results(
        total_tests, passed, failed, coverage_pct,
        final_status, json.dumps(details)
    )

    # Exit with appropriate code
    if final_status == "PASSED" and coverage_meets_req and failed == 0:
        print("\n✅ All requirements met!")
        sys.exit(0)
    else:
        print(f"\n❌ Requirements not met (status: {final_status})")
        sys.exit(1)


if __name__ == "__main__":
    main()
