# SPDX-License-Identifier: MIT

import os
import re
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

class SeverityLevel(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

@dataclass
class ValidationIssue:
    severity: SeverityLevel
    category: str
    message: str
    line_number: Optional[int] = None
    suggestion: Optional[str] = None

class TranslationVerifier:
    def __init__(self, original_readme_path: str = "README.md"):
        self.original_path = original_readme_path
        self.technical_terms = self._load_technical_terms()
        self.required_sections = self._extract_required_sections()

    def _load_technical_terms(self) -> Set[str]:
        """Load technical terms that should remain consistent across translations"""
        return {
            "RustChain", "Rustchain", "blockchain", "cryptocurrency", "mining",
            "RTC", "proof-of-work", "hash", "nonce", "transaction", "wallet",
            "peer-to-peer", "node", "network", "consensus", "API", "JSON",
            "HTTP", "SQLite", "Python", "Flask", "WebSocket", "CORS",
            "bounty", "marketplace", "escrow", "miner", "difficulty",
            "block", "genesis", "merkle", "SHA-256", "ECDSA", "secp256k1"
        }

    def _extract_required_sections(self) -> List[str]:
        """Extract required section headers from original README"""
        if not os.path.exists(self.original_path):
            return []

        sections = []
        with open(self.original_path, 'r', encoding='utf-8') as f:
            content = f.read()

        header_pattern = r'^#+\s+(.+)$'
        for match in re.finditer(header_pattern, content, re.MULTILINE):
            header = match.group(1).strip()
            sections.append(header)

        return sections

    def verify_translation(self, translation_path: str, language_code: str) -> List[ValidationIssue]:
        """Main verification method"""
        issues = []

        if not os.path.exists(translation_path):
            issues.append(ValidationIssue(
                SeverityLevel.ERROR,
                "file",
                f"Translation file not found: {translation_path}"
            ))
            return issues

        with open(translation_path, 'r', encoding='utf-8') as f:
            translation_content = f.read()

        # Run all verification checks
        issues.extend(self._check_file_format(translation_content))
        issues.extend(self._check_structure_completeness(translation_content))
        issues.extend(self._check_technical_terms(translation_content))
        issues.extend(self._check_links_integrity(translation_content))
        issues.extend(self._check_code_blocks(translation_content))
        issues.extend(self._check_language_specific(translation_content, language_code))

        return issues

    def _check_file_format(self, content: str) -> List[ValidationIssue]:
        """Check basic file format requirements"""
        issues = []
        lines = content.split('\n')

        # Check encoding and BOM
        if content.startswith('\ufeff'):
            issues.append(ValidationIssue(
                SeverityLevel.WARNING,
                "format",
                "File contains BOM (Byte Order Mark), consider removing"
            ))

        # Check for Windows line endings
        if '\r\n' in content:
            issues.append(ValidationIssue(
                SeverityLevel.INFO,
                "format",
                "File uses Windows line endings (CRLF), consider using LF"
            ))

        # Check trailing whitespace
        for i, line in enumerate(lines, 1):
            if line.endswith(' ') or line.endswith('\t'):
                issues.append(ValidationIssue(
                    SeverityLevel.WARNING,
                    "format",
                    f"Line has trailing whitespace",
                    line_number=i
                ))

        return issues

    def _check_structure_completeness(self, content: str) -> List[ValidationIssue]:
        """Check if translation maintains required structure"""
        issues = []

        # Extract headers from translation
        header_pattern = r'^#+\s+(.+)$'
        translation_headers = []
        for match in re.finditer(header_pattern, content, re.MULTILINE):
            header = match.group(1).strip()
            translation_headers.append(header)

        # Check for major missing sections
        critical_sections = ["installation", "usage", "api", "license", "contributing"]
        content_lower = content.lower()

        for section in critical_sections:
            if not any(section in header.lower() for header in translation_headers):
                if section not in content_lower:
                    issues.append(ValidationIssue(
                        SeverityLevel.ERROR,
                        "structure",
                        f"Missing critical section: {section.title()}"
                    ))

        # Check badge preservation
        if "![" not in content or "](https://" not in content:
            issues.append(ValidationIssue(
                SeverityLevel.WARNING,
                "structure",
                "No badges or images found - ensure status badges are preserved"
            ))

        return issues

    def _check_technical_terms(self, content: str) -> List[ValidationIssue]:
        """Check technical term consistency"""
        issues = []

        # Find potential mistranslated technical terms
        for term in self.technical_terms:
            if term.lower() in ["rustchain", "rtc"]:
                # These should NEVER be translated
                if term not in content:
                    issues.append(ValidationIssue(
                        SeverityLevel.ERROR,
                        "technical",
                        f"Required term '{term}' not found - this should not be translated"
                    ))

        # Check for code-like patterns that might be mistranslated
        code_patterns = [
            r'`[^`]+`',  # inline code
            r'```[\s\S]*?```',  # code blocks
            r'https?://[^\s]+',  # URLs
            r'\w+\.\w+',  # file extensions
        ]

        for pattern in code_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # Simple heuristic: if it contains non-ASCII and looks technical
                if any(ord(c) > 127 for c in match) and any(tech in match.lower() for tech in ["api", "json", "http"]):
                    issues.append(ValidationIssue(
                        SeverityLevel.WARNING,
                        "technical",
                        f"Possible mistranslated code/URL: {match[:50]}...",
                        suggestion="Verify technical terms in code blocks are not translated"
                    ))

        return issues

    def _check_links_integrity(self, content: str) -> List[ValidationIssue]:
        """Check link integrity and formatting"""
        issues = []

        # Find all markdown links
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        links = re.findall(link_pattern, content)

        for text, url in links:
            # Check for broken relative links
            if url.startswith('./') or url.startswith('../'):
                # Convert to absolute path for checking
                abs_path = os.path.abspath(url)
                if not os.path.exists(abs_path):
                    issues.append(ValidationIssue(
                        SeverityLevel.WARNING,
                        "links",
                        f"Relative link may be broken: {url}"
                    ))

            # Check for obviously mistranslated URLs
            if any(ord(c) > 127 for c in url):
                issues.append(ValidationIssue(
                    SeverityLevel.ERROR,
                    "links",
                    f"URL appears to contain non-ASCII characters: {url}"
                ))

        return issues

    def _check_code_blocks(self, content: str) -> List[ValidationIssue]:
        """Check code block preservation"""
        issues = []

        # Find code blocks
        code_block_pattern = r'```(\w+)?\n([\s\S]*?)```'
        blocks = re.findall(code_block_pattern, content)

        for lang, code in blocks:
            # Check for translated comments in code
            lines = code.split('\n')
            for i, line in enumerate(lines, 1):
                # Simple heuristic for translated comments
                if line.strip().startswith('#') or line.strip().startswith('//'):
                    comment = line.strip()
                    if any(ord(c) > 127 for c in comment):
                        # Has non-ASCII, might be translated
                        issues.append(ValidationIssue(
                            SeverityLevel.INFO,
                            "code",
                            f"Code comment may be translated: {comment[:30]}...",
                            suggestion="Consider keeping code comments in English"
                        ))

        return issues

    def _check_language_specific(self, content: str, language_code: str) -> List[ValidationIssue]:
        """Perform language-specific validation"""
        issues = []

        # Language-specific character validation
        lang_chars = {
            'zh-CN': r'[\u4e00-\u9fff]',  # Chinese
            'zh-TW': r'[\u4e00-\u9fff]',
            'ja': r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]',  # Hiragana, Katakana, Kanji
            'ko': r'[\uac00-\ud7af]',  # Korean
            'ar': r'[\u0600-\u06ff]',  # Arabic
            'ru': r'[\u0400-\u04ff]',  # Cyrillic
            'hi': r'[\u0900-\u097f]',  # Devanagari
        }

        if language_code in lang_chars:
            char_pattern = lang_chars[language_code]
            if not re.search(char_pattern, content):
                issues.append(ValidationIssue(
                    SeverityLevel.ERROR,
                    "language",
                    f"No {language_code} characters found - translation appears incomplete"
                ))

        # Check for machine translation artifacts
        machine_patterns = [
            r'\b(google|谷歌|구글)\s*(translate|翻译|번역)\b',
            r'\b(deepl|딥엘)\b',
            r'\[translated?\]',
        ]

        for pattern in machine_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(ValidationIssue(
                    SeverityLevel.WARNING,
                    "quality",
                    "Possible machine translation artifacts detected"
                ))

        return issues

    def generate_report(self, issues: List[ValidationIssue], translation_path: str) -> str:
        """Generate a formatted verification report"""
        report_lines = []
        report_lines.append(f"Translation Verification Report")
        report_lines.append(f"File: {translation_path}")
        report_lines.append(f"Issues found: {len(issues)}")
        report_lines.append("")

        # Group by severity
        by_severity = {}
        for issue in issues:
            if issue.severity not in by_severity:
                by_severity[issue.severity] = []
            by_severity[issue.severity].append(issue)

        for severity in [SeverityLevel.ERROR, SeverityLevel.WARNING, SeverityLevel.INFO]:
            if severity in by_severity:
                report_lines.append(f"{severity.value.upper()} ({len(by_severity[severity])} issues):")
                for issue in by_severity[severity]:
                    line_info = f" (line {issue.line_number})" if issue.line_number else ""
                    report_lines.append(f"  [{issue.category}]{line_info} {issue.message}")
                    if issue.suggestion:
                        report_lines.append(f"    Suggestion: {issue.suggestion}")
                report_lines.append("")

        # Summary
        error_count = len(by_severity.get(SeverityLevel.ERROR, []))
        if error_count == 0:
            report_lines.append("✅ Translation passes basic verification!")
        else:
            report_lines.append(f"❌ Translation has {error_count} critical errors that must be fixed.")

        return "\n".join(report_lines)

def main():
    """CLI interface for translation verification"""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python translation_verifier.py <translation_file> <language_code>")
        print("Example: python translation_verifier.py README_zh-CN.md zh-CN")
        sys.exit(1)

    translation_file = sys.argv[1]
    language_code = sys.argv[2]

    verifier = TranslationVerifier()
    issues = verifier.verify_translation(translation_file, language_code)
    report = verifier.generate_report(issues, translation_file)

    print(report)

    # Exit with error code if critical issues found
    error_count = sum(1 for issue in issues if issue.severity == SeverityLevel.ERROR)
    sys.exit(1 if error_count > 0 else 0)

if __name__ == "__main__":
    main()
