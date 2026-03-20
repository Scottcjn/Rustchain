// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import sys
import unittest
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestContributors(unittest.TestCase):
    """Test suite for CONTRIBUTORS.md validation."""

    def setUp(self):
        self.contributors_path = project_root / 'CONTRIBUTORS.md'

    def test_contributors_file_exists(self):
        """Test that CONTRIBUTORS.md exists in the repository."""
        self.assertTrue(
            self.contributors_path.exists(),
            "CONTRIBUTORS.md file not found in repository root"
        )

    def test_contributors_file_readable(self):
        """Test that CONTRIBUTORS.md is readable."""
        try:
            with open(self.contributors_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertIsInstance(content, str)
            self.assertGreater(len(content), 0, "CONTRIBUTORS.md is empty")
        except Exception as e:
            self.fail(f"Failed to read CONTRIBUTORS.md: {e}")

    def test_contributors_has_header(self):
        """Test that CONTRIBUTORS.md has proper header structure."""
        with open(self.contributors_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for title header
        self.assertIn('# Contributors', content, "Missing main header '# Contributors'")

    def test_contributors_has_sections(self):
        """Test that CONTRIBUTORS.md has expected sections."""
        with open(self.contributors_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        content_lower = ''.join(lines).lower()

        # Check for common contributor sections
        expected_sections = ['contributors', 'thank', 'community']
        found_sections = []

        for section in expected_sections:
            if section in content_lower:
                found_sections.append(section)

        self.assertGreater(
            len(found_sections), 0,
            "No expected sections found in CONTRIBUTORS.md"
        )

    def test_contributors_format_validation(self):
        """Test basic markdown format validation."""
        with open(self.contributors_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Check for proper markdown formatting
        has_markdown_elements = False

        for line in lines:
            stripped = line.strip()
            # Check for markdown headers, lists, or links
            if (stripped.startswith('#') or
                stripped.startswith('-') or
                stripped.startswith('*') or
                '[' in stripped and ']' in stripped):
                has_markdown_elements = True
                break

        self.assertTrue(
            has_markdown_elements,
            "CONTRIBUTORS.md should contain proper markdown formatting"
        )

    def test_contributors_not_empty_after_header(self):
        """Test that there's content beyond just the header."""
        with open(self.contributors_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Remove empty lines and header lines
        content_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                content_lines.append(stripped)

        self.assertGreater(
            len(content_lines), 0,
            "CONTRIBUTORS.md should have content beyond headers"
        )

    def test_file_ends_with_newline(self):
        """Test that CONTRIBUTORS.md ends with a newline."""
        with open(self.contributors_path, 'rb') as f:
            content = f.read()

        self.assertTrue(
            content.endswith(b'\n'),
            "CONTRIBUTORS.md should end with a newline"
        )


if __name__ == '__main__':
    unittest.main()
