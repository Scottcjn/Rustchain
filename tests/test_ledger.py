import pytest
import sqlite3
import time
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Import mock crypto
from tests import mock_crypto

# Modules are pre-loaded in conftest.py
tx_handler = sys.modules["tx_handler"]

@pytest.fixture
def pool(tmp_path):
    db_path = str(tmp_path / "test_rustchain.db")
    # Initialize with basic schema for balances which might be expected to exist
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE balances (wallet TEXT PRIMARY KEY, balance_urtc INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

    return tx_handler.TransactionPool(db_path)

def test_balance_operations(pool):
    """Verify seeding and checking balances."""
    addr, pub, priv = mock_crypto.generate_wallet_keypair()

    # Seed balance
    with sqlite3.connect(pool.db_path) as conn:
        conn.execute(
            "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
            (addr, 1000, 0)
        )

    assert pool.get_balance(addr) == 1000
    assert pool.get_available_balance(addr) == 1000

def test_address_validation(pool):
    """Verify that public key must match the address."""
    addr1, pub1, priv1 = mock_crypto.generate_wallet_keypair()
    addr2, pub2, priv2 = mock_crypto.generate_wallet_keypair()

    tx = mock_crypto.SignedTransaction(
        from_addr=addr1,
        to_addr=addr2,
        amount_urtc=100,
        nonce=1,
        timestamp=int(time.time()),
        public_key=pub2 # Wrong public key for addr1
    )

    # We need to mock tx.verify to pass for this test
    with patch.object(tx, 'verify', return_value=True):
        is_valid, reason = pool.validate_transaction(tx)
        assert is_valid is False
        assert "Public key does not match from_addr" in reason

def test_nonce_replay_protection(pool):
    """Verify that duplicate nonces are rejected."""
    addr1, pub1, priv1 = mock_crypto.generate_wallet_keypair()
    addr2, pub2, priv2 = mock_crypto.generate_wallet_keypair()

    # Seed balance
    with sqlite3.connect(pool.db_path) as conn:
        conn.execute(
            "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
            (addr1, 1000, 0)
        )

    tx1 = mock_crypto.SignedTransaction(
        from_addr=addr1,
        to_addr=addr2,
        amount_urtc=100,
        nonce=1,
        timestamp=int(time.time()),
        public_key=pub1
    )

    # First submission
    with patch.object(tx1, 'verify', return_value=True):
        success, res = pool.submit_transaction(tx1)
        assert success is True

    # Second submission with same nonce
    tx2 = mock_crypto.SignedTransaction(
        from_addr=addr1,
        to_addr=addr2,
        amount_urtc=50,
        nonce=1, # Duplicate nonce
        timestamp=int(time.time()) + 1,
        public_key=pub1
    )

    with patch.object(tx2, 'verify', return_value=True):
        success, reason = pool.submit_transaction(tx2)
        assert success is False
        assert "Invalid nonce" in reason

def test_insufficient_balance(pool):
    """Verify that transactions exceeding balance are rejected."""
    addr1, pub1, priv1 = mock_crypto.generate_wallet_keypair()
    addr2, pub2, priv2 = mock_crypto.generate_wallet_keypair()

    # Seed small balance
    with sqlite3.connect(pool.db_path) as conn:
        conn.execute(
            "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
            (addr1, 50, 0)
        )

    tx = mock_crypto.SignedTransaction(
        from_addr=addr1,
        to_addr=addr2,
        amount_urtc=100, # More than 50
        nonce=1,
        timestamp=int(time.time()),
        public_key=pub1
    )

    with patch.object(tx, 'verify', return_value=True):
        is_valid, reason = pool.validate_transaction(tx)
        assert is_valid is False
        assert "Insufficient balance" in reason
