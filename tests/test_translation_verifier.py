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

    def test_load_translation_content(self):
        """Test loading translation file content"""
        translation_text = """# RustChain

Une implémentation blockchain proof-of-work en Python.

## Fonctionnalités

- Réseau de minage décentralisé
- Smart contracts via API REST
- Récompenses RustChain Token (RTC)
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(translation_text)
            temp_path = f.name

        try:
            self.verifier.load_translation_content(temp_path)
            assert self.verifier.translation_content == translation_text
        finally:
            os.unlink(temp_path)

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
GET /balance/{miner_id} - Obtener balance
"""
        self.verifier.translation_content = translation

        result = self.verifier.validate_markdown_structure()
        assert result["valid"] is True
        assert len(result["missing_sections"]) == 0

    def test_validate_markdown_structure_missing_sections(self):
        """Test detection of missing sections"""
        self.verifier.original_content = self.sample_original
        incomplete_translation = """# RustChain

Implementación blockchain proof-of-work en Python.

## Características

- Red de minería descentralizada
"""
        self.verifier.translation_content = incomplete_translation

        result = self.verifier.validate_markdown_structure()
        assert result["valid"] is False
        assert "Installation" in result["missing_sections"]
        assert "API Reference" in result["missing_sections"]

    def test_check_technical_terms_preserved(self):
        """Test that technical terms are preserved in translation"""
        translation_with_terms = """# RustChain

Implementation blockchain proof-of-work en español.

- REST API funciona bien
- RTC rewards para mineros
- POST /submit_transaction endpoint
"""
        self.verifier.translation_content = translation_with_terms

        result = self.verifier.check_technical_terms()
        assert result["terms_preserved"] is True
        assert len(result["missing_terms"]) == 0

    def test_check_technical_terms_missing(self):
        """Test detection of missing technical terms"""
        translation_missing_terms = """# CadenaRust

Implementación blockchain prueba-de-trabajo en español.

- API REST funciona bien
- Recompensas tokens para mineros
"""
        self.verifier.translation_content = translation_missing_terms

        result = self.verifier.check_technical_terms()
        assert result["terms_preserved"] is False
        assert "RustChain" in result["missing_terms"]
        assert "RTC" in result["missing_terms"]

    def test_validate_code_blocks_preserved(self):
        """Test that code blocks remain unchanged"""
        translation_with_code = """# RustChain

Instalación:

```bash
pip install -r requirements.txt
python node/rustchain.py --host 0.0.0.0 --port 8545
```

Comandos útiles.
"""
        self.verifier.original_content = self.sample_original
        self.verifier.translation_content = translation_with_code

        result = self.verifier.validate_code_blocks()
        assert result["code_preserved"] is True

    def test_validate_code_blocks_modified(self):
        """Test detection of modified code blocks"""
        translation_bad_code = """# RustChain

Instalación:

```bash
pip instalar -r requisitos.txt
python nodo/rustchain.py --host 0.0.0.0 --puerto 8545
```
"""
        self.verifier.original_content = self.sample_original
        self.verifier.translation_content = translation_bad_code

        result = self.verifier.validate_code_blocks()
        assert result["code_preserved"] is False

    def test_check_format_consistency(self):
        """Test format consistency validation"""
        consistent_translation = """# RustChain

Una implementación blockchain proof-of-work en Python.

## Características

- Red minería descentralizada
- Smart contracts via REST API
- Recompensas RustChain Token (RTC)

## Instalación

```bash
pip install -r requirements.txt
python node/rustchain.py --host 0.0.0.0 --port 8545
```
"""
        self.verifier.original_content = self.sample_original
        self.verifier.translation_content = consistent_translation

        result = self.verifier.check_format_consistency()
        assert result["format_consistent"] is True
        assert result["heading_count_match"] is True

    def test_validate_language_detection(self):
        """Test language detection for translation"""
        spanish_text = """# RustChain

Una implementación blockchain de prueba de trabajo en Python.

## Características

- Red de minería descentralizada
- Contratos inteligentes vía API REST
- Recompensas con RustChain Token (RTC)
"""
        self.verifier.translation_content = spanish_text

        detected_lang = self.verifier.detect_language()
        # Language detection may vary, so we check it's not English
        assert detected_lang != "en"

    def test_full_validation_workflow(self):
        """Test complete validation workflow"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as orig_f:
            orig_f.write(self.sample_original)
            orig_path = orig_f.name

        good_translation = """# RustChain

Una implementación blockchain proof-of-work en Python.

## Características

- Red de minería descentralizada
- Smart contracts vía REST API
- Recompensas RustChain Token (RTC)

## Instalación

```bash
pip install -r requirements.txt
python node/rustchain.py --host 0.0.0.0 --port 8545
```

## Referencia API

POST /submit_transaction - Enviar nueva transacción
GET /balance/{miner_id} - Obtener balance cartera
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as trans_f:
            trans_f.write(good_translation)
            trans_path = trans_f.name

        try:
            result = validate_translation_file(orig_path, trans_path)
            assert result["overall_valid"] is True
            assert result["structure_valid"] is True
            assert result["technical_terms_preserved"] is True
        finally:
            os.unlink(orig_path)
            os.unlink(trans_path)

    def test_validation_with_errors(self):
        """Test validation with multiple errors"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as orig_f:
            orig_f.write(self.sample_original)
            orig_path = orig_f.name

        bad_translation = """# CadenaRust

Implementación blockchain en Python.

## Características

- Red de minería

```bash
pip instalar requisitos.txt
```
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as trans_f:
            trans_f.write(bad_translation)
            trans_path = trans_f.name

        try:
            result = validate_translation_file(orig_path, trans_path)
            assert result["overall_valid"] is False
            assert len(result["errors"]) > 0
        finally:
            os.unlink(orig_path)
            os.unlink(trans_path)

    def test_check_technical_terms_consistency(self):
        """Test standalone technical terms checking function"""
        original = "Use RustChain API for RTC transactions"
        good_translation = "Usa RustChain API para transacciones RTC"
        bad_translation = "Usa CadenaRust API para transacciones Token"

        assert check_technical_terms_consistency(original, good_translation) is True
        assert check_technical_terms_consistency(original, bad_translation) is False

    def test_verify_markdown_structure_standalone(self):
        """Test standalone markdown structure verification"""
        original = """# Title
## Section 1
### Subsection
## Section 2"""

        good_structure = """# Título
## Sección 1
### Subsección
## Sección 2"""

        bad_structure = """# Título
## Sección 1"""

        assert verify_markdown_structure(original, good_structure) is True
        assert verify_markdown_structure(original, bad_structure) is False

    def test_error_handling_empty_files(self):
        """Test error handling with empty translation files"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as orig_f:
            orig_f.write(self.sample_original)
            orig_path = orig_f.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as trans_f:
            trans_f.write("")
            trans_path = trans_f.name

        try:
            with pytest.raises(TranslationError, match="Translation file is empty"):
                validate_translation_file(orig_path, trans_path)
        finally:
            os.unlink(orig_path)
            os.unlink(trans_path)

    def test_file_encoding_handling(self):
        """Test handling of different file encodings"""
        unicode_content = """# RustChain

Implementación blockchain en español con caracteres especiales: ñáéíóú.

## Características

- Red de minería descentralizada
- Smart contracts vía REST API
- Recompensas RustChain Token (RTC)
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', encoding='utf-8', delete=False) as f:
            f.write(unicode_content)
            temp_path = f.name

        try:
            self.verifier.load_translation_content(temp_path)
            assert "ñáéíóú" in self.verifier.translation_content
        finally:
            os.unlink(temp_path)
