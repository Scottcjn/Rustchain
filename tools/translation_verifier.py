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

class TranslationError(Exception):
    """Exception raised for translation validation errors."""
    pass

class TranslationVerifier:
    def __init__(self, original_readme_path: str = "README.md"):
        self.original_path = original_readme_path
        self.original_content = None
        self.translation_content = None
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

    def load_original_content(self, file_path: str) -> None:
        """Load the original README content"""
        if not os.path.exists(file_path):
            raise TranslationError(f"Original file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            self.original_content = f.read()

    def load_translation_content(self, file_path: str) -> None:
        """Load the translation content"""
        if not os.path.exists(file_path):
            raise TranslationError(f"Translation file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            self.translation_content = f.read()

    def verify_translation(self, translation_path: str, language_code: str) -> List[ValidationIssue]:
        """Verify a translation file against the original"""
        issues = []

        # Load translation content
        try:
            self.load_translation_content(translation_path)
        except TranslationError as e:
            issues.append(ValidationIssue(
                severity=SeverityLevel.ERROR,
                category="file_access",
                message=str(e)
            ))
            return issues

        # Verify markdown structure
        structure_issues = self._verify_markdown_structure()
        issues.extend(structure_issues)

        # Check technical terms consistency
        term_issues = self._check_technical_terms_consistency()
        issues.extend(term_issues)

        # Validate format consistency
        format_issues = self._validate_format_consistency()
        issues.extend(format_issues)

        return issues

    def _verify_markdown_structure(self) -> List[ValidationIssue]:
        """Verify markdown structure consistency"""
        issues = []

        if not self.translation_content:
            return issues

        # Check for required sections
        translation_sections = self._extract_sections_from_content(self.translation_content)

        for required_section in self.required_sections:
            if not any(required_section.lower() in section.lower() for section in translation_sections):
                issues.append(ValidationIssue(
                    severity=SeverityLevel.WARNING,
                    category="structure",
                    message=f"Missing section: {required_section}",
                    suggestion=f"Add section header for {required_section}"
                ))

        return issues

    def _extract_sections_from_content(self, content: str) -> List[str]:
        """Extract section headers from content"""
        sections = []
        header_pattern = r'^#+\s+(.+)$'
        for match in re.finditer(header_pattern, content, re.MULTILINE):
            header = match.group(1).strip()
            sections.append(header)
        return sections

    def _check_technical_terms_consistency(self) -> List[ValidationIssue]:
        """Check that technical terms are used consistently"""
        issues = []

        if not self.translation_content:
            return issues

        for term in self.technical_terms:
            if term.lower() in self.translation_content.lower():
                # Check if term appears in its original form
                if term not in self.translation_content:
                    issues.append(ValidationIssue(
                        severity=SeverityLevel.WARNING,
                        category="technical_terms",
                        message=f"Technical term '{term}' should be preserved as-is",
                        suggestion=f"Keep '{term}' in English"
                    ))

        return issues

    def _validate_format_consistency(self) -> List[ValidationIssue]:
        """Validate format consistency with original"""
        issues = []

        if not self.translation_content:
            return issues

        # Check for code blocks
        code_blocks = re.findall(r'```[\s\S]*?```', self.translation_content)
        if not code_blocks:
            issues.append(ValidationIssue(
                severity=SeverityLevel.INFO,
                category="format",
                message="No code blocks found - verify if this is expected"
            ))

        # Check for links
        links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', self.translation_content)
        if not links:
            issues.append(ValidationIssue(
                severity=SeverityLevel.INFO,
                category="format",
                message="No markdown links found - verify if this is expected"
            ))

        return issues


def validate_translation_file(translation_path: str, language_code: str) -> List[ValidationIssue]:
    """Validate a translation file"""
    verifier = TranslationVerifier()
    return verifier.verify_translation(translation_path, language_code)


def check_technical_terms_consistency(content: str) -> List[ValidationIssue]:
    """Check technical terms consistency in content"""
    verifier = TranslationVerifier()
    verifier.translation_content = content
    return verifier._check_technical_terms_consistency()


def verify_markdown_structure(content: str) -> List[ValidationIssue]:
    """Verify markdown structure"""
    verifier = TranslationVerifier()
    verifier.translation_content = content
    return verifier._verify_markdown_structure()
