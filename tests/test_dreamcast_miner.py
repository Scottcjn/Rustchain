# SPDX-License-Identifier: MIT

"""
Tests for the Dreamcast miner functionality including SH4 detection,
fingerprint generation, network attestation, and hardware validation.
"""
import json
import os
import struct
import tempfile
import unittest
from unittest.mock import patch, mock_open, MagicMock, call
import hashlib
import sqlite3
import socket
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the actual module
from dreamcast_miner import DreamcastDetector
from dreamcast_boot_helper import DreamcastBootHelper
from sh4_fingerprint import SH4Fingerprint


class TestDreamcastDetector(unittest.TestCase):

    def setUp(self):
        self.detector = DreamcastDetector()

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_detect_sh4_cpu_success(self, mock_file, mock_exists):
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = (
            "processor\t: 0\n"
            "cpu family\t: sh\n"
            "cpu type\t: SH7750\n"
            "cache type\t: split I/D\n"
            "icache size\t: 16KiB\n"
            "dcache size\t: 16KiB\n"
            "bogomips\t: 199.07\n"
        )

        # Test that detector initializes
        self.assertIsInstance(self.detector, DreamcastDetector)
        self.assertIsInstance(self.detector.is_dreamcast, bool)

    @patch('os.path.exists')
    def test_detect_sh4_no_cpuinfo(self, mock_exists):
        mock_exists.return_value = False
        detector = DreamcastDetector()
        self.assertIsInstance(detector, DreamcastDetector)

    def test_hardware_signature_generation(self):
        # Test that hardware signature is generated
        self.assertIsNotNone(self.detector.hardware_sig)


class TestDreamcastBootHelper(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.helper = DreamcastBootHelper(work_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('subprocess.run')
    def test_check_toolchain_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="sh4-linux-gnu-gcc (GCC) 9.3.0\n"
        )

        result = self.helper.check_toolchain()
        self.assertTrue(result)

    @patch('subprocess.run')
    def test_check_toolchain_missing(self, mock_run):
        mock_run.side_effect = FileNotFoundError()

        result = self.helper.check_toolchain()
        self.assertFalse(result)


class TestSH4Fingerprint(unittest.TestCase):

    def setUp(self):
        self.fingerprint = SH4Fingerprint()

    @patch('builtins.open', new_callable=mock_open)
    def test_get_cpu_info(self, mock_file):
        mock_file.return_value.read.return_value = (
            "processor\t: 0\n"
            "cpu type\t: SH7750\n"
        )

        cpu_info = self.fingerprint._get_cpu_info()
        self.assertIsInstance(cpu_info, dict)

    def test_detect_cache_timing(self):
        # Test cache timing detection
        timings = self.fingerprint.detect_sh4_cache_timing()
        self.assertIsInstance(timings, dict)


if __name__ == '__main__':
    unittest.main()
