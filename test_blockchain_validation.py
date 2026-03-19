// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import pytest
import hashlib
import json
import time
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from node.rustchain_v2_integrated_v2.2.1_rip200 import (
    validate_hash,
    validate_block,
    validate_transaction,
    calculate_hash,
    Block,
    Transaction
)


class TestHashValidation:
    def test_validate_hash_valid_sha256(self):
        valid_hash = hashlib.sha256(b"test").hexdigest()
        assert validate_hash(valid_hash) == True
    
    def test_validate_hash_empty_string(self):
        assert validate_hash("") == False
    
    def test_validate_hash_none_input(self):
        assert validate_hash(None) == False
    
    def test_validate_hash_invalid_length(self):
        short_hash = "abc123"
        assert validate_hash(short_hash) == False
    
    def test_validate_hash_invalid_characters(self):
        invalid_hash = "g" * 64  # 'g' is not a valid hex character
        assert validate_hash(invalid_hash) == False
    
    def test_validate_hash_mixed_case(self):
        mixed_case_hash = "A" * 32 + "b" * 32
        assert validate_hash(mixed_case_hash) == True


class TestBlockValidation:
    def test_validate_block_valid_genesis(self):
        genesis_block = Block(0, [], "0", None)
        genesis_block.hash = calculate_hash(genesis_block)
        assert validate_block(genesis_block, None) == True
    
    def test_validate_block_none_input(self):
        assert validate_block(None, None) == False
    
    def test_validate_block_invalid_previous_hash(self):
        previous_block = Block(0, [], "0", None)
        previous_block.hash = calculate_hash(previous_block)
        
        current_block = Block(1, [], "invalid_hash", previous_block.hash)
        current_block.hash = calculate_hash(current_block)
        
        assert validate_block(current_block, previous_block) == False
    
    def test_validate_block_negative_index(self):
        block = Block(-1, [], "0", None)
        block.hash = calculate_hash(block)
        assert validate_block(block, None) == False
    
    def test_validate_block_incorrect_index_sequence(self):
        previous_block = Block(0, [], "0", None)
        previous_block.hash = calculate_hash(previous_block)
        
        current_block = Block(5, [], previous_block.hash, previous_block.hash)
        current_block.hash = calculate_hash(current_block)
        
        assert validate_block(current_block, previous_block) == False
    
    def test_validate_block_tampered_hash(self):
        block = Block(0, [], "0", None)
        block.hash = "tampered_hash"
        assert validate_block(block, None) == False


class TestTransactionValidation:
    def test_validate_transaction_valid_standard(self):
        transaction = Transaction("alice", "bob", 10.0, "payment")
        assert validate_transaction(transaction) == True
    
    def test_validate_transaction_none_input(self):
        assert validate_transaction(None) == False
    
    def test_validate_transaction_empty_sender(self):
        transaction = Transaction("", "bob", 10.0, "payment")
        assert validate_transaction(transaction) == False
    
    def test_validate_transaction_empty_receiver(self):
        transaction = Transaction("alice", "", 10.0, "payment")
        assert validate_transaction(transaction) == False
    
    def test_validate_transaction_negative_amount(self):
        transaction = Transaction("alice", "bob", -5.0, "payment")
        assert validate_transaction(transaction) == False
    
    def test_validate_transaction_zero_amount(self):
        transaction = Transaction("alice", "bob", 0.0, "payment")
        assert validate_transaction(transaction) == False
    
    def test_validate_transaction_none_amount(self):
        transaction = Transaction("alice", "bob", None, "payment")
        assert validate_transaction(transaction) == False
    
    def test_validate_transaction_string_amount(self):
        transaction = Transaction("alice", "bob", "invalid", "payment")
        assert validate_transaction(transaction) == False
    
    def test_validate_transaction_same_sender_receiver(self):
        transaction = Transaction("alice", "alice", 10.0, "payment")
        assert validate_transaction(transaction) == False
    
    def test_validate_transaction_large_amount(self):
        transaction = Transaction("alice", "bob", 999999999.99, "payment")
        assert validate_transaction(transaction) == True
    
    def test_validate_transaction_whitespace_addresses(self):
        transaction = Transaction("  alice  ", "  bob  ", 10.0, "payment")
        assert validate_transaction(transaction) == False


class TestCalculateHash:
    def test_calculate_hash_consistent(self):
        block = Block(0, [], "0", None)
        hash1 = calculate_hash(block)
        hash2 = calculate_hash(block)
        assert hash1 == hash2
    
    def test_calculate_hash_different_blocks(self):
        block1 = Block(0, [], "0", None)
        block2 = Block(1, [], "0", None)
        hash1 = calculate_hash(block1)
        hash2 = calculate_hash(block2)
        assert hash1 != hash2
    
    def test_calculate_hash_format(self):
        block = Block(0, [], "0", None)
        block_hash = calculate_hash(block)
        assert len(block_hash) == 64
        assert all(c in '0123456789abcdef' for c in block_hash)


class TestIntegrationScenarios:
    def test_blockchain_with_multiple_transactions(self):
        transactions = [
            Transaction("alice", "bob", 10.0, "payment"),
            Transaction("bob", "charlie", 5.0, "payment"),
            Transaction("charlie", "dave", 2.5, "payment")
        ]
        
        for tx in transactions:
            assert validate_transaction(tx) == True
        
        block = Block(1, transactions, "previous_hash", "previous_hash")
        block.hash = calculate_hash(block)
        
        assert validate_hash(block.hash) == True
    
    def test_corrupted_blockchain_detection(self):
        genesis = Block(0, [], "0", None)
        genesis.hash = calculate_hash(genesis)
        
        block1 = Block(1, [], genesis.hash, genesis.hash)
        block1.hash = calculate_hash(block1)
        
        # Corrupt the genesis block
        genesis.previous_hash = "corrupted"
        
        assert validate_block(block1, genesis) == False