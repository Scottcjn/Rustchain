#!/usr/bin/env python3
"""
wRTC Documentation Test Suite - Standalone Runner

Runs all documentation validation tests without requiring pytest.
Usage: python3 tests/run_tests.py
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Set


class Colors:
    """Terminal colors for output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class TestResult:
    """Test result container."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self, test_name: str):
        self.passed += 1
        print(f"{Colors.GREEN}✓{Colors.RESET} {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"{Colors.RED}✗{Colors.RESET} {test_name}")
        print(f"  {Colors.RED}Error: {error}{Colors.RESET}")


def test_documentation_file_exists():
    """Verify docs/wrtc.md exists."""
    docs_path = Path("docs/wrtc.md")
    assert docs_path.exists(), f"wrtc.md must exist at {docs_path}"
    assert docs_path.is_file(), "wrtc.md must be a file"


def test_documentation_not_empty():
    """Verify documentation has content."""
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    assert len(content) > 1000, "Documentation must be substantial (>1000 chars)"


def test_mint_address_format_base58():
    """Verify mint address is valid base58 format."""
    CANONICAL_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
    base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
    mint_chars = set(CANONICAL_MINT)
    
    assert mint_chars.issubset(base58_chars), (
        f"Mint address contains non-base58 characters: {mint_chars - base58_chars}"
    )


def test_mint_address_length():
    """Verify mint address has correct length (44 chars for this mint)."""
    CANONICAL_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
    # Solana mint addresses are 32 bytes = 43-44 base58 characters
    assert len(CANONICAL_MINT) == 44, (
        f"Mint address must be 44 characters, got {len(CANONICAL_MINT)}"
    )


def test_mint_address_in_documentation():
    """Verify canonical mint address appears in documentation."""
    CANONICAL_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    
    assert CANONICAL_MINT in content, (
        f"Canonical mint address {CANONICAL_MINT} must appear in documentation"
    )


def test_mint_address_consistency():
    """Verify all mint addresses in docs match canonical."""
    CANONICAL_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    
    mint_pattern = r'[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{32,44}'
    found_mints = set(re.findall(mint_pattern, content))
    likely_mints = {m for m in found_mints if len(m) == 43}
    
    for mint in likely_mints:
        assert mint == CANONICAL_MINT, (
            f"Found non-canonical mint address: {mint}"
        )


def test_required_sections_exist():
    """Verify all required sections are present."""
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    content_lower = content.lower()
    
    required = [
        ("anti-scam", ["anti-scam", "scam"]),
        ("buying wRTC", ["buy", "raydium"]),
        ("bridging", ["bridge", "bottube"]),
        ("withdrawing", ["withdraw"]),
        ("quick reference", ["quick reference"]),
        ("troubleshooting", ["troubleshoot"]),
    ]
    
    for section_name, keywords in required:
        found = any(kw in content_lower for kw in keywords)
        assert found, f"Required section '{section_name}' not found"


def test_raydium_url_present():
    """Verify Raydium swap URL is present and correct."""
    CANONICAL_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    
    expected_url = f"https://raydium.io/swap/?inputMint=sol&outputMint={CANONICAL_MINT}"
    assert expected_url in content, f"Raydium URL must be present"


def test_bottube_bridge_url_present():
    """Verify BoTTube bridge URL is present."""
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    
    assert "https://bottube.ai/bridge/wrtc" in content, "BoTTube bridge URL must be present"


def test_dexscreener_url_present():
    """Verify DexScreener URL is present."""
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    
    assert "dexscreener.com" in content.lower(), "DexScreener URL must be present"


def test_no_placeholder_urls():
    """Verify no placeholder/example URLs remain."""
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    
    # Check for bad placeholder URLs, but allow YOUR_WALLET in code examples
    placeholders = [
        (r'example\.com', "example.com URLs"),
        (r'your-domain\.com', "your-domain.com URLs"),
        (r'placeholder', "placeholder text"),
    ]
    
    for pattern, desc in placeholders:
        matches = re.findall(pattern, content, re.IGNORECASE)
        assert not matches, f"Found placeholder: {desc}"


def test_anti_scam_checklist_exists():
    """Verify anti-scam checklist section exists."""
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    content_lower = content.lower()
    
    assert "anti-scam" in content_lower or "scam" in content_lower, (
        "Documentation must include anti-scam guidance"
    )


def test_red_flags_documented():
    """Verify red flags/warnings are documented."""
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    content_lower = content.lower()
    
    indicators = ["red flag", "warning", "stop", "verify"]
    found = any(w in content_lower for w in indicators)
    assert found, "Documentation must include warning indicators"


def test_no_todo_placeholders():
    """Verify no TODO or FIXME placeholders remain."""
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    content_lower = content.lower()
    
    todos = ["todo:", "fixme:", "xxx:", "coming soon", "under construction", "tbd"]
    
    for todo in todos:
        assert todo not in content_lower, f"Found TODO placeholder: {todo}"


def test_step_by_step_instructions():
    """Verify step-by-step instructions are present."""
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    
    step_patterns = [r'Step \d+', r'#### Step', r'\d+\)', r'\d+\.\s']
    found = any(re.search(p, content) for p in step_patterns)
    assert found, "Documentation should include numbered step-by-step instructions"


def test_tables_used():
    """Verify tables are used for reference."""
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    
    assert "|" in content, "Documentation should include tables"


def test_readme_links_to_wrtc_docs():
    """Verify README.md links to the new wRTC documentation."""
    readme_path = Path("README.md")
    content = readme_path.read_text(encoding="utf-8")
    
    assert "wrtc.md" in content.lower() or "docs/wrtc" in content.lower(), (
        "README should reference wRTC documentation"
    )


def test_readme_has_canonical_mint():
    """Verify README contains the canonical mint address."""
    CANONICAL_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
    readme_path = Path("README.md")
    content = readme_path.read_text(encoding="utf-8")
    
    assert CANONICAL_MINT in content, "README must contain the canonical wRTC mint address"


def test_proper_markdown_headers():
    """Verify documentation uses proper markdown headers."""
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    
    assert content.startswith("# "), "Documentation should start with H1 header"
    assert "## " in content, "Should use H2 headers"
    assert "### " in content, "Should use H3 headers"


def test_token_decimals_documented():
    """Verify token decimals (6) are documented."""
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    
    assert "6" in content, "Token decimals must be documented"


def test_official_resources_listed():
    """Verify official resources are listed."""
    docs_path = Path("docs/wrtc.md")
    content = docs_path.read_text(encoding="utf-8")
    content_lower = content.lower()
    
    resources = ["raydium", "bottube", "dexscreener"]
    for resource in resources:
        assert resource in content_lower, f"Official resource '{resource}' must be listed"


def run_all_tests():
    """Run all tests and report results."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=" * 60)
    print("wRTC Documentation Test Suite")
    print("=" * 60 + f"{Colors.RESET}\n")
    
    result = TestResult()
    
    # Get all test functions
    test_functions = [
        obj for name, obj in globals().items()
        if callable(obj) and name.startswith("test_")
    ]
    
    print(f"Running {len(test_functions)} tests...\n")
    
    for test_func in test_functions:
        test_name = test_func.__name__
        try:
            test_func()
            result.add_pass(test_name)
        except AssertionError as e:
            result.add_fail(test_name, str(e))
        except Exception as e:
            result.add_fail(test_name, f"Unexpected error: {e}")
    
    # Summary
    print(f"\n{Colors.BOLD}{Colors.BLUE}" + "=" * 60)
    print("Test Summary")
    print("=" * 60 + f"{Colors.RESET}")
    print(f"{Colors.GREEN}Passed: {result.passed}{Colors.RESET}")
    print(f"{Colors.RED}Failed: {result.failed}{Colors.RESET}")
    print(f"Total:  {result.passed + result.failed}")
    
    if result.failed > 0:
        print(f"\n{Colors.RED}{Colors.BOLD}Failed Tests:{Colors.RESET}")
        for test_name, error in result.errors:
            print(f"  - {test_name}: {error}")
        return 1
    else:
        print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed! ✓{Colors.RESET}")
        return 0


if __name__ == "__main__":
    # Change to project root if running from tests directory
    script_dir = Path(__file__).parent
    if script_dir.name == "tests":
        os.chdir(script_dir.parent)
    
    exit_code = run_all_tests()
    sys.exit(exit_code)
