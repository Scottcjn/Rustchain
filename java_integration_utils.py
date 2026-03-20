# SPDX-License-Identifier: MIT

import sqlite3
import hashlib
import hmac
import time
import os
import json
import re
from typing import Dict, List, Optional, Tuple, Union
import secrets

DB_PATH = 'rustchain.db'

class JavaIntegrationUtils:
    """Utility functions for Java SDK integration and enterprise tooling."""

    def __init__(self):
        self.init_database()

    def init_database(self):
        """Initialize database tables for Java integration support."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS java_addresses (
                    address TEXT PRIMARY KEY,
                    public_key TEXT,
                    validation_status TEXT DEFAULT 'pending',
                    created_at INTEGER,
                    validated_at INTEGER
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS epoch_rewards (
                    epoch_id INTEGER,
                    validator_address TEXT,
                    base_reward REAL,
                    performance_bonus REAL,
                    total_reward REAL,
                    calculated_at INTEGER,
                    PRIMARY KEY (epoch_id, validator_address)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS hardware_fingerprints (
                    node_id TEXT PRIMARY KEY,
                    cpu_timing TEXT,
                    cache_metrics TEXT,
                    simd_features TEXT,
                    collected_at INTEGER,
                    signature TEXT
                )
            ''')

class AddressValidator:
    """RustChain address validation utilities for Java SDK."""

    @staticmethod
    def validate_rtc_address(address: str) -> Dict[str, Union[bool, str]]:
        """Validate RustChain address format and checksum."""
        if not address or len(address) != 42:
            return {'valid': False, 'error': 'Invalid address length'}

        if not address.startswith('rtc'):
            return {'valid': False, 'error': 'Address must start with rtc prefix'}

        hex_part = address[3:]
        if not re.match(r'^[a-fA-F0-9]{39}$', hex_part):
            return {'valid': False, 'error': 'Invalid hexadecimal format'}

        # Verify checksum (last 2 chars)
        payload = hex_part[:-2]
        expected_checksum = hashlib.sha256(payload.encode()).hexdigest()[:2]
        actual_checksum = hex_part[-2:]

        if expected_checksum.lower() != actual_checksum.lower():
            return {'valid': False, 'error': 'Invalid checksum'}

        return {'valid': True, 'address_type': 'standard'}

    @staticmethod
    def generate_rtc_address() -> Dict[str, str]:
        """Generate new RustChain address for Java wallet applications."""
        private_key = secrets.token_hex(32)

        # Simulate Ed25519 public key derivation
        public_key_hash = hashlib.sha256(private_key.encode()).hexdigest()
        payload = public_key_hash[:37]
        checksum = hashlib.sha256(payload.encode()).hexdigest()[:2]

        address = f"rtc{payload}{checksum}"

        return {
            'address': address,
            'private_key': private_key,
            'public_key': public_key_hash
        }

    def store_validated_address(self, address: str, public_key: str) -> bool:
        """Store validated address for Java SDK caching."""
        validation_result = self.validate_rtc_address(address)
        if not validation_result['valid']:
            return False

        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO java_addresses
                    (address, public_key, validation_status, created_at, validated_at)
                    VALUES (?, ?, 'valid', ?, ?)
                ''', (address, public_key, int(time.time()), int(time.time())))
            return True
        except sqlite3.Error:
            return False

class EpochRewardCalculator:
    """Calculate epoch rewards for validators - Java SDK integration."""

    BASE_REWARD_RTC = 5.0
    PERFORMANCE_MULTIPLIER = 1.5
    MAX_BONUS_PERCENTAGE = 0.25

    @staticmethod
    def calculate_validator_reward(validator_data: Dict) -> Dict[str, float]:
        """Calculate reward for validator based on performance metrics."""
        stake_amount = validator_data.get('stake_amount', 0)
        uptime_percentage = validator_data.get('uptime_percentage', 0.0)
        blocks_validated = validator_data.get('blocks_validated', 0)
        expected_blocks = validator_data.get('expected_blocks', 1)

        # Base reward calculation
        base_reward = EpochRewardCalculator.BASE_REWARD_RTC * min(stake_amount / 1000.0, 10.0)

        # Performance bonus
        performance_ratio = min(blocks_validated / expected_blocks, 1.0)
        uptime_bonus = uptime_percentage / 100.0

        performance_score = (performance_ratio * 0.7) + (uptime_bonus * 0.3)
        performance_bonus = base_reward * EpochRewardCalculator.MAX_BONUS_PERCENTAGE * performance_score

        total_reward = base_reward + performance_bonus

        return {
            'base_reward': round(base_reward, 6),
            'performance_bonus': round(performance_bonus, 6),
            'total_reward': round(total_reward, 6),
            'performance_score': round(performance_score, 4)
        }

    def store_epoch_rewards(self, epoch_id: int, rewards_data: List[Dict]) -> int:
        """Store calculated rewards for Java SDK historical queries."""
        stored_count = 0
        timestamp = int(time.time())

        try:
            with sqlite3.connect(DB_PATH) as conn:
                for reward_entry in rewards_data:
                    conn.execute('''
                        INSERT OR REPLACE INTO epoch_rewards
                        (epoch_id, validator_address, base_reward, performance_bonus, total_reward, calculated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        epoch_id,
                        reward_entry['validator_address'],
                        reward_entry['base_reward'],
                        reward_entry['performance_bonus'],
                        reward_entry['total_reward'],
                        timestamp
                    ))
                    stored_count += 1
        except sqlite3.Error:
            pass

        return stored_count

    def get_validator_rewards_history(self, validator_address: str, limit: int = 10) -> List[Dict]:
        """Get reward history for Java dashboard applications."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute('''
                    SELECT epoch_id, base_reward, performance_bonus, total_reward, calculated_at
                    FROM epoch_rewards
                    WHERE validator_address = ?
                    ORDER BY epoch_id DESC
                    LIMIT ?
                ''', (validator_address, limit))

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'epoch_id': row[0],
                        'base_reward': row[1],
                        'performance_bonus': row[2],
                        'total_reward': row[3],
                        'calculated_at': row[4]
                    })
                return results
        except sqlite3.Error:
            return []

class HardwareFingerprintCollector:
    """Collect hardware fingerprints for Java-based attestation protocol."""

    @staticmethod
    def collect_cpu_timing_metrics() -> Dict[str, Union[int, float]]:
        """Collect CPU timing data for hardware attestation."""
        start_time = time.perf_counter()

        # CPU-intensive operation for timing measurement
        test_value = 1
        for i in range(100000):
            test_value = (test_value * 31 + i) % 1000000007

        elapsed_ns = int((time.perf_counter() - start_time) * 1_000_000_000)

        return {
            'cpu_cycles_estimate': elapsed_ns,
            'operations_per_second': int(100000 / (elapsed_ns / 1_000_000_000)),
            'timing_variance': abs(elapsed_ns % 1000),
            'collected_at': int(time.time())
        }

    @staticmethod
    def collect_cache_metrics() -> Dict[str, int]:
        """Simulate cache performance metrics collection."""
        # Memory access patterns for cache behavior analysis
        test_data = bytearray(64 * 1024)  # 64KB test buffer

        start_time = time.perf_counter()
        for i in range(0, len(test_data), 64):  # Cache line jumps
            test_data[i] = (test_data[i] + 1) % 256
        sequential_time = time.perf_counter() - start_time

        start_time = time.perf_counter()
        for i in range(1000):  # Random access
            idx = (i * 7919) % len(test_data)  # Pseudo-random pattern
            test_data[idx] = (test_data[idx] + 1) % 256
        random_time = time.perf_counter() - start_time

        return {
            'sequential_access_ns': int(sequential_time * 1_000_000_000),
            'random_access_ns': int(random_time * 1_000_000_000),
            'cache_efficiency_ratio': int((sequential_time / random_time) * 1000),
            'test_buffer_size': len(test_data)
        }

    @staticmethod
    def detect_simd_capabilities() -> Dict[str, bool]:
        """Detect SIMD capabilities for JVM-based fingerprinting."""
        capabilities = {
            'sse2_available': True,  # Most modern x86_64
            'avx_available': False,
            'avx2_available': False,
            'neon_available': False  # ARM
        }

        # In real implementation, this would use JNI calls
        # For now, simulate based on platform detection
        import platform
        arch = platform.machine().lower()

        if 'x86' in arch or 'amd64' in arch:
            capabilities['avx_available'] = True
            if '64' in arch:
                capabilities['avx2_available'] = True
        elif 'arm' in arch or 'aarch' in arch:
            capabilities['neon_available'] = True

        return capabilities

    def generate_hardware_fingerprint(self, node_id: str) -> Dict[str, str]:
        """Generate complete hardware fingerprint for Java attestation client."""
        cpu_metrics = self.collect_cpu_timing_metrics()
        cache_metrics = self.collect_cache_metrics()
        simd_caps = self.detect_simd_capabilities()

        fingerprint_data = {
            'node_id': node_id,
            'cpu_timing': json.dumps(cpu_metrics),
            'cache_metrics': json.dumps(cache_metrics),
            'simd_features': json.dumps(simd_caps),
            'timestamp': int(time.time())
        }

        # Create signature for integrity verification
        fingerprint_str = f"{node_id}:{cpu_metrics}:{cache_metrics}:{simd_caps}"
        signature = hashlib.sha256(fingerprint_str.encode()).hexdigest()

        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO hardware_fingerprints
                    (node_id, cpu_timing, cache_metrics, simd_features, collected_at, signature)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    node_id,
                    fingerprint_data['cpu_timing'],
                    fingerprint_data['cache_metrics'],
                    fingerprint_data['simd_features'],
                    fingerprint_data['timestamp'],
                    signature
                ))
        except sqlite3.Error:
            pass

        return {
            'node_id': node_id,
            'fingerprint_hash': signature,
            'collection_timestamp': str(fingerprint_data['timestamp'])
        }

# Convenience functions for Java SDK integration
def validate_address(address: str) -> bool:
    """Quick address validation for Java applications."""
    validator = AddressValidator()
    result = validator.validate_rtc_address(address)
    return result['valid']

def calculate_epoch_reward(validator_data: Dict) -> float:
    """Quick reward calculation for Java tools."""
    calculator = EpochRewardCalculator()
    result = calculator.calculate_validator_reward(validator_data)
    return result['total_reward']

def collect_node_fingerprint(node_id: str) -> str:
    """Quick fingerprint collection for Java attestation."""
    collector = HardwareFingerprintCollector()
    result = collector.generate_hardware_fingerprint(node_id)
    return result['fingerprint_hash']
