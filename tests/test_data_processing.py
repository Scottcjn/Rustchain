"""
Unit tests for src/utils/data_processing.py

Bounty: [ONBOARD: 5 RTC] Star + Write a Unit Test for Any Module
Issue: https://github.com/Scottcjn/rustchain-bounties/issues/2787
Author: alex (OpenClaw AI Agent)
Date: 2026-06-12
"""

import json
import unittest
import sys
from pathlib import Path

# Add src to path for importing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.data_processing import parse_json_input


class TestParseJsonInput(unittest.TestCase):
    """Test cases for parse_json_input function."""

    def test_parse_valid_json_object(self):
        """Should parse a valid JSON object string."""
        input_json = '{"name": "RustChain", "type": "DePIN"}'
        result = parse_json_input(input_json)
        self.assertEqual(result["name"], "RustChain")
        self.assertEqual(result["type"], "DePIN")

    def test_parse_valid_json_array(self):
        """Should parse a valid JSON array string."""
        input_json = '["PowerPC", "SPARC", "MIPS", "RISC-V"]'
        result = parse_json_input(input_json)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], "PowerPC")
        self.assertEqual(result[-1], "RISC-V")

    def test_parse_valid_json_string(self):
        """Should parse a valid JSON string."""
        input_json = '"Proof of Antiquity"'
        result = parse_json_input(input_json)
        self.assertEqual(result, "Proof of Antiquity")

    def test_parse_valid_json_number(self):
        """Should parse a valid JSON number."""
        input_json = "42"
        result = parse_json_input(input_json)
        self.assertEqual(result, 42)
        self.assertIsInstance(result, int)

    def test_parse_valid_json_boolean(self):
        """Should parse a valid JSON boolean."""
        input_json = "true"
        result = parse_json_input(input_json)
        self.assertTrue(result)

    def test_parse_valid_json_null(self):
        """Should parse JSON null."""
        input_json = "null"
        result = parse_json_input(input_json)
        self.assertIsNone(result)

    def test_parse_nested_json(self):
        """Should parse deeply nested JSON structures."""
        input_json = json.dumps({
            "chain": "RustChain",
            "consensus": {
                "type": "PoA",
                "layers": ["oscillator", "cache", "simd", "thermal"]
            },
            "architectures": ["PowerPC", "SPARC", "MIPS"]
        })
        result = parse_json_input(input_json)
        self.assertEqual(result["chain"], "RustChain")
        self.assertEqual(result["consensus"]["type"], "PoA")
        self.assertEqual(len(result["consensus"]["layers"]), 4)

    def test_invalid_json_raises_value_error(self):
        """Should raise ValueError for invalid JSON."""
        input_json = '{"invalid": json}'
        with self.assertRaises(ValueError) as context:
            parse_json_input(input_json)
        self.assertIn("Invalid JSON input", str(context.exception))

    def test_empty_string_raises_value_error(self):
        """Should raise ValueError for empty string."""
        with self.assertRaises(ValueError):
            parse_json_input("")

    def test_malformed_json_raises_value_error(self):
        """Should raise ValueError for malformed JSON."""
        test_cases = [
            '{"unclosed": "string}',
            "[1, 2,",
            "just_plain_text",
            "{}",  # Actually valid empty object, should pass
        ]
        for case in test_cases[:-1]:  # Skip the valid empty object
            with self.assertRaises(ValueError):
                parse_json_input(case)

    def test_parse_empty_object(self):
        """Should parse an empty JSON object."""
        result = parse_json_input("{}")
        self.assertEqual(result, {})

    def test_parse_empty_array(self):
        """Should parse an empty JSON array."""
        result = parse_json_input("[]")
        self.assertEqual(result, [])

    def test_unicode_content(self):
        """Should handle Unicode content correctly."""
        input_json = '{"message": "复古硬件", "emoji": "🖥️"}'
        result = parse_json_input(input_json)
        self.assertEqual(result["message"], "复古硬件")
        self.assertEqual(result["emoji"], "🖥️")


class TestEdgeCases(unittest.TestCase):
    """Edge case tests for data_processing module."""

    def test_whitespace_json(self):
        """Should handle JSON with leading/trailing whitespace."""
        input_json = '   {"key": "value"}   '
        result = parse_json_input(input_json)
        self.assertEqual(result["key"], "value")

    def test_large_json(self):
        """Should handle large JSON structures."""
        large_data = {
            "nodes": [{"id": i, "arch": "PowerPC"} for i in range(1000)]
        }
        input_json = json.dumps(large_data)
        result = parse_json_input(input_json)
        self.assertEqual(len(result["nodes"]), 1000)
        self.assertEqual(result["nodes"][999]["id"], 999)


if __name__ == "__main__":
    unittest.main()
