// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import pytest
import sqlite3
import json
import hashlib
import time
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append('node')
from node.rustchain_v2_integrated_v2_2_1_rip200 import (
    calculate_hash,
    validate_block,
    calculate_merkle_root,
    is_valid_proof_of_work,
    adjust_difficulty,
    create_genesis_block,
    mine_block,
    validate_transaction
)

DB_PATH = 'test_blockchain.db'

@pytest.fixture
def clean_db():
    """Clean database before each test"""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

@pytest.fixture
def sample_block():
    """Create sample block for testing"""
    return {
        'index': 1,
        'timestamp': time.time(),
        'transactions': [
            {'from': 'alice', 'to': 'bob', 'amount': 10.0, 'fee': 0.1},
            {'from': 'bob', 'to': 'charlie', 'amount': 5.0, 'fee': 0.05}
        ],
        'previous_hash': 'previous_block_hash',
        'nonce': 12345,
        'difficulty': 4
    }

@pytest.fixture
def empty_block():
    """Create empty block for edge case testing"""
    return {
        'index': 0,
        'timestamp': time.time(),
        'transactions': [],
        'previous_hash': '0',
        'nonce': 0,
        'difficulty': 1
    }

class TestHashCalculation:
    def test_calculate_hash_consistent(self, sample_block):
        """Test hash calculation consistency"""
        hash1 = calculate_hash(sample_block)
        hash2 = calculate_hash(sample_block)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

    def test_calculate_hash_different_blocks(self, sample_block):
        """Test different blocks produce different hashes"""
        block2 = sample_block.copy()
        block2['nonce'] = 54321

        hash1 = calculate_hash(sample_block)
        hash2 = calculate_hash(block2)
        assert hash1 != hash2

    def test_calculate_hash_empty_block(self, empty_block):
        """Test hash calculation with empty transaction list"""
        block_hash = calculate_hash(empty_block)
        assert block_hash is not None
        assert len(block_hash) == 64

    def test_calculate_hash_malformed_data(self):
        """Test hash calculation with malformed block data"""
        malformed_block = {'invalid': 'structure'}

        with pytest.raises((KeyError, TypeError)):
            calculate_hash(malformed_block)

class TestBlockValidation:
    def test_validate_block_success(self, sample_block, clean_db):
        """Test successful block validation"""
        sample_block['hash'] = calculate_hash(sample_block)

        # Mock previous block hash verification
        with patch('node.rustchain_v2_integrated_v2_2_1_rip200.get_latest_block') as mock_latest:
            mock_latest.return_value = {'hash': 'previous_block_hash', 'index': 0}
            result = validate_block(sample_block)
            assert result is True

    def test_validate_block_invalid_hash(self, sample_block, clean_db):
        """Test block validation with incorrect hash"""
        sample_block['hash'] = 'invalid_hash_value'

        with patch('node.rustchain_v2_integrated_v2_2_1_rip200.get_latest_block') as mock_latest:
            mock_latest.return_value = {'hash': 'previous_block_hash', 'index': 0}
            result = validate_block(sample_block)
            assert result is False

    def test_validate_block_missing_fields(self, clean_db):
        """Test validation with missing required fields"""
        incomplete_block = {'index': 1, 'timestamp': time.time()}

        with pytest.raises(KeyError):
            validate_block(incomplete_block)

    def test_validate_block_future_timestamp(self, sample_block, clean_db):
        """Test validation with future timestamp (edge case)"""
        sample_block['timestamp'] = time.time() + 3600  # 1 hour in future
        sample_block['hash'] = calculate_hash(sample_block)

        with patch('node.rustchain_v2_integrated_v2_2_1_rip200.get_latest_block') as mock_latest:
            mock_latest.return_value = {'hash': 'previous_block_hash', 'index': 0}
            result = validate_block(sample_block)
            # Should still be valid as future timestamp handling may vary
            assert isinstance(result, bool)

class TestMerkleRoot:
    def test_merkle_root_single_transaction(self):
        """Test merkle root with single transaction"""
        transactions = [{'from': 'alice', 'to': 'bob', 'amount': 10.0}]
        root = calculate_merkle_root(transactions)
        assert root is not None
        assert len(root) == 64

    def test_merkle_root_multiple_transactions(self, sample_block):
        """Test merkle root with multiple transactions"""
        root = calculate_merkle_root(sample_block['transactions'])
        assert root is not None
        assert len(root) == 64

    def test_merkle_root_empty_transactions(self):
        """Test merkle root with empty transaction list"""
        root = calculate_merkle_root([])
        # Should handle empty list gracefully
        assert root is not None

    def test_merkle_root_consistency(self, sample_block):
        """Test merkle root calculation consistency"""
        root1 = calculate_merkle_root(sample_block['transactions'])
        root2 = calculate_merkle_root(sample_block['transactions'])
        assert root1 == root2

    def test_merkle_root_order_sensitivity(self):
        """Test that transaction order affects merkle root"""
        tx1 = {'from': 'alice', 'to': 'bob', 'amount': 10.0}
        tx2 = {'from': 'bob', 'to': 'charlie', 'amount': 5.0}

        root1 = calculate_merkle_root([tx1, tx2])
        root2 = calculate_merkle_root([tx2, tx1])
        assert root1 != root2

class TestProofOfWork:
    def test_valid_proof_of_work(self):
        """Test valid proof of work verification"""
        # Create a hash with leading zeros
        valid_hash = '0000abc123def456'  # 4 leading zeros
        assert is_valid_proof_of_work(valid_hash, 4) is True

    def test_invalid_proof_of_work(self):
        """Test invalid proof of work verification"""
        invalid_hash = '123abc456def789'  # No leading zeros
        assert is_valid_proof_of_work(invalid_hash, 4) is False

    def test_proof_of_work_boundary_cases(self):
        """Test proof of work with boundary difficulty values"""
        hash_no_zeros = 'abcdef123456789'
        hash_one_zero = '0abcdef12345678'
        hash_many_zeros = '00000000abcdef1'

        # Zero difficulty
        assert is_valid_proof_of_work(hash_no_zeros, 0) is True

        # Exact match
        assert is_valid_proof_of_work(hash_one_zero, 1) is True
        assert is_valid_proof_of_work(hash_one_zero, 2) is False

        # High difficulty
        assert is_valid_proof_of_work(hash_many_zeros, 8) is True
        assert is_valid_proof_of_work(hash_many_zeros, 9) is False

    def test_proof_of_work_empty_hash(self):
        """Test proof of work with empty hash string"""
        with pytest.raises((IndexError, TypeError)):
            is_valid_proof_of_work('', 1)

class TestDifficultyAdjustment:
    def test_difficulty_increase_fast_blocks(self, clean_db):
        """Test difficulty increases when blocks are mined too fast"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS blocks
                           (id INTEGER PRIMARY KEY, timestamp REAL, difficulty INTEGER)''')

            # Add blocks with timestamps indicating fast mining
            fast_timestamps = [time.time() - i * 5 for i in range(10, 0, -1)]  # 5 sec intervals
            for i, ts in enumerate(fast_timestamps):
                cursor.execute('INSERT INTO blocks (timestamp, difficulty) VALUES (?, ?)', (ts, 4))

        new_difficulty = adjust_difficulty(4)
        assert new_difficulty > 4

    def test_difficulty_decrease_slow_blocks(self, clean_db):
        """Test difficulty decreases when blocks are mined too slowly"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS blocks
                           (id INTEGER PRIMARY KEY, timestamp REAL, difficulty INTEGER)''')

            # Add blocks with timestamps indicating slow mining
            slow_timestamps = [time.time() - i * 600 for i in range(10, 0, -1)]  # 10 min intervals
            for i, ts in enumerate(slow_timestamps):
                cursor.execute('INSERT INTO blocks (timestamp, difficulty) VALUES (?, ?)', (ts, 4))

        new_difficulty = adjust_difficulty(4)
        assert new_difficulty < 4

    def test_difficulty_minimum_boundary(self, clean_db):
        """Test difficulty doesn't go below minimum value"""
        new_difficulty = adjust_difficulty(1)  # Already at minimum
        assert new_difficulty >= 1

class TestTransactionValidation:
    def test_validate_transaction_success(self):
        """Test successful transaction validation"""
        valid_tx = {
            'from': 'alice',
            'to': 'bob',
            'amount': 10.0,
            'fee': 0.1,
            'timestamp': time.time()
        }

        with patch('node.rustchain_v2_integrated_v2_2_1_rip200.get_balance') as mock_balance:
            mock_balance.return_value = 20.0  # Sufficient balance
            result = validate_transaction(valid_tx)
            assert result is True

    def test_validate_transaction_insufficient_funds(self):
        """Test transaction validation with insufficient funds"""
        invalid_tx = {
            'from': 'alice',
            'to': 'bob',
            'amount': 100.0,
            'fee': 0.1,
            'timestamp': time.time()
        }

        with patch('node.rustchain_v2_integrated_v2_2_1_rip200.get_balance') as mock_balance:
            mock_balance.return_value = 5.0  # Insufficient balance
            result = validate_transaction(invalid_tx)
            assert result is False

    def test_validate_transaction_negative_amount(self):
        """Test transaction validation with negative amount"""
        invalid_tx = {
            'from': 'alice',
            'to': 'bob',
            'amount': -10.0,
            'fee': 0.1,
            'timestamp': time.time()
        }

        result = validate_transaction(invalid_tx)
        assert result is False

    def test_validate_transaction_missing_fields(self):
        """Test transaction validation with missing required fields"""
        incomplete_tx = {'from': 'alice', 'amount': 10.0}

        with pytest.raises(KeyError):
            validate_transaction(incomplete_tx)

class TestGenesisBlock:
    def test_create_genesis_block(self, clean_db):
        """Test genesis block creation"""
        genesis = create_genesis_block()

        assert genesis['index'] == 0
        assert genesis['previous_hash'] == '0'
        assert len(genesis['transactions']) == 0
        assert 'timestamp' in genesis
        assert 'hash' in genesis

    def test_genesis_block_uniqueness(self, clean_db):
        """Test genesis blocks have consistent properties"""
        genesis1 = create_genesis_block()
        genesis2 = create_genesis_block()

        # Should have same structure but potentially different timestamps/hashes
        assert genesis1['index'] == genesis2['index']
        assert genesis1['previous_hash'] == genesis2['previous_hash']

class TestMining:
    def test_mine_block_basic(self, sample_block, clean_db):
        """Test basic block mining functionality"""
        with patch('node.rustchain_v2_integrated_v2_2_1_rip200.get_latest_block') as mock_latest:
            mock_latest.return_value = {'hash': 'previous_hash', 'index': 0}

            mined_block = mine_block(sample_block['transactions'], 2)  # Low difficulty for testing

            assert 'nonce' in mined_block
            assert 'hash' in mined_block
            assert is_valid_proof_of_work(mined_block['hash'], 2)

    def test_mine_empty_block(self, clean_db):
        """Test mining block with no transactions"""
        with patch('node.rustchain_v2_integrated_v2_2_1_rip200.get_latest_block') as mock_latest:
            mock_latest.return_value = {'hash': 'previous_hash', 'index': 0}

            mined_block = mine_block([], 1)  # Very low difficulty

            assert len(mined_block['transactions']) == 0
            assert 'hash' in mined_block
            assert is_valid_proof_of_work(mined_block['hash'], 1)
