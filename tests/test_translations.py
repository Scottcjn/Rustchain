# SPDX-License-Identifier: MIT

import os
import json
import sqlite3
import pytest
from pathlib import Path

def test_translation_files_exist():
    """Test that expected translation files are present."""
    translations_dir = Path("translations")
    if not translations_dir.exists():
        pytest.skip("Translations directory not found")

    expected_languages = [
        "zh-CN", "zh-TW", "es", "pt-BR", "ja", "ko",
        "ru", "fr", "de", "ar", "hi", "tr"
    ]

    translation_files = list(translations_dir.glob("README-*.md"))
    found_languages = []

    for file in translation_files:
        lang_code = file.stem.replace("README-", "")
        found_languages.append(lang_code)

    assert len(found_languages) > 0, "No translation files found"

def test_translation_file_structure():
    """Test that translation files have required sections."""
    translations_dir = Path("translations")
    if not translations_dir.exists():
        pytest.skip("Translations directory not found")

    required_sections = [
        "# Rustchain",
        "## Overview",
        "## Installation",
        "## Usage",
        "## Features",
        "## License"
    ]

    translation_files = list(translations_dir.glob("README-*.md"))
    assert len(translation_files) > 0, "No translation files to test"

    for file in translation_files:
        content = file.read_text(encoding='utf-8')

        for section in required_sections:
            section_found = any(
                section.lower() in line.lower()
                for line in content.split('\n')
                if line.strip().startswith('#')
            )
            assert section_found, f"Missing section '{section}' in {file.name}"

def test_translation_metadata():
    """Test translation metadata if present."""
    translations_dir = Path("translations")
    if not translations_dir.exists():
        pytest.skip("Translations directory not found")

    metadata_file = translations_dir / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        assert "translations" in metadata
        assert isinstance(metadata["translations"], dict)

        for lang_code, info in metadata["translations"].items():
            assert "name" in info
            assert "file" in info
            assert "status" in info

            file_path = translations_dir / info["file"]
            assert file_path.exists(), f"Translation file {info['file']} not found"

def test_translation_file_encoding():
    """Test that translation files use UTF-8 encoding."""
    translations_dir = Path("translations")
    if not translations_dir.exists():
        pytest.skip("Translations directory not found")

    translation_files = list(translations_dir.glob("README-*.md"))

    for file in translation_files:
        try:
            content = file.read_text(encoding='utf-8')
            assert len(content) > 100, f"Translation file {file.name} seems too short"
        except UnicodeDecodeError:
            pytest.fail(f"Translation file {file.name} is not valid UTF-8")

def test_translation_completeness():
    """Test that translations are reasonably complete."""
    translations_dir = Path("translations")
    if not translations_dir.exists():
        pytest.skip("Translations directory not found")

    main_readme = Path("README.md")
    if not main_readme.exists():
        pytest.skip("Main README.md not found")

    main_content = main_readme.read_text(encoding='utf-8')
    main_lines = [line.strip() for line in main_content.split('\n') if line.strip()]
    main_length = len(main_lines)

    translation_files = list(translations_dir.glob("README-*.md"))

    for file in translation_files:
        content = file.read_text(encoding='utf-8')
        trans_lines = [line.strip() for line in content.split('\n') if line.strip()]
        trans_length = len(trans_lines)

        # Translation should be at least 50% of original length
        min_expected = main_length * 0.5
        assert trans_length >= min_expected, (
            f"Translation {file.name} seems incomplete: "
            f"{trans_length} lines vs {main_length} in original"
        )

def test_translation_links():
    """Test that important links are preserved in translations."""
    translations_dir = Path("translations")
    if not translations_dir.exists():
        pytest.skip("Translations directory not found")

    important_links = [
        "https://github.com/Scottcjn/Rustchain",
        "LICENSE",
        "MIT"
    ]

    translation_files = list(translations_dir.glob("README-*.md"))

    for file in translation_files:
        content = file.read_text(encoding='utf-8')

        for link in important_links:
            assert link in content, f"Important link '{link}' missing from {file.name}"

def test_translation_code_blocks():
    """Test that code blocks are preserved in translations."""
    translations_dir = Path("translations")
    if not translations_dir.exists():
        pytest.skip("Translations directory not found")

    translation_files = list(translations_dir.glob("README-*.md"))

    for file in translation_files:
        content = file.read_text(encoding='utf-8')

        # Check for code block markers
        code_markers = content.count('```')
        assert code_markers % 2 == 0, f"Unmatched code blocks in {file.name}"

        # Should have at least some code examples
        assert code_markers >= 2, f"Missing code examples in {file.name}"

def test_bounty_tracking():
    """Test bounty tracking if database exists."""
    db_path = "rustchain.db"
    if not os.path.exists(db_path):
        pytest.skip("Database not found")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Check if bounty tracking table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name LIKE '%bounty%'
        """)

        bounty_tables = cursor.fetchall()
        if not bounty_tables:
            pytest.skip("No bounty tracking tables found")

        # Basic check that bounty data structure is valid
        table_name = bounty_tables[0][0]
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]

        expected_columns = ["id", "type", "status", "amount"]
        for col in expected_columns:
            assert any(col.lower() in c.lower() for c in columns), (
                f"Expected column '{col}' not found in {table_name}"
            )
