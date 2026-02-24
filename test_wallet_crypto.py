#!/usr/bin/env python3
"""
Test script to verify the secure wallet works with the new crypto module.
"""

from rustchain_crypto import RustChainWallet, SignedTransaction, verify_transaction

def test_wallet_creation():
    """Test wallet creation and signing."""
    print("Test 1: Creating wallet...")
    wallet = RustChainWallet.create()
    print(f"  ✓ Address: {wallet.address}")
    print(f"  ✓ Mnemonic: {wallet.mnemonic[:50]}...")
    print(f"  ✓ Public key: {wallet.public_key[:40]}...")
    return wallet

def test_wallet_restore(wallet):
    """Test wallet restoration from seed phrase."""
    print("\nTest 2: Restoring wallet from seed...")
    restored = RustChainWallet.from_mnemonic(wallet.mnemonic)
    assert restored.address == wallet.address
    assert restored.public_key == wallet.public_key
    print(f"  ✓ Restored address matches: {restored.address}")

def test_transaction_signing(wallet):
    """Test transaction signing and verification."""
    print("\nTest 3: Signing and verifying transaction...")
    
    # Sign a transaction
    tx_dict = wallet.sign_transaction(
        to_address="RTC" + "A" * 40,
        amount=10.5,
        memo="Test transaction",
        nonce=12345
    )
    
    print(f"  ✓ Transaction signed")
    print(f"    Hash: {tx_dict['tx_hash'][:40]}...")
    print(f"    Signature: {tx_dict['signature'][:40]}...")
    
    # Verify using SignedTransaction class
    tx = SignedTransaction(**tx_dict)
    assert tx.verify() == True
    print(f"  ✓ Signature verification passed")
    
    # Verify using verify_transaction function
    assert verify_transaction(tx) == True
    print(f"  ✓ verify_transaction() passed")
    
    # Test with invalid signature
    tx_bad = SignedTransaction(
        from_addr=tx.from_addr,
        to_addr=tx.to_addr,
        amount_urtc=tx.amount_urtc,
        nonce=tx.nonce,
        timestamp=tx.timestamp,
        memo=tx.memo,
        signature="00" * 64,  # Invalid signature
        public_key=tx.public_key
    )
    assert tx_bad.verify() == False
    print(f"  ✓ Invalid signature correctly rejected")

def test_encrypted_keystore(wallet):
    """Test encrypted wallet export/import."""
    print("\nTest 4: Encrypted keystore...")
    
    # Export
    password = "test123!@#"
    encrypted = wallet.export_encrypted(password)
    print(f"  ✓ Wallet exported with password")
    
    # Restore with correct password
    restored = RustChainWallet.from_encrypted(encrypted, password)
    assert restored.address == wallet.address
    print(f"  ✓ Wallet restored with correct password")
    
    # Try with wrong password (should fail)
    try:
        RustChainWallet.from_encrypted(encrypted, "wrongpassword")
        assert False, "Should have raised exception"
    except Exception as e:
        print(f"  ✓ Wrong password correctly rejected: {type(e).__name__}")

def test_keypair_generation():
    """Test standalone keypair generation."""
    print("\nTest 5: Keypair generation...")
    from rustchain_crypto import generate_keypair
    
    addr, pub, priv = generate_keypair()
    print(f"  ✓ Generated keypair")
    print(f"    Address: {addr}")
    print(f"    Public key: {pub[:40]}...")
    print(f"    Private key: {priv[:40]}...")

def test_address_derivation():
    """Test address derivation from public key."""
    print("\nTest 6: Address derivation...")
    from rustchain_crypto import address_from_public_key, generate_keypair
    
    _, pub, _ = generate_keypair()
    addr = address_from_public_key(bytes.fromhex(pub))
    
    assert addr.startswith("RTC")
    assert len(addr) == 43
    print(f"  ✓ Address derived: {addr}")

def test_hash_functions():
    """Test hash functions."""
    print("\nTest 7: Hash functions...")
    from rustchain_crypto import blake2b256, blake2b256_hex
    
    data = b"test message"
    hash_bytes = blake2b256(data)
    hash_hex = blake2b256_hex(data)
    
    assert len(hash_bytes) == 32
    assert len(hash_hex) == 64
    print(f"  ✓ Blake2b-256 hash: {hash_hex[:40]}...")

if __name__ == "__main__":
    print("=" * 60)
    print("RustChain Crypto Module - Comprehensive Test")
    print("=" * 60)
    
    wallet = test_wallet_creation()
    test_wallet_restore(wallet)
    test_transaction_signing(wallet)
    test_encrypted_keystore(wallet)
    test_keypair_generation()
    test_address_derivation()
    test_hash_functions()
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
