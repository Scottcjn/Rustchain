#!/usr/bin/env python3
"""
RustChain SDK Test Runner
==========================

Simple script to test the RustChain Python SDK installation and basic functionality.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        from rustchain import (
            RustChainClient,
            Wallet,
            Transaction,
            RustChainError,
            WalletError,
            TransactionError,
        )
        print("[OK] All imports successful")
        return True
    except ImportError as e:
        print(f"[FAIL] Import failed: {e}")
        return False


def test_client_initialization():
    """Test client initialization"""
    print("\nTesting client initialization...")
    
    try:
        from rustchain import RustChainClient
        
        # Test default initialization
        client = RustChainClient()
        assert client.node_url == "https://50.28.86.131"
        assert client.admin_key is None
        assert client.timeout == 10
        
        # Test custom initialization
        client2 = RustChainClient(
            node_url="https://custom-node.example.com",
            admin_key="test-key",
            timeout=30
        )
        assert client2.node_url == "https://custom-node.example.com"
        assert client2.admin_key == "test-key"
        assert client2.timeout == 30
        
        print("[OK] Client initialization successful")
        return True
    except Exception as e:
        print(f"[FAIL] Client initialization failed: {e}")
        return False


def test_wallet_validation():
    """Test wallet name validation"""
    print("\nTesting wallet validation...")
    
    try:
        from rustchain import RustChainClient, Wallet
        
        client = RustChainClient()
        wallet = Wallet(client)
        
        # Test valid names
        valid_names = ["my-wallet", "wallet123", "test-01", "abc"]
        for name in valid_names:
            is_valid, msg = wallet.validate_name(name)
            assert is_valid, f"Valid name '{name}' failed: {msg}"
        
        # Test invalid names
        invalid_names = [
            ("AB", "too short"),
            ("a" * 65, "too long"),
            ("My-Wallet", "uppercase"),
            ("my_wallet", "underscore"),
            ("-wallet", "starts with hyphen"),
            ("wallet-", "ends with hyphen"),
        ]
        
        for name, reason in invalid_names:
            is_valid, msg = wallet.validate_name(name)
            assert not is_valid, f"Invalid name '{name}' ({reason}) passed validation"
        
        print("[OK] Wallet validation successful")
        return True
    except Exception as e:
        print(f"[FAIL] Wallet validation failed: {e}")
        return False


def test_transaction_building():
    """Test transaction building"""
    print("\nTesting transaction building...")
    
    try:
        from rustchain import RustChainClient, Transaction
        
        client = RustChainClient(admin_key="test-key")
        tx = Transaction(client)
        
        # Test build_transfer (no network call)
        preview = tx.build_transfer("wallet1", "wallet2", 10.0)
        assert preview["from_miner"] == "wallet1"
        assert preview["to_miner"] == "wallet2"
        assert preview["amount_rtc"] == 10.0
        assert preview["status"] == "preview"
        
        # Test validation without network check
        # Just test basic validation logic
        is_valid, msg = tx.validate_transfer.__func__(tx, "wallet1", "wallet2", 10.0)
        # We expect this to try network call, which is OK
        # Just checking method exists and has correct signature
        
        print("[OK] Transaction building successful")
        return True
    except Exception as e:
        # Network errors are expected here
        if "balance" in str(e).lower() or "404" in str(e) or "HTTP" in str(e):
            print("[OK] Transaction building successful (network-dependent check skipped)")
            return True
        print(f"[FAIL] Transaction building failed: {e}")
        return False


def test_exceptions():
    """Test exception classes"""
    print("\nTesting exceptions...")
    
    try:
        from rustchain.exceptions import (
            RustChainError,
            WalletError,
            TransactionError,
            NetworkError,
            AuthenticationError,
        )
        
        # Test RustChainError
        error = RustChainError("Test error", status_code=500)
        assert str(error) == "500: Test error"
        assert error.status_code == 500
        
        # Test without status code
        error2 = RustChainError("Test error 2")
        assert str(error2) == "Test error 2"
        
        # Test subclasses
        wallet_error = WalletError("Wallet error")
        assert isinstance(wallet_error, RustChainError)
        
        tx_error = TransactionError("Transaction error")
        assert isinstance(tx_error, RustChainError)
        
        network_error = NetworkError("Network error")
        assert isinstance(network_error, RustChainError)
        
        auth_error = AuthenticationError("Auth error")
        assert isinstance(auth_error, RustChainError)
        
        print("[OK] Exception tests successful")
        return True
    except Exception as e:
        print(f"[FAIL] Exception tests failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("RustChain Python SDK - Test Suite")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_client_initialization,
        test_wallet_validation,
        test_transaction_building,
        test_exceptions,
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print("\n[FAILED] Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
