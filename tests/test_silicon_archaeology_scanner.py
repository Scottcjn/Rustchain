# SPDX-License-Identifier: MIT

import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import platform
import sys
import os


class TestSiliconArchaeologyScanner(unittest.TestCase):

    def setUp(self):
        # Mock the scanner module import
        self.mock_scanner = MagicMock()
        sys.modules['silicon_archaeology.scanner'] = self.mock_scanner
        from silicon_archaeology.scanner import detect_cpu, classify_epoch, scan_hardware

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

        from silicon_archaeology.scanner import detect_cpu
        result = detect_cpu()

        self.assertIsNotNone(result)
        self.assertIn('family', result)
        self.assertIn('model', result)
        self.assertEqual(result['family'], 'Intel')
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

        from silicon_archaeology.scanner import detect_cpu
        result = detect_cpu()

        self.assertIsNotNone(result)
        self.assertEqual(result['family'], 'AMD')
        self.assertIn('Ryzen', result['model'])

    def test_epoch_classification_vintage(self):
        from silicon_archaeology.scanner import classify_epoch

        # Test various CPU configurations
        test_cases = [
            ('Intel', '486', 0, 1991),
            ('Intel', 'Pentium', 1, 1995),
            ('Intel', 'Pentium II', 2, 1999),
            ('Intel', 'Core 2 Duo', 3, 2008),
            ('Intel', 'Core i7-8550U', 4, 2018),
            ('AMD', 'K6', 1, 1997),
            ('PowerPC', 'G4', 2, 2001)
        ]

        for family, model, expected_epoch, expected_year in test_cases:
            with self.subTest(family=family, model=model):
                result = classify_epoch(family, model)
                self.assertEqual(result['epoch'], expected_epoch)
                self.assertGreaterEqual(result['year_estimate'], expected_year - 2)
                self.assertLessEqual(result['year_estimate'], expected_year + 2)

    def test_json_output_validation(self):
        from silicon_archaeology.scanner import scan_hardware

        with patch('silicon_archaeology.scanner.detect_cpu') as mock_detect:
            mock_detect.return_value = {
                'family': 'Intel',
                'model': 'Core i5-4570',
                'raw_data': {'cpu_family': 6, 'model': 60}
            }

            result = scan_hardware()

            # Verify JSON structure
            self.assertIsInstance(result, dict)
            required_keys = ['family', 'model', 'epoch', 'year_estimate', 'rustchain_multiplier']
            for key in required_keys:
                self.assertIn(key, result)

            # Verify data types
            self.assertIsInstance(result['family'], str)
            self.assertIsInstance(result['model'], str)
            self.assertIsInstance(result['epoch'], int)
            self.assertIsInstance(result['year_estimate'], int)
            self.assertIsInstance(result['rustchain_multiplier'], (int, float))

            # Verify value ranges
            self.assertGreaterEqual(result['epoch'], 0)
            self.assertLessEqual(result['epoch'], 4)
            self.assertGreater(result['rustchain_multiplier'], 0)

    @patch('platform.system')
    @patch('subprocess.check_output')
    @patch('os.path.exists')
    def test_cross_platform_compatibility(self, mock_exists, mock_subprocess, mock_system):
        from silicon_archaeology.scanner import detect_cpu

        # Test macOS detection
        mock_system.return_value = 'Darwin'
        mock_exists.return_value = False
        mock_subprocess.return_value = b'machdep.cpu.brand_string: Intel(R) Core(TM) i9-9880H CPU @ 2.30GHz\n'

        result = detect_cpu()
        self.assertIsNotNone(result)

        # Test PowerPC scenario
        mock_system.return_value = 'Linux'
        mock_exists.return_value = True

        with patch('builtins.open', mock_open(read_data="""processor	: 0
cpu		: POWER8 (architected), altivec supported
clock		: 3425.000000MHz
revision	: 2.1 (pvr 004d 0201)
""")) as mock_file:
            result = detect_cpu()
            self.assertIsNotNone(result)

    @patch('os.path.exists')
    def test_error_handling_no_proc_cpuinfo(self, mock_exists):
        mock_exists.return_value = False

        with patch('platform.system', return_value='Linux'):
            from silicon_archaeology.scanner import detect_cpu

            # Should fallback gracefully when /proc/cpuinfo doesn't exist
            result = detect_cpu()
            self.assertIsNotNone(result)
            self.assertIn('family', result)

    @patch('builtins.open')
    def test_error_handling_corrupted_cpuinfo(self, mock_file):
        mock_file.side_effect = IOError("Permission denied")

        from silicon_archaeology.scanner import detect_cpu
        result = detect_cpu()

        # Should return fallback data on read error
        self.assertIsNotNone(result)
        self.assertIn('family', result)

    def test_rustchain_multiplier_calculation(self):
        from silicon_archaeology.scanner import classify_epoch

        # Test that older hardware gets higher multipliers
        modern_result = classify_epoch('Intel', 'Core i7-10700K')
        vintage_result = classify_epoch('Intel', '486DX')

        self.assertGreater(vintage_result['rustchain_multiplier'],
                          modern_result['rustchain_multiplier'])

        # Verify multiplier is reasonable (between 1x and 50x)
        self.assertGreaterEqual(modern_result['rustchain_multiplier'], 1.0)
        self.assertLessEqual(vintage_result['rustchain_multiplier'], 50.0)

    def test_unknown_hardware_handling(self):
        from silicon_archaeology.scanner import classify_epoch

        # Test with completely unknown hardware
        result = classify_epoch('UnknownVendor', 'Mystery CPU X1000')

        self.assertIsNotNone(result)
        self.assertIn('epoch', result)
        self.assertIn('rustchain_multiplier', result)
        # Unknown hardware should get conservative estimates
        self.assertGreaterEqual(result['epoch'], 0)
        self.assertLessEqual(result['epoch'], 4)

    @patch('json.dumps')
    def test_json_serialization_safety(self, mock_dumps):
        from silicon_archaeology.scanner import scan_hardware

        # Mock json.dumps to raise an exception
        mock_dumps.side_effect = TypeError("Object not serializable")

        with patch('silicon_archaeology.scanner.detect_cpu') as mock_detect:
            mock_detect.return_value = {
                'family': 'Intel',
                'model': 'Test CPU',
                'raw_data': {'test': 'data'}
            }

            # Should handle JSON serialization errors gracefully
            try:
                result = scan_hardware()
                # If it doesn't raise, verify it returns valid data
                self.assertIsInstance(result, dict)
            except TypeError:
                # Or it should raise the expected error
                pass


if __name__ == '__main__':
    unittest.main()
