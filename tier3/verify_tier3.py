#!/usr/bin/env python3
"""
Quick Verification Script for Reviewers

Run this script to quickly verify the Tier 3 deliverable:
1. Multi-agent pipeline execution
2. RTC transaction flow
3. Artifact generation
4. Test suite execution

Usage:
    python verify_tier3.py
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list, description: str) -> bool:
    """Run a command and report results"""
    print(f"\n{'='*70}")
    print(f"  {description}")
    print(f"{'='*70}")
    print(f"Command: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode == 0:
        print(f"\n✓ {description} - PASSED")
        return True
    else:
        print(f"\n✗ {description} - FAILED")
        return False


def main():
    script_dir = Path(__file__).parent
    tests_passed = 0
    tests_total = 0
    
    print("\n" + "="*70)
    print("  RustChain Bounty #685 Tier 3 - Verification Suite")
    print("="*70)
    print("\nThis script verifies the autonomous multi-agent pipeline demo.")
    
    # Test 1: Run demo pipeline
    tests_total += 1
    if run_command(
        [sys.executable, str(script_dir / "demo_pipeline.py"), "--runs", "3"],
        "Demo Pipeline Execution"
    ):
        tests_passed += 1
    
    # Test 2: Run unit tests
    tests_total += 1
    if run_command(
        [sys.executable, "-m", "pytest", str(script_dir / "tests/test_pipeline.py"), "-v"],
        "Unit Test Suite"
    ):
        tests_passed += 1
    
    # Test 3: Verify artifacts exist
    tests_total += 1
    artifact_dir = script_dir / "artifacts"
    print(f"\n{'='*70}")
    print(f"  Artifact Verification")
    print(f"{'='*70}")
    
    if artifact_dir.exists():
        artifacts = list(artifact_dir.glob("*.json"))
        print(f"\nFound {len(artifacts)} artifact files:")
        for artifact in artifacts[:10]:  # Show first 10
            print(f"  - {artifact.name}")
        
        if len(artifacts) > 0:
            print(f"\n✓ Artifact Generation - PASSED")
            tests_passed += 1
        else:
            print(f"\n✗ Artifact Generation - FAILED (no artifacts found)")
    else:
        print(f"\n✗ Artifact Generation - FAILED (directory not found)")
    
    # Summary
    print(f"\n{'='*70}")
    print(f"  VERIFICATION SUMMARY")
    print(f"{'='*70}")
    print(f"\nTests Passed: {tests_passed}/{tests_total}")
    
    if tests_passed == tests_total:
        print(f"\n✓✓✓ ALL VERIFICATIONS PASSED ✓✓✓")
        print(f"\nThe Tier 3 deliverable is ready for review.")
        print(f"Artifacts are available in: {artifact_dir}")
        return 0
    else:
        print(f"\n✗✗✗ SOME VERIFICATIONS FAILED ✗✗✗")
        return 1


if __name__ == "__main__":
    sys.exit(main())
