# SPDX-License-Identifier: MIT

"""
Tests for translation verifier including section validation, technical term checks,
format consistency, and error handling.
"""

import pytest
import tempfile
import os
from unittest.mock import patch, mock_open
from tools.translation_verifier import (
    TranslationVerifier,
    validate_translation_file,
    check_technical_terms_consistency,
    verify_markdown_structure,
    TranslationError
)


class TestTranslationVerifier:

    def setup_method(self):
        self.verifier = TranslationVerifier()
        self.sample_original = """# RustChain

A proof-of-work blockchain implementation in Python.

## Features

- Decentralized mining network
- Smart contracts via REST API
- RustChain Token (RTC) rewards

## Installation

```bash
pip install -r requirements.txt
python node/rustchain.py --host 0.0.0.0 --port 8545
```

## API Reference

POST /submit_transaction - Submit a new transaction
GET /balance/{miner_id} - Get wallet balance
"""

    def test_verifier_initialization(self):
        """Test TranslationVerifier initializes correctly"""
        assert self.verifier.original_content is None
        assert self.verifier.translation_content is None
        assert len(self.verifier.technical_terms) > 0
        assert "RustChain" in self.verifier.technical_terms

    def test_load_original_content_valid_file(self):
        """Test loading original README content"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(self.sample_original)
            temp_path = f.name

        try:
            self.verifier.load_original_content(temp_path)
            assert self.verifier.original_content == self.sample_original
        finally:
            os.unlink(temp_path)

    def test_load_original_content_missing_file(self):
        """Test error handling for missing original file"""
        with pytest.raises(TranslationError, match="Original file not found"):
            self.verifier.load_original_content("nonexistent.md")

    def test_validate_markdown_structure_complete(self):
        """Test markdown structure validation with complete sections"""
        self.verifier.original_content = self.sample_original
        translation = """# RustChain
Implementación blockchain proof-of-work en Python.
## Características
- Red de minería descentralizada
- Smart contracts vía API REST
- Recompensas RustChain Token (RTC)
## Instalación
```bash
pip install -r requirements.txt
python node/rustchain.py --host 0.0.0.0 --port 8545
```
## Referencia API
POST /submit_transaction - Enviar nueva transacción
"""

        result = self.verifier.validate_markdown_structure(translation)
        assert result['overall_valid'] == True
        assert len(result['missing_sections']) == 0

    def test_validate_markdown_structure_missing_sections(self):
        """Test markdown structure validation with missing sections"""
        self.verifier.original_content = self.sample_original
        translation = """# RustChain
Implementación blockchain proof-of-work en Python.
## Características
- Red de minería descentralizada
"""

        result = self.verifier.validate_markdown_structure(translation)
        assert result['overall_valid'] == False
        assert len(result['missing_sections']) > 0

    def test_check_technical_terms_preserved(self):
        """Test technical terms checking when preserved"""
        translation = """# RustChain
Un sistema blockchain con RTC tokens y mining distribuido.
Utiliza proof-of-work y wallet management.
"""

        result = self.verifier.check_technical_terms(translation)
        # Should have some missing terms but not all
        assert isinstance(result['missing_terms'], list)

    def test_check_technical_terms_missing(self):
        """Test technical terms checking when terms are missing"""
        translation = """# Sistema
Un sistema simple sin términos técnicos.
"""

        result = self.verifier.check_technical_terms(translation)
        assert result['overall_valid'] == False
        assert len(result['missing_terms']) > 0

    def test_validate_code_blocks_preserved(self):
        """Test code block validation when preserved"""
        original = """# Test
```bash
pip install requirements
```
"""
        translation = """# Prueba
```bash
pip install requirements
```
"""

        result = self.verifier.validate_code_blocks(original, translation)
        assert result['overall_valid'] == True
        assert len(result['issues']) == 0

    def test_validate_code_blocks_modified(self):
        """Test code block validation when modified"""
        original = """# Test
```bash
pip install requirements
```
"""
        translation = """# Prueba
```bash
pip install dependencias
```
"""

        result = self.verifier.validate_code_blocks(original, translation)
        assert result['overall_valid'] == False
        assert len(result['issues']) > 0

    def test_check_format_consistency(self):
        """Test format consistency checking"""
        valid_content = """# RustChain
## Section
Content here
"""

        result = self.verifier.check_format_consistency(valid_content)
        assert result['overall_valid'] == True

        invalid_content = """No main header
Just content
"""

        result = self.verifier.check_format_consistency(invalid_content)
        assert result['overall_valid'] == False

    def test_validate_language_detection(self):
        """Test language detection functionality"""
        portuguese_text = "Uma implementação blockchain em Python com tokens RTC"
        spanish_text = "Una implementación blockchain en Python con tokens RTC"
        english_text = "A blockchain implementation in Python with RTC tokens"

        assert self.verifier.detect_language(portuguese_text) == 'pt'
        assert self.verifier.detect_language(spanish_text) == 'es'
        assert self.verifier.detect_language(english_text) == 'en'

    def test_verify_translation_complete(self):
        """Test complete translation verification"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pt-BR.md', delete=False) as f:
            f.write("""# RustChain
Um sistema blockchain com RTC, mining, e wallet.
## Features
Características do sistema
```bash
pip install -r requirements.txt
```
""")
            temp_path = f.name

        try:
            issues = self.verifier.verify_translation(temp_path, 'pt-BR')
            assert isinstance(issues, list)
        finally:
            os.unlink(temp_path)


class TestStandaloneFunctions:

    def test_check_technical_terms_consistency(self):
        """Test standalone technical terms function"""
        content = "Simple text without technical terms"
        missing = check_technical_terms_consistency(content)
        assert isinstance(missing, list)
        assert len(missing) > 0

    def test_verify_markdown_structure(self):
        """Test standalone markdown structure function"""
        content = """# Main Header
## Sub Header
Content
"""
        result = verify_markdown_structure(content)
        assert 'overall_valid' in result
        assert 'found_headers' in result

    def test_validate_translation_file_missing(self):
        """Test validation with missing files"""
        result = validate_translation_file('nonexistent.md', 'also_nonexistent.md')
        assert 'valid' in result
        assert 'issues' in result
