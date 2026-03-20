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
        """Load original README content"""
        if not os.path.exists(file_path):
            raise TranslationError(f"Original file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            self.original_content = f.read()

    def load_translation_content(self, file_path: str) -> None:
        """Load translation content"""
        if not os.path.exists(file_path):
            raise TranslationError(f"Translation file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            self.translation_content = f.read()

    def validate_markdown_structure(self, content: str) -> List[ValidationIssue]:
        """Validate markdown structure completeness"""
        issues = []

        # Check for required sections
        header_pattern = r'^#+\s+(.+)$'
        found_headers = []

        for match in re.finditer(header_pattern, content, re.MULTILINE):
            header = match.group(1).strip()
            found_headers.append(header)

        # Check if all required sections are present
        missing_sections = []
        for required in self.required_sections:
            if not any(required.lower() in found.lower() for found in found_headers):
                missing_sections.append(required)

        if missing_sections:
            issues.append(ValidationIssue(
                severity=SeverityLevel.ERROR,
                category="structure",
                message=f"Missing required sections: {', '.join(missing_sections)}"
            ))

        return issues

    def check_technical_terms(self, content: str) -> List[ValidationIssue]:
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
                message=f"Missing technical terms: {', '.join(missing_terms)}"
            ))

        return issues

    def validate_code_blocks(self, original: str, translation: str) -> List[ValidationIssue]:
        """Validate that code blocks are preserved"""
        issues = []

        # Extract code blocks from both versions
        code_block_pattern = r'```[\s\S]*?```'
        original_blocks = re.findall(code_block_pattern, original)
        translation_blocks = re.findall(code_block_pattern, translation)

        if len(original_blocks) != len(translation_blocks):
            issues.append(ValidationIssue(
                severity=SeverityLevel.ERROR,
                category="code_blocks",
                message=f"Code block count mismatch: original has {len(original_blocks)}, translation has {len(translation_blocks)}"
            ))

        # Check if code content is preserved
        for i, (orig_block, trans_block) in enumerate(zip(original_blocks, translation_blocks)):
            if orig_block != trans_block:
                issues.append(ValidationIssue(
                    severity=SeverityLevel.ERROR,
                    category="code_blocks",
                    message=f"Code block {i+1} content modified"
                ))

        return issues

    def check_format_consistency(self, content: str) -> List[ValidationIssue]:
        """Check format consistency"""
        issues = []
        lines = content.split('\n')

        # Check for consistent heading format
        heading_pattern = r'^(#+)\s+(.+)$'
        for i, line in enumerate(lines):
            match = re.match(heading_pattern, line)
            if match:
                level = len(match.group(1))
                title = match.group(2)

                # Check for trailing spaces in headings
                if title != title.strip():
                    issues.append(ValidationIssue(
                        severity=SeverityLevel.WARNING,
                        category="format",
                        message=f"Heading has trailing spaces at line {i+1}",
                        line_number=i+1
                    ))

        return issues

    def detect_language(self, content: str) -> str:
        """Detect language of the content"""
        # Simple language detection based on common words
        content_lower = content.lower()

        if any(word in content_lower for word in ['visão geral', 'características', 'instalação', 'português']):
            return 'pt-BR'
        elif any(word in content_lower for word in ['overview', 'features', 'installation', 'english']):
            return 'en'
        elif any(word in content_lower for word in ['características', 'instalación', 'español']):
            return 'es'
        elif any(word in content_lower for word in ['aperçu', 'fonctionnalités', 'français']):
            return 'fr'
        else:
            return 'unknown'

    def verify_translation(self, translation_path: str, language_code: str) -> List[ValidationIssue]:
        """Main verification method"""
        issues = []

        # Load translation content
        try:
            self.load_translation_content(translation_path)
        except TranslationError as e:
            issues.append(ValidationIssue(
                severity=SeverityLevel.ERROR,
                category="file",
                message=str(e)
            ))
            return issues

        # Load original content if not already loaded
        if self.original_content is None:
            try:
                self.load_original_content(self.original_path)
            except TranslationError as e:
                issues.append(ValidationIssue(
                    severity=SeverityLevel.ERROR,
                    category="file",
                    message=str(e)
                ))
                return issues

        # Run all validation checks
        issues.extend(self.validate_markdown_structure(self.translation_content))
        issues.extend(self.check_technical_terms(self.translation_content))
        issues.extend(self.validate_code_blocks(self.original_content, self.translation_content))
        issues.extend(self.check_format_consistency(self.translation_content))

        # Verify detected language matches expected
        detected_lang = self.detect_language(self.translation_content)
        if detected_lang != language_code and detected_lang != 'unknown':
            issues.append(ValidationIssue(
                severity=SeverityLevel.WARNING,
                category="language",
                message=f"Language mismatch: expected {language_code}, detected {detected_lang}"
            ))

        return issues


def validate_translation_file(translation_path: str, language_code: str) -> Dict:
    """Standalone function to validate a translation file"""
    verifier = TranslationVerifier()
    issues = verifier.verify_translation(translation_path, language_code)

    return {
        'valid': len([i for i in issues if i.severity == SeverityLevel.ERROR]) == 0,
        'issues': [{
            'severity': issue.severity.value,
            'category': issue.category,
            'message': issue.message,
            'line_number': issue.line_number,
            'suggestion': issue.suggestion
        } for issue in issues]
    }


def check_technical_terms_consistency(translation_path: str) -> Dict:
    """Check technical terms consistency"""
    verifier = TranslationVerifier()
    try:
        verifier.load_translation_content(translation_path)
        issues = verifier.check_technical_terms(verifier.translation_content)

        return {
            'consistent': len(issues) == 0,
            'missing_terms': [issue.message for issue in issues if 'Missing technical terms' in issue.message]
        }
    except TranslationError as e:
        return {'consistent': False, 'error': str(e)}


def verify_markdown_structure(translation_path: str) -> Dict:
    """Verify markdown structure"""
    verifier = TranslationVerifier()
    try:
        verifier.load_translation_content(translation_path)
        issues = verifier.validate_markdown_structure(verifier.translation_content)

        return {
            'valid_structure': len([i for i in issues if i.severity == SeverityLevel.ERROR]) == 0,
            'structure_issues': [issue.message for issue in issues]
        }
    except TranslationError as e:
        return {'valid_structure': False, 'error': str(e)}
