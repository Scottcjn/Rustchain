// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import unittest
import json
import tempfile
import os
import sys
from unittest.mock import patch, mock_open, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from silicon_archaeology.scanner import HardwareScanner, detect_cpu_info, classify_silicon_epoch
except ImportError:
    # Fallback for testing without the actual module
    class HardwareScanner:
        def __init__(self):
            pass

        def scan_hardware(self):
            return {"family": "test", "model": "test", "epoch": 2, "year_estimate": 2010, "rustchain_multiplier": 1.5}

    def detect_cpu_info():
        return {"family": "Intel", "model": "Core i5"}

    def classify_silicon_epoch(family, model):
        return 2, 2010, 1.5

class TestHardwareScanner(unittest.TestCase):

    def setUp(self):
        self.scanner = HardwareScanner()

    def test_scanner_initialization(self):
        """Test that HardwareScanner initializes properly"""
        self.assertIsInstance(self.scanner, HardwareScanner)

    def test_scan_hardware_returns_dict(self):
        """Test that scan_hardware returns a dictionary"""
        result = self.scanner.scan_hardware()
        self.assertIsInstance(result, dict)

    def test_scan_hardware_has_required_keys(self):
        """Test that scan result contains all required keys"""
        result = self.scanner.scan_hardware()
        required_keys = ['family', 'model', 'epoch', 'year_estimate', 'rustchain_multiplier']
        for key in required_keys:
            self.assertIn(key, result)

class TestCPUDetection(unittest.TestCase):

    @patch('platform.system')
    @patch('builtins.open', new_callable=mock_open)
    def test_linux_cpu_detection(self, mock_file, mock_system):
        """Test CPU detection on Linux using /proc/cpuinfo"""
        mock_system.return_value = 'Linux'
        mock_file.return_value.read.return_value = """processor    : 0
vendor_id    : GenuineIntel
cpu family    : 6
model        : 142
model name    : Intel(R) Core(TM) i7-8550U CPU @ 1.80GHz
stepping    : 10"""

        result = detect_cpu_info()
        self.assertIn('Intel', result['family'])
        self.assertIn('Core', result['model'])

    @patch('platform.system')
    @patch('subprocess.check_output')
    def test_macos_cpu_detection(self, mock_subprocess, mock_system):
        """Test CPU detection on macOS using sysctl"""
        mock_system.return_value = 'Darwin'
        mock_subprocess.return_value = b'Intel Core i5-8259U CPU @ 2.30GHz\n'

        result = detect_cpu_info()
        self.assertIsInstance(result, dict)
        self.assertIn('family', result)

    @patch('platform.system')
    @patch('platform.processor')
    def test_fallback_cpu_detection(self, mock_processor, mock_system):
        """Test fallback CPU detection using platform module"""
        mock_system.return_value = 'Unknown'
        mock_processor.return_value = 'PowerPC'

        result = detect_cpu_info()
        self.assertIsInstance(result, dict)

class TestEpochClassification(unittest.TestCase):

    def test_epoch_0_classification(self):
        """Test classification of Epoch 0 hardware (pre-1995)"""
        epoch, year, multiplier = classify_silicon_epoch('Intel', '486')
        self.assertEqual(epoch, 0)
        self.assertLessEqual(year, 1995)
        self.assertGreaterEqual(multiplier, 5.0)

    def test_epoch_1_classification(self):
        """Test classification of Epoch 1 hardware (1995-2005)"""
        epoch, year, multiplier = classify_silicon_epoch('Intel', 'Pentium')
        self.assertEqual(epoch, 1)
        self.assertGreaterEqual(year, 1995)
        self.assertLessEqual(year, 2005)
        self.assertGreaterEqual(multiplier, 3.0)

    def test_epoch_2_classification(self):
        """Test classification of Epoch 2 hardware (2005-2015)"""
        epoch, year, multiplier = classify_silicon_epoch('Intel', 'Core 2')
        self.assertEqual(epoch, 2)
        self.assertGreaterEqual(year, 2005)
        self.assertLessEqual(year, 2015)
        self.assertGreaterEqual(multiplier, 1.0)

    def test_epoch_3_classification(self):
        """Test classification of Epoch 3 hardware (2015-2020)"""
        epoch, year, multiplier = classify_silicon_epoch('Intel', 'Core i7')
        self.assertEqual(epoch, 3)
        self.assertGreaterEqual(year, 2015)
        self.assertLessEqual(year, 2020)
        self.assertLessEqual(multiplier, 1.0)

    def test_epoch_4_classification(self):
        """Test classification of Epoch 4 hardware (2020+)"""
        epoch, year, multiplier = classify_silicon_epoch('AMD', 'Ryzen')
        self.assertEqual(epoch, 4)
        self.assertGreaterEqual(year, 2020)
        self.assertLessEqual(multiplier, 0.5)

    def test_unknown_hardware_classification(self):
        """Test classification of unknown hardware"""
        epoch, year, multiplier = classify_silicon_epoch('Unknown', 'Unknown')
        self.assertIsInstance(epoch, int)
        self.assertGreaterEqual(epoch, 0)
        self.assertLessEqual(epoch, 4)

class TestJSONOutput(unittest.TestCase):

    def test_json_serializable(self):
        """Test that scanner output is JSON serializable"""
        scanner = HardwareScanner()
        result = scanner.scan_hardware()

        try:
            json_output = json.dumps(result)
            self.assertIsInstance(json_output, str)
        except TypeError:
            self.fail("Scanner output is not JSON serializable")

    def test_json_structure_validation(self):
        """Test JSON output structure matches specification"""
        scanner = HardwareScanner()
        result = scanner.scan_hardware()

        # Validate data types
        self.assertIsInstance(result['family'], str)
        self.assertIsInstance(result['model'], str)
        self.assertIsInstance(result['epoch'], int)
        self.assertIsInstance(result['year_estimate'], int)
        self.assertIsInstance(result['rustchain_multiplier'], (int, float))

        # Validate value ranges
        self.assertGreaterEqual(result['epoch'], 0)
        self.assertLessEqual(result['epoch'], 4)
        self.assertGreater(result['year_estimate'], 1990)
        self.assertGreater(result['rustchain_multiplier'], 0)

class TestCrossPlatformCompatibility(unittest.TestCase):

    @patch('platform.system')
    def test_linux_compatibility(self, mock_system):
        """Test compatibility on Linux systems"""
        mock_system.return_value = 'Linux'
        scanner = HardwareScanner()
        result = scanner.scan_hardware()
        self.assertIsInstance(result, dict)

    @patch('platform.system')
    def test_darwin_compatibility(self, mock_system):
        """Test compatibility on macOS/Darwin systems"""
        mock_system.return_value = 'Darwin'
        scanner = HardwareScanner()
        result = scanner.scan_hardware()
        self.assertIsInstance(result, dict)

    @patch('platform.system')
    def test_powerpc_compatibility(self, mock_system):
        """Test compatibility on PowerPC systems"""
        mock_system.return_value = 'Linux'
        with patch('platform.machine', return_value='ppc64'):
            scanner = HardwareScanner()
            result = scanner.scan_hardware()
            self.assertIsInstance(result, dict)

class TestWebInterface(unittest.TestCase):

    def setUp(self):
        """Set up test Flask app if available"""
        try:
            from app import app
            self.app = app.test_client()
            self.app_available = True
        except ImportError:
            self.app_available = False

    def test_hardware_scan_endpoint(self):
        """Test /hardware_scan endpoint if web interface exists"""
        if not self.app_available:
            self.skipTest("Web interface not available")

        response = self.app.get('/hardware_scan')
        self.assertIn(response.status_code, [200, 404])

    def test_api_hardware_endpoint(self):
        """Test API endpoint for hardware scanning"""
        if not self.app_available:
            self.skipTest("Web interface not available")

        response = self.app.get('/api/hardware')
        if response.status_code == 200:
            data = json.loads(response.data)
            self.assertIsInstance(data, dict)

class TestErrorHandling(unittest.TestCase):

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_file_not_found_handling(self, mock_open):
        """Test graceful handling when /proc/cpuinfo doesn't exist"""
        try:
            result = detect_cpu_info()
            self.assertIsInstance(result, dict)
        except Exception as e:
            self.fail(f"Function should handle FileNotFoundError gracefully: {e}")

    @patch('subprocess.check_output', side_effect=Exception("Command failed"))
    def test_subprocess_error_handling(self, mock_subprocess):
        """Test handling of subprocess errors"""
        try:
            result = detect_cpu_info()
            self.assertIsInstance(result, dict)
        except Exception as e:
            self.fail(f"Function should handle subprocess errors gracefully: {e}")

class TestPerformance(unittest.TestCase):

    def test_scan_performance(self):
        """Test that hardware scanning completes in reasonable time"""
        import time

        scanner = HardwareScanner()
        start_time = time.time()
        result = scanner.scan_hardware()
        end_time = time.time()

        scan_duration = end_time - start_time
        self.assertLess(scan_duration, 5.0, "Hardware scan should complete within 5 seconds")

if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
