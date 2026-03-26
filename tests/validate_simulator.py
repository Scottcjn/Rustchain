#!/usr/bin/env python3
"""
RustChain Interactive Mining Simulator - Validation Script
Issue #2301 - Validation Tests

This script validates the implementation of the Interactive RustChain Mining Simulator
against the bounty requirements.
"""

import os
import re
import sys
from pathlib import Path

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def log_pass(message):
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def log_fail(message):
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def log_info(message):
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def log_warn(message):
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def log_section(message):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{message}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

class SimulatorValidator:
    def __init__(self, simulator_path):
        self.simulator_path = Path(simulator_path)
        self.html_file = self.simulator_path / 'index.html'
        self.readme_file = self.simulator_path / 'README.md'
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        
    def validate_all(self):
        """Run all validation checks."""
        log_section("RustChain Mining Simulator - Validation Suite")
        log_info(f"Simulator Path: {self.simulator_path.absolute()}")
        
        self.check_file_exists()
        self.check_html_structure()
        self.check_hardware_options()
        self.check_simulation_stages()
        self.check_reward_calculations()
        self.check_bonus_features()
        self.check_responsive_design()
        self.check_documentation()
        
        self.print_summary()
        return self.failed == 0
    
    def check_file_exists(self):
        """Check if required files exist."""
        log_section("1. File Existence Checks")
        
        if self.html_file.exists():
            log_pass(f"index.html exists ({self.html_file.stat().st_size:,} bytes)")
            self.passed += 1
        else:
            log_fail("index.html not found")
            self.failed += 1
            
        if self.readme_file.exists():
            log_pass("README.md exists")
            self.passed += 1
        else:
            log_warn("README.md not found (recommended)")
            self.warnings += 1
    
    def check_html_structure(self):
        """Validate HTML structure and required elements."""
        log_section("2. HTML Structure Validation")
        
        try:
            content = self.html_file.read_text(encoding='utf-8')
        except Exception as e:
            log_fail(f"Cannot read index.html: {e}")
            self.failed += 1
            return
        
        checks = [
            ('<!DOCTYPE html>', 'HTML5 doctype'),
            ('<html', 'HTML root element'),
            ('<head>', 'Head section'),
            ('<body>', 'Body section'),
            ('<title>', 'Page title'),
            ('<style>', 'CSS styles'),
            ('<script>', 'JavaScript code'),
            ('hardware-section', 'Hardware selection section'),
            ('simulation-container', 'Simulation container'),
            ('stage-panel', 'Stage panels'),
            ('fingerprint-visualizer', 'Fingerprint visualizer'),
            ('attestation-payload', 'Attestation payload display'),
            ('epoch-visualizer', 'Epoch visualization'),
            ('rewards-grid', 'Rewards display'),
            ('calculator-section', 'Earnings calculator'),
            ('download-section', 'Download links'),
        ]
        
        for pattern, description in checks:
            if pattern in content:
                log_pass(f"{description} present")
                self.passed += 1
            else:
                log_fail(f"{description} missing")
                self.failed += 1
    
    def check_hardware_options(self):
        """Validate hardware options and multipliers."""
        log_section("3. Hardware Options Validation")
        
        content = self.html_file.read_text(encoding='utf-8')
        
        # Check for required hardware types
        hardware_checks = [
            ('g4', 'PowerBook G4', '2.5'),
            ('g5', 'Power Mac G5', '2.0'),
            ('x86', 'Modern x86', '1.0'),
            ('vm', 'Virtual Machine', '0.000000001'),
        ]
        
        for hw_type, hw_name, multiplier in hardware_checks:
            if f'data-hardware="{hw_type}"' in content and f'data-multiplier="{multiplier}"' in content:
                log_pass(f"{hw_name} ({multiplier}×) configured correctly")
                self.passed += 1
            else:
                log_fail(f"{hw_name} ({multiplier}×) not found or incorrect")
                self.failed += 1
        
        # Check hardware cards exist
        if content.count('hardware-card') >= 4:
            log_pass("All 4 hardware cards present")
            self.passed += 1
        else:
            log_fail("Missing hardware cards")
            self.failed += 1
    
    def check_simulation_stages(self):
        """Validate all 4 simulation stages."""
        log_section("4. Simulation Stages Validation")
        
        content = self.html_file.read_text(encoding='utf-8')
        
        stages = [
            ('Hardware Detection', 'Stage 1'),
            ('Attestation', 'Stage 2'),
            ('Epoch Participation', 'Stage 3'),
            ('Reward Calculation', 'Stage 4'),
        ]
        
        for stage_name, stage_label in stages:
            if stage_name in content:
                log_pass(f"{stage_label}: {stage_name} implemented")
                self.passed += 1
            else:
                log_fail(f"{stage_label}: {stage_name} missing")
                self.failed += 1
        
        # Check stage indicators
        stage_indicators = content.count('stage-indicator')
        if stage_indicators >= 4:
            log_pass(f"Stage indicators present ({stage_indicators})")
            self.passed += 1
        else:
            log_fail("Stage indicators missing or incomplete")
            self.failed += 1
        
        # Check stage panels
        stage_panels = content.count('stage-panel')
        if stage_panels >= 4:
            log_pass(f"Stage panels present ({stage_panels})")
            self.passed += 1
        else:
            log_fail("Stage panels missing or incomplete")
            self.failed += 1
    
    def check_reward_calculations(self):
        """Validate reward calculation logic."""
        log_section("5. Reward Calculation Validation")
        
        content = self.html_file.read_text(encoding='utf-8')
        
        # Check for calculation constants
        calc_checks = [
            ('RTC_PER_EPOCH', 'RTC per epoch constant'),
            ('EPOCHS_PER_HOUR', 'Epochs per hour constant'),
            ('EPOCHS_PER_DAY', 'Epochs per day constant'),
            ('EPOCHS_PER_WEEK', 'Epochs per week constant'),
            ('EPOCHS_PER_MONTH', 'Epochs per month constant'),
            ('USD_RATE', 'USD conversion rate'),
        ]
        
        for const, description in calc_checks:
            if const in content:
                log_pass(f"{description} defined")
                self.passed += 1
            else:
                log_fail(f"{description} missing")
                self.failed += 1
        
        # Check for calculation function
        if 'calculateRewards' in content or 'calculate()' in content:
            log_pass("Reward calculation function present")
            self.passed += 1
        else:
            log_fail("Reward calculation function missing")
            self.failed += 1
        
        # Check for reward display elements
        reward_periods = ['Epoch', 'Hour', 'Day', 'Week', 'Month', 'Year']
        for period in reward_periods:
            if f'reward{period}' in content.lower():
                log_pass(f"{period} reward display present")
                self.passed += 1
            else:
                log_warn(f"{period} reward display missing")
                self.warnings += 1
    
    def check_bonus_features(self):
        """Validate bonus features (animated fingerprint, earnings calculator)."""
        log_section("6. Bonus Features Validation")
        
        content = self.html_file.read_text(encoding='utf-8')
        
        # Animated fingerprint check
        fingerprint_checks = [
            ('fingerprint-visualizer', 'Fingerprint visualizer container'),
            ('fingerprint-item', 'Individual fingerprint items'),
            ('scanning', 'Scanning animation class'),
            ('verified', 'Verified state class'),
            ('runHardwareDetection', 'Detection animation function'),
        ]
        
        log_info("Bonus Feature 1: Animated Fingerprint Check")
        for check, description in fingerprint_checks:
            if check in content:
                log_pass(f"{description} present")
                self.passed += 1
            else:
                log_fail(f"{description} missing")
                self.failed += 1
        
        # Earnings calculator
        log_info("Bonus Feature 2: What Would You Earn? Calculator")
        calculator_checks = [
            ('calculator-section', 'Calculator section'),
            ('comparison-table', 'Comparison table'),
            ('comparisonBody', 'Comparison table body'),
            ('updateComparisonTable', 'Comparison update function'),
            ('What Would You Earn', 'Calculator title'),
        ]
        
        for check, description in calculator_checks:
            if check in content:
                log_pass(f"{description} present")
                self.passed += 1
            else:
                log_fail(f"{description} missing")
                self.failed += 1
    
    def check_responsive_design(self):
        """Validate responsive design implementation."""
        log_section("7. Responsive Design Validation")
        
        content = self.html_file.read_text(encoding='utf-8')
        
        # Check for responsive meta tag
        if 'viewport' in content and 'width=device-width' in content:
            log_pass("Viewport meta tag present")
            self.passed += 1
        else:
            log_fail("Viewport meta tag missing")
            self.failed += 1
        
        # Check for media queries
        if '@media' in content:
            log_pass("CSS media queries present")
            self.passed += 1
        else:
            log_warn("No CSS media queries found (may not be responsive)")
            self.warnings += 1
        
        # Check for responsive units
        if 'max-width' in content or 'min-width' in content:
            log_pass("Responsive width constraints present")
            self.passed += 1
        else:
            log_warn("No responsive width constraints found")
            self.warnings += 1
        
        # Check for flexbox/grid layouts
        if 'display: grid' in content or 'display: flex' in content:
            log_pass("Modern layout system (Grid/Flexbox) used")
            self.passed += 1
        else:
            log_warn("May not use modern layout systems")
            self.warnings += 1
    
    def check_documentation(self):
        """Validate documentation completeness."""
        log_section("8. Documentation Validation")
        
        if not self.readme_file.exists():
            log_warn("README.md not found")
            self.warnings += 1
            return
        
        content = self.readme_file.read_text(encoding='utf-8')
        
        doc_sections = [
            ('Issue #2301', 'Issue reference'),
            ('Features', 'Features section'),
            ('Hardware', 'Hardware options documented'),
            ('Usage', 'Usage instructions'),
            ('Testing', 'Testing instructions'),
            ('Deployment', 'Deployment guide'),
        ]
        
        for section, description in doc_sections:
            if section in content:
                log_pass(f"{description} present")
                self.passed += 1
            else:
                log_warn(f"{description} missing")
                self.warnings += 1
    
    def print_summary(self):
        """Print validation summary."""
        log_section("Validation Summary")
        
        total = self.passed + self.failed
        success_rate = (self.passed / total * 100) if total > 0 else 0
        
        print(f"{Colors.BOLD}Total Checks:{Colors.END}     {total}")
        print(f"{Colors.GREEN}Passed:{Colors.END}          {self.passed}")
        print(f"{Colors.RED}Failed:{Colors.END}          {self.failed}")
        print(f"{Colors.YELLOW}Warnings:{Colors.END}        {self.warnings}")
        print(f"{Colors.BOLD}Success Rate:{Colors.END}    {success_rate:.1f}%\n")
        
        if self.failed == 0:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 VALIDATION PASSED!{Colors.END}")
            print(f"{Colors.GREEN}All required features implemented correctly.{Colors.END}")
        else:
            print(f"{Colors.RED}{Colors.BOLD}❌ VALIDATION FAILED!{Colors.END}")
            print(f"{Colors.RED}{self.failed} critical issue(s) must be fixed.{Colors.END}")
        
        if self.warnings > 0:
            print(f"\n{Colors.YELLOW}⚠️  {self.warnings} non-critical warning(s) noted.{Colors.END}")
        
        print()


def main():
    """Main entry point."""
    # Determine simulator path
    if len(sys.argv) > 1:
        simulator_path = Path(sys.argv[1])
    else:
        # Default to simulator directory in current working directory
        simulator_path = Path(__file__).parent.parent / 'simulator'
    
    if not simulator_path.exists():
        print(f"{Colors.RED}Error: Simulator path not found: {simulator_path}{Colors.END}")
        sys.exit(1)
    
    validator = SimulatorValidator(simulator_path)
    success = validator.validate_all()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
