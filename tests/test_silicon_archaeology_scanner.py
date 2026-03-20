# SPDX-License-Identifier: MIT

import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import platform
import sys
import os

# Add the root directory to sys.path to import the scanner module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from silicon_archaeology_scanner import SiliconArchaeologyScanner


class TestSiliconArchaeologyScanner(unittest.TestCase):

    def setUp(self):
        self.scanner = SiliconArchaeologyScanner()

    @patch('builtins.open', new_callable=mock_open, read_data="""processor	: 0
vendor_id	: GenuineIntel
cpu family	: 6
model		: 142
model name	: Intel(R) Core(TM) i7-8550U CPU @ 1.80GHz
stepping	: 10
microcode	: 0xf0
cpu MHz		: 1800.000
cache size	: 8192 KB
""")
    @patch('os.path.exists')
    def test_cpu_detection_intel_modern(self, mock_exists, mock_file):
        mock_exists.return_value = True

        result = self.scanner._parse_proc_cpuinfo()

        self.assertIsNotNone(result)
        self.assertIn('vendor', result)
        self.assertIn('model', result)
        mock_file.assert_called_once_with('/proc/cpuinfo', 'r')

    @patch('builtins.open', new_callable=mock_open, read_data="""processor	: 0
vendor_id	: AuthenticAMD
cpu family	: 23
model		: 113
model name	: AMD Ryzen 9 3900X 12-Core Processor
stepping	: 0
microcode	: 0x8701021
cpu MHz		: 3800.000
cache size	: 512 KB
""")
    @patch('os.path.exists')
    def test_cpu_detection_amd_zen(self, mock_exists, mock_file):
        mock_exists.return_value = True

        result = self.scanner._parse_proc_cpuinfo()

        self.assertIsNotNone(result)
        self.assertIn('vendor', result)
        self.assertIn('model', result)

    def test_epoch_classification_vintage(self):
        # Test various CPU configurations
        test_cases = [
            ({'model': '8080'}, 0),
            ({'model': 'pentium'}, 3),
            ({'model': 'core i7'}, 4)
        ]

        for cpu_info, expected_epoch in test_cases:
            classified = self.scanner._classify_hardware(cpu_info)
            self.assertIn('epoch', classified)

    def test_scanner_initialization(self):
        """Test that scanner initializes correctly"""
        scanner = SiliconArchaeologyScanner()
        self.assertIsNotNone(scanner.system)
        self.assertIsNotNone(scanner.machine)
        self.assertIn(scanner.system, ['linux', 'darwin', 'windows'])

    def test_epoch_table_structure(self):
        """Test that EPOCH_TABLE has correct structure"""
        for epoch, data in SiliconArchaeologyScanner.EPOCH_TABLE.items():
            self.assertIn('families', data)
            self.assertIn('year_range', data)
            self.assertIn('multiplier', data)
            self.assertIsInstance(data['families'], list)
            self.assertIsInstance(data['year_range'], tuple)
            self.assertEqual(len(data['year_range']), 2)

    @patch('platform.system')
    @patch('platform.machine')
    def test_platform_fallback(self, mock_machine, mock_system):
        """Test platform detection fallback"""
        mock_system.return_value = 'Unknown'
        mock_machine.return_value = 'x86_64'

        scanner = SiliconArchaeologyScanner()
        result = scanner._parse_platform_fallback()

        self.assertIsInstance(result, dict)
        self.assertIn('vendor', result)
        self.assertIn('model', result)


if __name__ == '__main__':
    unittest.main()
