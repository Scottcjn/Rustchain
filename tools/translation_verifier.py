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

    def load_original_content(self, path: str) -> None:
        """Load the original README content"""
        if not os.path.exists(path):
            raise TranslationError(f"Original file not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            self.original_content = f.read()

    def load_translation_content(self, path: str) -> None:
        """Load the translation content"""
        if not os.path.exists(path):
            raise TranslationError(f"Translation file not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            self.translation_content = f.read()

    def validate_markdown_structure(self, content: str) -> Dict[str, any]:
        """Validate markdown structure of translation"""
        issues = []
        missing_sections = []

        # Extract headers from content
        header_pattern = r'^#+\s+(.+)$'
        found_headers = []
        for match in re.finditer(header_pattern, content, re.MULTILINE):
            header = match.group(1).strip()
            found_headers.append(header)

        # Check for missing required sections
        for required in self.required_sections:
            if not any(required.lower() in header.lower() for header in found_headers):
                missing_sections.append(required)

        if missing_sections:
            issues.append(ValidationIssue(
                severity=SeverityLevel.ERROR,
                category="structure",
                message=f"Missing required sections: {', '.join(missing_sections)}"
            ))

        return {
            "issues": issues,
            "missing_sections": missing_sections,
            "found_headers": found_headers,
            "overall_valid": len(missing_sections) == 0
        }

    def check_technical_terms(self, content: str) -> Dict[str, any]:
        """Check if technical terms are preserved"""
        issues = []
        missing_terms = []

        for term in self.technical_terms:
            if term not in content:
                missing_terms.append(term)

        if missing_terms:
            issues.append(ValidationIssue(
                severity=SeverityLevel.WARNING,
                category="technical_terms",
                message=f"Missing technical terms: {', '.join(missing_terms[:5])}"
            ))

        return {
            "issues": issues,
            "missing_terms": missing_terms,
            "overall_valid": len(missing_terms) == 0
        }

    def validate_code_blocks(self, original: str, translation: str) -> Dict[str, any]:
        """Validate that code blocks are preserved"""
        issues = []

        # Extract code blocks
        code_pattern = r'```[\w]*\n([\s\S]*?)```'
        original_blocks = re.findall(code_pattern, original)
        translation_blocks = re.findall(code_pattern, translation)

        if len(original_blocks) != len(translation_blocks):
            issues.append(ValidationIssue(
                severity=SeverityLevel.ERROR,
                category="code_blocks",
                message=f"Code block count mismatch: {len(original_blocks)} vs {len(translation_blocks)}"
            ))

        # Check if code blocks are identical
        for i, (orig, trans) in enumerate(zip(original_blocks, translation_blocks)):
            if orig.strip() != trans.strip():
                issues.append(ValidationIssue(
                    severity=SeverityLevel.ERROR,
                    category="code_blocks",
                    message=f"Code block {i+1} modified in translation"
                ))

        return {
            "issues": issues,
            "original_blocks": original_blocks,
            "translation_blocks": translation_blocks,
            "overall_valid": len(issues) == 0
        }

    def check_format_consistency(self, content: str) -> Dict[str, any]:
        """Check format consistency"""
        issues = []

        # Check for proper markdown formatting
        if not re.search(r'^#\s+', content, re.MULTILINE):
            issues.append(ValidationIssue(
                severity=SeverityLevel.ERROR,
                category="format",
                message="No main header found"
            ))

        return {
            "issues": issues,
            "overall_valid": len(issues) == 0
        }

    def detect_language(self, content: str) -> str:
        """Detect the language of the content"""
        # Simple language detection based on common words
        portuguese_indicators = ['o', 'a', 'e', 'de', 'para', 'com', 'uma', 'um', 'são', 'é']
        spanish_indicators = ['el', 'la', 'y', 'de', 'para', 'con', 'una', 'un', 'son', 'es']
        french_indicators = ['le', 'la', 'et', 'de', 'pour', 'avec', 'une', 'un', 'sont', 'est']

        words = content.lower().split()

        pt_count = sum(1 for word in words if word in portuguese_indicators)
        es_count = sum(1 for word in words if word in spanish_indicators)
        fr_count = sum(1 for word in words if word in french_indicators)

        if pt_count > es_count and pt_count > fr_count:
            return 'pt'
        elif es_count > fr_count:
            return 'es'
        elif fr_count > 0:
            return 'fr'
        else:
            return 'en'

    def verify_translation(self, translation_path: str, language_code: str) -> List[ValidationIssue]:
        """Verify a complete translation file"""
        all_issues = []

        # Load translation content
        self.load_translation_content(translation_path)

        # Run all validations
        structure_result = self.validate_markdown_structure(self.translation_content)
        all_issues.extend(structure_result['issues'])

        terms_result = self.check_technical_terms(self.translation_content)
        all_issues.extend(terms_result['issues'])

        format_result = self.check_format_consistency(self.translation_content)
        all_issues.extend(format_result['issues'])

        if self.original_content:
            code_result = self.validate_code_blocks(self.original_content, self.translation_content)
            all_issues.extend(code_result['issues'])

        return all_issues


def validate_translation_file(translation_path: str, original_path: str = "README.md") -> Dict[str, any]:
    """Standalone function to validate a translation file"""
    verifier = TranslationVerifier(original_path)

    if os.path.exists(original_path):
        verifier.load_original_content(original_path)

    language_code = Path(translation_path).stem.split('.')[-1] if '.' in Path(translation_path).stem else 'unknown'
    issues = verifier.verify_translation(translation_path, language_code)

    return {
        "valid": len([i for i in issues if i.severity == SeverityLevel.ERROR]) == 0,
        "issues": issues,
        "language_code": language_code
    }


def check_technical_terms_consistency(content: str) -> List[str]:
    """Standalone function to check technical terms"""
    verifier = TranslationVerifier()
    result = verifier.check_technical_terms(content)
    return result['missing_terms']


def verify_markdown_structure(content: str) -> Dict[str, any]:
    """Standalone function to verify markdown structure"""
    verifier = TranslationVerifier()
    return verifier.validate_markdown_structure(content)
