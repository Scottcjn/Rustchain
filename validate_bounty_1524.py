#!/usr/bin/env python3
"""
Bounty #1524 Validation Runner
==============================
Executable validation script with reproducible steps for reviewers.

Usage:
    python3 validate_bounty_1524.py [--verbose] [--api-test] [--all]

This script performs comprehensive validation of the Beacon Atlas 3D Agent World
implementation for Bounty #1524.
"""
import os
import sys
import json
import time
import sqlite3
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime

# ANSI Colors
class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'

def colored(text, color):
    return f"{color}{text}{Colors.RESET}"

class ValidationRunner:
    """Runs comprehensive validation for Bounty #1524."""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'bounty': '1524',
            'branch': 'feat/issue1524-beacon-atlas-world',
            'checks': [],
            'summary': {'passed': 0, 'failed': 0, 'warnings': 0}
        }
    
    def log(self, message, level='info'):
        """Log message with appropriate formatting."""
        colors = {
            'info': Colors.BLUE,
            'success': Colors.GREEN,
            'error': Colors.RED,
            'warning': Colors.YELLOW,
            'section': Colors.CYAN + Colors.BOLD,
        }
        prefix = {
            'info': '[INFO]',
            'success': '[✓]',
            'error': '[✗]',
            'warning': '[!]',
            'section': '\n[====]',
        }
        print(f"{colors.get(level, '')}{prefix.get(level, '')} {message}{Colors.RESET}")
    
    def add_result(self, name, passed, details=None):
        """Record a validation result."""
        result = {
            'name': name,
            'passed': passed,
            'details': details,
            'timestamp': time.time()
        }
        self.results['checks'].append(result)
        
        if passed:
            self.results['summary']['passed'] += 1
            self.log(f"{name}: PASSED", 'success')
        else:
            self.results['summary']['failed'] += 1
            self.log(f"{name}: FAILED - {details or 'Unknown error'}", 'error')
    
    # =========================================================================
    # Validation Checks
    # =========================================================================
    
    def check_files_exist(self):
        """Verify all required files exist."""
        self.log("Checking required files...", 'section')
        
        required_files = [
            'site/beacon/bounties.js',
            'site/beacon/vehicles.js',
            'site/beacon/demo.html',
            'site/beacon/index.html',
            'node/beacon_api.py',
            'tests/test_beacon_atlas.py',
            'tests/test_beacon_atlas_behavior.py',
            'docs/BOUNTY_1524_IMPLEMENTATION.md',
            'docs/BOUNTY_1524_VALIDATION.md',
        ]
        
        all_exist = True
        missing = []
        
        for filepath in required_files:
            full_path = self.project_root / filepath
            if not full_path.exists():
                all_exist = False
                missing.append(filepath)
                if self.verbose:
                    self.log(f"  Missing: {filepath}", 'error')
            elif self.verbose:
                self.log(f"  Found: {filepath} ({full_path.stat().st_size} bytes)", 'success')
        
        self.add_result('files_exist', all_exist, 
                       f"Missing: {missing}" if missing else "All files present")
        return all_exist
    
    def check_file_sizes(self):
        """Verify files have substantial content."""
        self.log("Checking file sizes...", 'section')
        
        min_sizes = {
            'site/beacon/bounties.js': 5000,
            'site/beacon/vehicles.js': 3000,
            'site/beacon/demo.html': 5000,
            'node/beacon_api.py': 10000,
            'tests/test_beacon_atlas.py': 5000,
            'docs/BOUNTY_1524_IMPLEMENTATION.md': 10000,
        }
        
        all_ok = True
        undersized = []
        
        for filepath, min_size in min_sizes.items():
            full_path = self.project_root / filepath
            if full_path.exists():
                actual_size = full_path.stat().st_size
                if actual_size < min_size:
                    all_ok = False
                    undersized.append(f"{filepath}: {actual_size} < {min_size}")
                elif self.verbose:
                    self.log(f"  {filepath}: {actual_size} bytes >= {min_size}", 'success')
        
        self.add_result('file_sizes', all_ok,
                       f"Undersized: {undersized}" if undersized else "All files adequate size")
        return all_ok
    
    def check_python_syntax(self):
        """Verify Python files have valid syntax."""
        self.log("Checking Python syntax...", 'section')
        
        python_files = [
            'node/beacon_api.py',
            'tests/test_beacon_atlas.py',
            'tests/test_beacon_atlas_behavior.py',
        ]
        
        all_valid = True
        
        for filepath in python_files:
            full_path = self.project_root / filepath
            try:
                with open(full_path, 'r') as f:
                    compile(f.read(), str(full_path), 'exec')
                if self.verbose:
                    self.log(f"  {filepath}: Valid syntax", 'success')
            except SyntaxError as e:
                all_valid = False
                self.log(f"  {filepath}: Syntax error - {e}", 'error')
        
        self.add_result('python_syntax', all_valid,
                       "All Python files valid" if all_valid else "Syntax errors found")
        return all_valid
    
    def check_javascript_syntax(self):
        """Verify JavaScript files have ES6 module syntax."""
        self.log("Checking JavaScript syntax...", 'section')
        
        js_files = [
            'site/beacon/bounties.js',
            'site/beacon/vehicles.js',
            'site/beacon/scene.js',
        ]
        
        all_valid = True
        
        for filepath in js_files:
            full_path = self.project_root / filepath
            if full_path.exists():
                content = full_path.read_text()
                has_import = 'import' in content
                has_export = 'export' in content
                
                if has_import and has_export:
                    if self.verbose:
                        self.log(f"  {filepath}: ES6 module syntax OK", 'success')
                else:
                    all_valid = False
                    self.log(f"  {filepath}: Missing ES6 imports/exports", 'warning')
        
        self.add_result('javascript_syntax', all_valid,
                       "ES6 modules valid" if all_valid else "Syntax issues found")
        return all_valid
    
    def check_api_endpoints(self):
        """Verify API endpoints are defined."""
        self.log("Checking API endpoints...", 'section')
        
        api_file = self.project_root / 'node/beacon_api.py'
        content = api_file.read_text()
        
        required_endpoints = [
            ('/api/contracts', 'GET'),
            ('/api/contracts', 'POST'),
            ('/api/bounties', 'GET'),
            ('/api/bounties/sync', 'POST'),
            ('/api/reputation', 'GET'),
            ('/api/health', 'GET'),
        ]
        
        all_found = True
        
        for endpoint, method in required_endpoints:
            # Check for route definition
            if f"route('{endpoint}'" in content or f'route("{endpoint}"' in content:
                if self.verbose:
                    self.log(f"  {method} {endpoint}: Defined", 'success')
            else:
                all_found = False
                self.log(f"  {method} {endpoint}: NOT FOUND", 'error')
        
        self.add_result('api_endpoints', all_found,
                       "All endpoints defined" if all_found else "Missing endpoints")
        return all_found
    
    def check_database_schema(self):
        """Verify database schema is defined."""
        self.log("Checking database schema...", 'section')
        
        api_file = self.project_root / 'node/beacon_api.py'
        content = api_file.read_text()
        
        required_tables = [
            'beacon_contracts',
            'beacon_bounties',
            'beacon_reputation',
            'beacon_chat',
        ]
        
        all_found = True
        
        for table in required_tables:
            if f"CREATE TABLE" in content and table in content:
                if self.verbose:
                    self.log(f"  Table {table}: Defined", 'success')
            else:
                all_found = False
                self.log(f"  Table {table}: NOT FOUND", 'error')
        
        self.add_result('database_schema', all_found,
                       "All tables defined" if all_found else "Missing tables")
        return all_found
    
    def check_test_coverage(self):
        """Verify test suite has adequate coverage."""
        self.log("Checking test coverage...", 'section')
        
        test_file = self.project_root / 'tests/test_beacon_atlas.py'
        content = test_file.read_text()
        
        # Count test methods
        test_count = content.count('def test_')
        class_count = content.count('class Test')
        
        adequate = test_count >= 10 and class_count >= 3
        
        self.log(f"  Found {test_count} tests in {class_count} classes", 
                'success' if adequate else 'warning')
        
        self.add_result('test_coverage', adequate,
                       f"{test_count} tests, {class_count} classes")
        return adequate
    
    def check_feature_implementation(self):
        """Verify key features are implemented."""
        self.log("Checking feature implementation...", 'section')
        
        bounties_js = (self.project_root / 'site/beacon/bounties.js').read_text()
        vehicles_js = (self.project_root / 'site/beacon/vehicles.js').read_text()
        
        features = {
            'Difficulty colors': 'DIFFICULTY_COLORS' in bounties_js,
            '3D positioning': 'getBountyPosition' in bounties_js,
            'Animation': 'onAnimate' in bounties_js and 'Math.sin' in bounties_js,
            'Vehicle types': any(v in vehicles_js for v in ['car', 'plane', 'drone']),
            'Three.js integration': 'THREE' in bounties_js,
        }
        
        all_implemented = all(features.values())
        
        for feature, implemented in features.items():
            status = '✓' if implemented else '✗'
            if self.verbose:
                self.log(f"  {status} {feature}", 'success' if implemented else 'error')
        
        self.add_result('feature_implementation', all_implemented,
                       "All features present" if all_implemented else "Missing features")
        return all_implemented
    
    def run_unit_tests(self):
        """Run the unit test suite."""
        self.log("Running unit tests...", 'section')
        
        test_file = self.project_root / 'tests/test_beacon_atlas.py'
        
        try:
            result = subprocess.run(
                [sys.executable, str(test_file), '-v'],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            passed = result.returncode == 0
            
            # Parse test output
            if 'OK' in result.stdout:
                self.log(f"  All tests passed", 'success')
            else:
                self.log(f"  Some tests failed", 'error')
                if self.verbose:
                    print(result.stdout)
                    print(result.stderr)
            
            self.add_result('unit_tests', passed,
                           "Tests passed" if passed else "Tests failed")
            return passed
            
        except subprocess.TimeoutExpired:
            self.add_result('unit_tests', False, "Test timeout")
            return False
        except Exception as e:
            self.add_result('unit_tests', False, str(e))
            return False
    
    def run_behavioral_tests(self):
        """Run behavioral integration tests."""
        self.log("Running behavioral tests...", 'section')
        
        test_file = self.project_root / 'tests/test_beacon_atlas_behavior.py'
        
        try:
            result = subprocess.run(
                [sys.executable, str(test_file), '-v'],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            passed = result.returncode == 0
            
            if 'OK' in result.stdout:
                self.log(f"  All behavioral tests passed", 'success')
            else:
                self.log(f"  Some behavioral tests failed", 'warning')
                if self.verbose:
                    print(result.stdout)
                    print(result.stderr)
            
            self.add_result('behavioral_tests', passed,
                           "Tests passed" if passed else "Tests failed")
            return passed
            
        except subprocess.TimeoutExpired:
            self.add_result('behavioral_tests', False, "Test timeout")
            return False
        except Exception as e:
            self.add_result('behavioral_tests', False, str(e))
            return False
    
    def check_documentation(self):
        """Verify documentation is complete."""
        self.log("Checking documentation...", 'section')
        
        impl_doc = self.project_root / 'docs/BOUNTY_1524_IMPLEMENTATION.md'
        val_doc = self.project_root / 'docs/BOUNTY_1524_VALIDATION.md'
        
        checks = {
            'Implementation doc exists': impl_doc.exists(),
            'Validation doc exists': val_doc.exists(),
            'Bounty reference': 'Bounty #1524' in impl_doc.read_text() if impl_doc.exists() else False,
            'API documentation': 'API' in impl_doc.read_text() if impl_doc.exists() else False,
            'Test results documented': 'test' in val_doc.read_text().lower() if val_doc.exists() else False,
        }
        
        all_ok = all(checks.values())
        
        for check, passed in checks.items():
            if self.verbose:
                self.log(f"  {'✓' if passed else '✗'} {check}", 
                        'success' if passed else 'error')
        
        self.add_result('documentation', all_ok,
                       "Documentation complete" if all_ok else "Documentation incomplete")
        return all_ok
    
    # =========================================================================
    # Report Generation
    # =========================================================================
    
    def generate_report(self):
        """Generate validation report."""
        self.log("\nGenerating validation report...", 'section')
        
        report_path = self.project_root / 'BOUNTY_1524_VALIDATION_RESULT.json'
        
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        self.log(f"Report saved to: {report_path}", 'success')
        
        # Print summary
        summary = self.results['summary']
        total = summary['passed'] + summary['failed']
        
        print("\n" + "=" * 60)
        print(colored("VALIDATION SUMMARY", Colors.CYAN + Colors.BOLD))
        print("=" * 60)
        print(f"Total Checks:  {total}")
        print(colored(f"Passed:        {summary['passed']}", Colors.GREEN))
        print(colored(f"Failed:        {summary['failed']}", Colors.RED))
        print("=" * 60)
        
        if summary['failed'] == 0:
            print(colored("\n✓ ALL VALIDATIONS PASSED", Colors.GREEN + Colors.BOLD))
            print(colored("Bounty #1524 is ready for review", Colors.GREEN))
        else:
            print(colored("\n✗ SOME VALIDATIONS FAILED", Colors.RED + Colors.BOLD))
            print(colored("Please review failures above", Colors.YELLOW))
        
        print("=" * 60)
        
        return summary['failed'] == 0
    
    # =========================================================================
    # Main Runner
    # =========================================================================
    
    def run_all(self, run_tests=True):
        """Run all validation checks."""
        print(colored("\n" + "=" * 60, Colors.CYAN + Colors.BOLD))
        print(colored("  Bounty #1524 Validation Runner", Colors.CYAN + Colors.BOLD))
        print(colored("  Beacon Atlas 3D Agent World", Colors.CYAN + Colors.BOLD))
        print(colored("=" * 60 + "\n", Colors.CYAN + Colors.BOLD))
        
        # Static checks
        self.check_files_exist()
        self.check_file_sizes()
        self.check_python_syntax()
        self.check_javascript_syntax()
        self.check_api_endpoints()
        self.check_database_schema()
        self.check_test_coverage()
        self.check_feature_implementation()
        self.check_documentation()
        
        # Dynamic tests
        if run_tests:
            self.run_unit_tests()
            self.run_behavioral_tests()
        
        # Generate report
        return self.generate_report()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Bounty #1524 Validation Runner'
    )
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed output')
    parser.add_argument('--no-tests', action='store_true',
                       help='Skip running actual tests')
    parser.add_argument('--report-only', action='store_true',
                       help='Only generate report from previous run')
    
    args = parser.parse_args()
    
    runner = ValidationRunner(verbose=args.verbose)
    success = runner.run_all(run_tests=not args.no_tests)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
