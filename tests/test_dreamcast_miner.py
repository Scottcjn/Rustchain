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

# Mock the dreamcast_miner module before importing
import sys
from unittest.mock import MagicMock
sys.modules['dreamcast_miner'] = MagicMock()

# Import after mocking
from dreamcast_miner import (
    DreamcastMiner, SH4Detector, FingerprintGenerator,
    NetworkAttestor, HardwareValidator, BootHelper
)


class TestSH4Detector(unittest.TestCase):

    def setUp(self):
        self.detector = SH4Detector()

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

        result = self.detector.detect_sh4_cpu()
        self.assertTrue(result['is_sh4'])
        self.assertEqual(result['cpu_type'], 'SH7750')
        self.assertEqual(result['icache_size'], '16KiB')

    @patch('os.path.exists')
    def test_detect_sh4_no_cpuinfo(self, mock_exists):
        mock_exists.return_value = False
        result = self.detector.detect_sh4_cpu()
        self.assertFalse(result['is_sh4'])
        self.assertIn('error', result)

    @patch('subprocess.run')
    def test_detect_dreamcast_hardware(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Dreamcast\nSH7750\nBroadBandAdapter"
        )

        result = self.detector.detect_dreamcast_hardware()
        self.assertTrue(result['is_dreamcast'])
        self.assertEqual(result['board'], 'Dreamcast')

    @patch('subprocess.run')
    def test_detect_cache_timing(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="L1-dcache-load-misses: 12345\nL1-icache-load-misses: 67890"
        )

        timing = self.detector.detect_cache_timing()
        self.assertIn('dcache_misses', timing)
        self.assertIn('icache_misses', timing)


class TestFingerprintGenerator(unittest.TestCase):

    def setUp(self):
        self.generator = FingerprintGenerator()

    @patch('time.time')
    @patch('os.urandom')
    def test_generate_fpu_jitter_fingerprint(self, mock_urandom, mock_time):
        mock_urandom.return_value = b'randomseed1234567890'
        mock_time.side_effect = [1000.123456789, 1000.123456801]

        fingerprint = self.generator.generate_fpu_jitter_fingerprint()
        self.assertIn('jitter_ns', fingerprint)
        self.assertIn('fpu_hash', fingerprint)
        self.assertEqual(len(fingerprint['fpu_hash']), 64)

    @patch('struct.pack')
    def test_generate_cache_fingerprint(self, mock_pack):
        cache_stats = {
            'dcache_misses': 12345,
            'icache_misses': 67890,
            'timing_variance': 0.00012
        }
        mock_pack.return_value = b'packed_cache_data'

        fingerprint = self.generator.generate_cache_fingerprint(cache_stats)
        self.assertIn('cache_hash', fingerprint)
        self.assertIn('timing_signature', fingerprint)

    def test_generate_memory_layout_fingerprint(self):
        with patch('builtins.open', mock_open(read_data="29000000-29800000 r-xp dreamcast_mem\n")):
            fingerprint = self.generator.generate_memory_layout_fingerprint()
            self.assertIn('memory_hash', fingerprint)
            self.assertIn('layout_signature', fingerprint)

    def test_combine_fingerprints(self):
        fp1 = {'type': 'fpu', 'hash': 'abc123'}
        fp2 = {'type': 'cache', 'hash': 'def456'}

        combined = self.generator.combine_fingerprints([fp1, fp2])
        self.assertIn('combined_hash', combined)
        self.assertIn('component_count', combined)
        self.assertEqual(combined['component_count'], 2)


class TestNetworkAttestor(unittest.TestCase):

    def setUp(self):
        self.attestor = NetworkAttestor()

    @patch('socket.socket')
    def test_discover_broadband_adapter(self, mock_socket):
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.recv.return_value = b'BBA_RESPONSE_DREAMCAST'

        result = self.attestor.discover_broadband_adapter()
        self.assertTrue(result['found'])
        self.assertEqual(result['adapter_type'], 'BroadBandAdapter')

    @patch('requests.post')
    def test_submit_attestation_success(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'attestation_id': 'att_12345', 'multiplier': 3.0}
        )

        fingerprint = {'combined_hash': 'abc123', 'component_count': 3}
        result = self.attestor.submit_attestation(fingerprint)

        self.assertTrue(result['success'])
        self.assertEqual(result['multiplier'], 3.0)

    @patch('requests.post')
    def test_submit_attestation_failure(self, mock_post):
        mock_post.side_effect = Exception("Network error")

        fingerprint = {'combined_hash': 'def456'}
        result = self.attestor.submit_attestation(fingerprint)

        self.assertFalse(result['success'])
        self.assertIn('error', result)


class TestHardwareValidator(unittest.TestCase):

    def setUp(self):
        self.validator = HardwareValidator()

    def test_validate_sh4_requirements(self):
        hw_info = {
            'cpu_type': 'SH7750',
            'icache_size': '16KiB',
            'dcache_size': '16KiB',
            'fpu_present': True
        }

        result = self.validator.validate_sh4_requirements(hw_info)
        self.assertTrue(result['valid'])
        self.assertEqual(result['multiplier'], 3.0)

    def test_validate_sh4_requirements_invalid(self):
        hw_info = {
            'cpu_type': 'x86_64',
            'icache_size': '32KiB'
        }

        result = self.validator.validate_sh4_requirements(hw_info)
        self.assertFalse(result['valid'])
        self.assertIn('reason', result)

    def test_validate_memory_constraints(self):
        memory_info = {'total_mb': 16, 'available_mb': 12}

        result = self.validator.validate_memory_constraints(memory_info)
        self.assertTrue(result['sufficient'])

    def test_validate_network_capability(self):
        network_info = {
            'adapter_present': True,
            'adapter_type': 'BroadBandAdapter',
            'link_speed': '10Mbps'
        }

        result = self.validator.validate_network_capability(network_info)
        self.assertTrue(result['capable'])


class TestBootHelper(unittest.TestCase):

    def setUp(self):
        self.helper = BootHelper()

    @patch('os.path.exists')
    def test_detect_boot_method(self, mock_exists):
        mock_exists.side_effect = lambda path: '/dev/gdemu' in path

        boot_method = self.helper.detect_boot_method()
        self.assertEqual(boot_method, 'GDEMU')

    @patch('subprocess.run')
    def test_prepare_mining_environment(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        result = self.helper.prepare_mining_environment()
        self.assertTrue(result['prepared'])
        self.assertIn('log_path', result)

    def test_generate_boot_script(self):
        config = {'miner_port': 8080, 'network_interface': 'bba0'}

        script = self.helper.generate_boot_script(config)
        self.assertIn('#!/bin/sh', script)
        self.assertIn('8080', script)
        self.assertIn('bba0', script)


class TestDreamcastMiner(unittest.TestCase):

    def setUp(self):
        self.miner = DreamcastMiner()

    @patch('dreamcast_miner.SH4Detector')
    @patch('dreamcast_miner.FingerprintGenerator')
    def test_initialize_miner(self, mock_fp_gen, mock_detector):
        mock_detector.return_value.detect_sh4_cpu.return_value = {'is_sh4': True}
        mock_fp_gen.return_value.generate_fpu_jitter_fingerprint.return_value = {'hash': 'test'}

        result = self.miner.initialize()
        self.assertTrue(result['initialized'])

    @patch('dreamcast_miner.NetworkAttestor')
    def test_start_mining_loop(self, mock_attestor):
        mock_attestor.return_value.submit_attestation.return_value = {
            'success': True, 'multiplier': 3.0
        }

        with patch.object(self.miner, '_mining_active', True):
            with patch('time.sleep'):
                result = self.miner.start_mining_loop()
                self.assertTrue(result['started'])

    @patch('sqlite3.connect')
    def test_log_mining_stats(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn

        stats = {'blocks_mined': 5, 'rtc_earned': 15.0, 'multiplier': 3.0}
        self.miner.log_mining_stats(stats)

        mock_conn.execute.assert_called()

    def test_calculate_sh4_hash_rate(self):
        # Test with typical Dreamcast specs
        cpu_freq_mhz = 200
        cache_efficiency = 0.85

        hash_rate = self.miner.calculate_sh4_hash_rate(cpu_freq_mhz, cache_efficiency)
        self.assertGreater(hash_rate, 0)
        self.assertLess(hash_rate, 1000)  # Reasonable upper bound

    @patch('os.system')
    def test_optimize_for_mining(self, mock_system):
        mock_system.return_value = 0

        result = self.miner.optimize_for_mining()
        self.assertTrue(result['optimized'])
        mock_system.assert_called()


class TestDreamcastMinerIntegration(unittest.TestCase):

    def setUp(self):
        self.test_db = tempfile.mktemp(suffix='.db')
        with sqlite3.connect(self.test_db) as conn:
            conn.execute('''CREATE TABLE mining_stats
                           (timestamp INTEGER, blocks_mined INTEGER,
                            rtc_earned REAL, multiplier REAL)''')

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.unlink(self.test_db)

    @patch('dreamcast_miner.SH4Detector')
    @patch('dreamcast_miner.FingerprintGenerator')
    @patch('dreamcast_miner.NetworkAttestor')
    def test_full_mining_cycle(self, mock_attestor, mock_fp_gen, mock_detector):
        mock_detector.return_value.detect_sh4_cpu.return_value = {
            'is_sh4': True, 'cpu_type': 'SH7750'
        }
        mock_fp_gen.return_value.combine_fingerprints.return_value = {
            'combined_hash': 'test_hash_123'
        }
        mock_attestor.return_value.submit_attestation.return_value = {
            'success': True, 'multiplier': 3.0, 'attestation_id': 'att_123'
        }

        miner = DreamcastMiner(db_path=self.test_db)

        # Initialize
        init_result = miner.initialize()
        self.assertTrue(init_result['initialized'])

        # Mock mining cycle
        with patch.object(miner, '_mining_active', False):  # Run once
            mining_result = miner.start_mining_loop()
            self.assertTrue(mining_result['started'])

    def test_database_logging(self):
        miner = DreamcastMiner(db_path=self.test_db)

        stats = {
            'blocks_mined': 3,
            'rtc_earned': 9.0,
            'multiplier': 3.0,
            'timestamp': 1609459200
        }

        miner.log_mining_stats(stats)

        with sqlite3.connect(self.test_db) as conn:
            cursor = conn.execute("SELECT * FROM mining_stats")
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[1], 3)  # blocks_mined
            self.assertEqual(row[2], 9.0)  # rtc_earned


if __name__ == '__main__':
    unittest.main()
