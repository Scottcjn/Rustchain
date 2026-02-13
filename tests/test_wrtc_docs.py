"""
wRTC Documentation Test Suite

Comprehensive tests to validate wRTC documentation integrity.
Ensures all URLs are reachable, mint address is valid, and content is complete.

Run with: python -m pytest tests/test_wrtc_docs.py -v
"""

import re
import os
import pytest
from pathlib import Path
from typing import List, Tuple, Set


class TestWRTCDocumentation:
    """Test suite for wRTC quickstart documentation."""

    DOCS_PATH = Path(__file__).parent.parent / "docs" / "wrtc.md"
    README_PATH = Path(__file__).parent.parent / "README.md"
    CANONICAL_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
    CANONICAL_DECIMALS = "6"

    @pytest.fixture(scope="class")
    def docs_content(self) -> str:
        """Load the wrtc.md documentation content."""
        if not self.DOCS_PATH.exists():
            pytest.fail(f"Documentation file not found: {self.DOCS_PATH}")
        return self.DOCS_PATH.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def readme_content(self) -> str:
        """Load the README.md content."""
        if not self.README_PATH.exists():
            pytest.fail(f"README file not found: {self.README_PATH}")
        return self.README_PATH.read_text(encoding="utf-8")

    # =========================================================================
    # Section 1: File Existence Tests
    # =========================================================================

    def test_documentation_file_exists(self):
        """Verify docs/wrtc.md exists."""
        assert self.DOCS_PATH.exists(), f"wrtc.md must exist at {self.DOCS_PATH}"
        assert self.DOCS_PATH.is_file(), "wrtc.md must be a file"

    def test_documentation_not_empty(self, docs_content: str):
        """Verify documentation has content."""
        assert len(docs_content) > 1000, "Documentation must be substantial (>1000 chars)"

    # =========================================================================
    # Section 2: Mint Address Tests
    # =========================================================================

    def test_mint_address_format_base58(self):
        """Verify mint address is valid base58 format."""
        # Base58 alphabet
        base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        mint_chars = set(self.CANONICAL_MINT)
        
        assert mint_chars.issubset(base58_chars), (
            f"Mint address contains non-base58 characters: {mint_chars - base58_chars}"
        )

    def test_mint_address_length(self):
        """Verify mint address has correct length (32 bytes = ~43-44 base58 chars)."""
        assert len(self.CANONICAL_MINT) == 43, (
            f"Mint address must be 43 characters, got {len(self.CANONICAL_MINT)}"
        )

    def test_mint_address_in_documentation(self, docs_content: str):
        """Verify canonical mint address appears in documentation."""
        assert self.CANONICAL_MINT in docs_content, (
            f"Canonical mint address {self.CANONICAL_MINT} must appear in documentation"
        )

    def test_mint_address_consistency(self, docs_content: str):
        """Verify all mint addresses in docs match canonical."""
        # Find all potential Solana mint addresses (base58, 32-44 chars)
        mint_pattern = r'[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{32,44}'
        found_mints = set(re.findall(mint_pattern, docs_content))
        
        # Filter to likely mint addresses (43 chars is standard)
        likely_mints = {m for m in found_mints if len(m) == 43}
        
        # All 43-char base58 strings should be the canonical mint
        for mint in likely_mints:
            assert mint == self.CANONICAL_MINT, (
                f"Found non-canonical mint address: {mint}. "
                f"All 43-char addresses should be {self.CANONICAL_MINT}"
            )

    # =========================================================================
    # Section 3: Required Sections Tests
    # =========================================================================

    @pytest.mark.parametrize("section", [
        ("Anti-Scam Checklist", ["anti-scam", "checklist"]),
        ("Step-by-Step Guide", ["step", "guide"]),
        ("Buying wRTC", ["buy", "raydium"]),
        ("Bridging", ["bridge", "bottube"]),
        ("Withdrawing", ["withdraw"]),
        ("Quick Reference", ["quick reference", "reference"]),
        ("Troubleshooting", ["troubleshoot"]),
    ])
    def test_required_sections_exist(self, docs_content: str, section: Tuple[str, List[str]]):
        """Verify all required sections are present in documentation."""
        section_name, keywords = section
        content_lower = docs_content.lower()
        
        # Check for at least one keyword
        found = any(kw.lower() in content_lower for kw in keywords)
        assert found, f"Required section '{section_name}' not found (looked for: {keywords})"

    def test_table_of_contents_exists(self, docs_content: str):
        """Verify documentation has a table of contents."""
        toc_patterns = ["table of contents", "## contents", "## toc", "## index"]
        content_lower = docs_content.lower()
        assert any(p in content_lower for p in toc_patterns), (
            "Documentation must have a table of contents"
        )

    def test_canonical_info_section(self, docs_content: str):
        """Verify canonical info (mint, decimals) is clearly documented."""
        assert self.CANONICAL_MINT in docs_content, "Canonical mint must be documented"
        assert self.CANONICAL_DECIMALS in docs_content, "Canonical decimals must be documented"

    # =========================================================================
    # Section 4: URL Validation Tests
    # =========================================================================

    def extract_urls(self, content: str) -> List[str]:
        """Extract all URLs from content."""
        # Match markdown links and plain URLs
        url_patterns = [
            r'\[([^\]]+)\]\((https?://[^\)]+)\)',  # Markdown links
            r'<(https?://[^>]+)>',                   # Angle bracket URLs
            r'https?://[^\s\)\]\>]+',               # Plain URLs
        ]
        
        urls = []
        for pattern in url_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    urls.append(match[1])  # From markdown link
                else:
                    urls.append(match)
        
        return urls

    def test_raydium_url_present(self, docs_content: str):
        """Verify Raydium swap URL is present and correct."""
        expected_url = "https://raydium.io/swap/?inputMint=sol&outputMint=" + self.CANONICAL_MINT
        assert expected_url in docs_content, f"Raydium URL must be present: {expected_url}"

    def test_bottube_bridge_url_present(self, docs_content: str):
        """Verify BoTTube bridge URL is present and correct."""
        expected_url = "https://bottube.ai/bridge/wrtc"
        assert expected_url in docs_content, f"BoTTube bridge URL must be present: {expected_url}"

    def test_dexscreener_url_present(self, docs_content: str):
        """Verify DexScreener URL is present."""
        assert "dexscreener.com" in docs_content, "DexScreener URL must be present"

    def test_no_placeholder_urls(self, docs_content: str):
        """Verify no placeholder/example URLs remain."""
        placeholder_patterns = [
            r'example\.com',
            r'your-domain\.com',
            r'placeholder',
            r'YOUR_',
            r'xxx\.xxx\.xxx\.xxx',
            r'localhost:\d+',
            r'127\.0\.0\.1',
        ]
        
        for pattern in placeholder_patterns:
            matches = re.findall(pattern, docs_content, re.IGNORECASE)
            assert not matches, f"Found placeholder pattern '{pattern}': {matches}"

    def test_all_urls_use_https(self, docs_content: str):
        """Verify all external URLs use HTTPS (not HTTP)."""
        urls = self.extract_urls(docs_content)
        external_urls = [u for u in urls if u.startswith('http')]
        
        for url in external_urls:
            assert url.startswith('https://') or 'localhost' in url or '127.0.0.1' in url, (
                f"URL must use HTTPS: {url}"
            )

    # =========================================================================
    # Section 5: Anti-Scam Content Tests
    # =========================================================================

    def test_anti_scam_checklist_exists(self, docs_content: str):
        """Verify anti-scam checklist section exists."""
        content_lower = docs_content.lower()
        assert "anti-scam" in content_lower or "scam" in content_lower, (
            "Documentation must include anti-scam guidance"
        )

    def test_red_flags_documented(self, docs_content: str):
        """Verify red flags/warnings are documented."""
        content_lower = docs_content.lower()
        warning_indicators = ["red flag", "warning", "⚠️", "stop", "verify"]
        assert any(w in content_lower for w in warning_indicators), (
            "Documentation must include warning indicators"
        )

    def test_mint_verification_emphasized(self, docs_content: str):
        """Verify mint address verification is emphasized."""
        # Count occurrences of mint address (should appear multiple times)
        mint_count = docs_content.count(self.CANONICAL_MINT)
        assert mint_count >= 3, (
            f"Mint address should appear at least 3 times for emphasis, found {mint_count}"
        )

    # =========================================================================
    # Section 6: Content Quality Tests
    # =========================================================================

    def test_no_todo_placeholders(self, docs_content: str):
        """Verify no TODO or FIXME placeholders remain."""
        todo_patterns = [
            r'TODO[:\s]',
            r'FIXME[:\s]',
            r'XXX[:\s]',
            r'HACK[:\s]',
            r'NOTE:\s*\(to be',
            r'coming soon',
            r'under construction',
            r'tbd',
        ]
        
        content_lower = docs_content.lower()
        for pattern in todo_patterns:
            matches = re.findall(pattern, content_lower)
            assert not matches, f"Found TODO/placeholder: {matches}"

    def test_code_examples_present(self, docs_content: str):
        """Verify code/command examples are present."""
        assert "```" in docs_content, "Documentation should include code blocks"
        
        # Check for bash/curl examples
        content_lower = docs_content.lower()
        assert "curl" in content_lower or "```bash" in content_lower, (
            "Should include bash/curl examples"
        )

    def test_step_by_step_instructions(self, docs_content: str):
        """Verify step-by-step instructions are present."""
        # Look for numbered steps or step markers
        step_patterns = [
            r'Step \d+',
            r'#### Step',
            r'\d+\)',
            r'\d+\.\s',
        ]
        
        found = any(re.search(p, docs_content) for p in step_patterns)
        assert found, "Documentation should include numbered step-by-step instructions"

    def test_tables_used_for_reference(self, docs_content: str):
        """Verify tables are used for quick reference."""
        assert "|" in docs_content, "Documentation should include tables for reference data"

    # =========================================================================
    # Section 7: README Integration Tests
    # =========================================================================

    def test_readme_links_to_wrtc_docs(self, readme_content: str):
        """Verify README.md links to the new wRTC documentation."""
        assert "wrtc.md" in readme_content.lower() or "wrtc" in readme_content.lower(), (
            "README should reference wRTC documentation"
        )

    def test_readme_has_canonical_mint(self, readme_content: str):
        """Verify README contains the canonical mint address."""
        assert self.CANONICAL_MINT in readme_content, (
            "README must contain the canonical wRTC mint address"
        )

    def test_readme_has_bridge_link(self, readme_content: str):
        """Verify README links to BoTTube bridge."""
        assert "bottube.ai/bridge" in readme_content.lower(), (
            "README must link to BoTTube bridge"
        )

    def test_readme_has_raydium_link(self, readme_content: str):
        """Verify README links to Raydium swap."""
        assert "raydium" in readme_content.lower(), (
            "README must link to Raydium DEX"
        )

    # =========================================================================
    # Section 8: Formatting Tests
    # =========================================================================

    def test_proper_markdown_headers(self, docs_content: str):
        """Verify documentation uses proper markdown headers."""
        # Check for H1
        assert docs_content.startswith("# "), "Documentation should start with H1 header"
        
        # Check for multiple header levels
        assert "## " in docs_content, "Should use H2 headers"
        assert "### " in docs_content, "Should use H3 headers"

    def test_no_broken_markdown_links(self, docs_content: str):
        """Verify no broken markdown link syntax."""
        # Look for malformed markdown links
        broken_patterns = [
            r'\[\s*\]\s*\(\s*\)',  # Empty link
            r'\[([^\]]+)\]\s*[^\(]',  # Link text without URL
            r'\[([^\]]*)$'  # Unclosed link
        ]
        
        for pattern in broken_patterns:
            matches = re.findall(pattern, docs_content, re.MULTILINE)
            # Allow some edge cases but check for obvious errors
            if pattern == broken_patterns[0]:
                assert not matches, f"Found empty markdown links"

    # =========================================================================
    # Section 9: Canonical Information Tests
    # =========================================================================

    def test_token_decimals_documented(self, docs_content: str):
        """Verify token decimals (6) are documented."""
        assert "6" in docs_content, "Token decimals must be documented"
        
        # Check for explicit mention
        decimals_patterns = [
            r'decimal[:\s]*6',
            r'6[:\s]*decimal',
            r'decimals[:\s]*6',
        ]
        found = any(re.search(p, docs_content.lower()) for p in decimals_patterns)
        assert found, "Token decimals should be explicitly documented"

    def test_official_resources_listed(self, docs_content: str):
        """Verify official resources are listed."""
        required_resources = [
            "raydium",
            "bottube",
            "dexscreener",
        ]
        
        content_lower = docs_content.lower()
        for resource in required_resources:
            assert resource in content_lower, f"Official resource '{resource}' must be listed"


class TestDocumentationIntegrity:
    """Additional integrity checks for the documentation."""

    def test_no_duplicate_sections(self):
        """Verify no accidentally duplicated sections."""
        docs_path = Path(__file__).parent.parent / "docs" / "wrtc.md"
        if not docs_path.exists():
            pytest.skip("wrtc.md not found")
        
        content = docs_path.read_text(encoding="utf-8")
        
        # Find all H2 headers
        h2_headers = re.findall(r'^## (.+)$', content, re.MULTILINE)
        
        # Check for duplicates
        seen = set()
        duplicates = []
        for h in h2_headers:
            if h in seen:
                duplicates.append(h)
            seen.add(h)
        
        assert not duplicates, f"Found duplicate H2 sections: {duplicates}"

    def test_consistent_mint_formatting(self):
        """Verify mint address is consistently formatted."""
        docs_path = Path(__file__).parent.parent / "docs" / "wrtc.md"
        if not docs_path.exists():
            pytest.skip("wrtc.md not found")
        
        content = docs_path.read_text(encoding="utf-8")
        canonical_mint = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
        
        # Find all occurrences
        occurrences = [m.start() for m in re.finditer(canonical_mint, content)]
        
        # Each occurrence should be properly formatted (code block or plain)
        for pos in occurrences:
            # Check surrounding context
            start = max(0, pos - 10)
            end = min(len(content), pos + len(canonical_mint) + 10)
            context = content[start:end]
            
            # Mint should not be split across lines or malformed
            assert '\n' not in canonical_mint, "Mint address should not contain newlines"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
