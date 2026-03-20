// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import pytest
import tempfile
import os
import sys
import sqlite3
from pathlib import Path

# Add the project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

@pytest.fixture
def temp_db():
    """Provide a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)

@pytest.fixture
def temp_data_dir():
    """Provide temporary data directory for clawrtc operations"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def mock_wallet_data():
    """Mock wallet data for testing"""
    return {
        'address': 'RTC1abc123def456ghi789',
        'private_key': '0123456789abcdef' * 4,
        'public_key': 'abcdef0123456789' * 4,
        'balance': 1000.0
    }

@pytest.fixture
def mock_miner_data():
    """Mock miner attestation data"""
    return {
        'miner_id': 'miner_001',
        'hardware_hash': 'hw_abc123def456',
        'attestation_proof': 'proof_xyz789',
        'timestamp': 1640995200,
        'difficulty': 10000
    }

@pytest.fixture
def mock_hardware_fingerprint():
    """Mock hardware fingerprint for testing"""
    return {
        'cpu_info': 'Intel Core i7-9700K',
        'gpu_info': 'NVIDIA GeForce RTX 3070',
        'memory_total': 16384,
        'disk_serial': 'SSD123456789',
        'network_mac': '00:11:22:33:44:55',
        'fingerprint_hash': 'fp_abc123def456ghi789'
    }

@pytest.fixture(autouse=True)
def setup_test_environment(temp_data_dir, monkeypatch):
    """Setup test environment variables and paths"""
    monkeypatch.setenv('CLAWRTC_DATA_DIR', temp_data_dir)
    monkeypatch.setenv('CLAWRTC_TEST_MODE', '1')

    # Ensure data directory exists
    os.makedirs(temp_data_dir, exist_ok=True)

@pytest.fixture
def sample_blockchain_data():
    """Sample blockchain data for integration tests"""
    return [
        {
            'block_height': 1,
            'block_hash': 'block_hash_001',
            'prev_hash': '0' * 64,
            'merkle_root': 'merkle_001',
            'timestamp': 1640995200,
            'difficulty': 1000,
            'nonce': 12345
        },
        {
            'block_height': 2,
            'block_hash': 'block_hash_002',
            'prev_hash': 'block_hash_001',
            'merkle_root': 'merkle_002',
            'timestamp': 1640995260,
            'difficulty': 1100,
            'nonce': 67890
        }
    ]

@pytest.fixture
def initialized_db(temp_db):
    """Database with initialized schema"""
    with sqlite3.connect(temp_db) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                address TEXT PRIMARY KEY,
                private_key TEXT NOT NULL,
                public_key TEXT NOT NULL,
                balance REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS miners (
                id TEXT PRIMARY KEY,
                hardware_hash TEXT NOT NULL,
                attestation_proof TEXT,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                txid TEXT PRIMARY KEY,
                from_address TEXT,
                to_address TEXT,
                amount REAL NOT NULL,
                fee REAL DEFAULT 0.0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                block_height INTEGER
            )
        ''')

        conn.commit()

    return temp_db

# Test configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )

def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on their location/name"""
    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        if "test_e2e" in item.name or "end_to_end" in item.nodeid:
            item.add_marker(pytest.mark.slow)
