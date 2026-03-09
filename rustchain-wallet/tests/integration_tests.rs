//! Integration tests for RustChain Wallet
//!
//! These tests verify the complete wallet functionality.

use rustchain_wallet::{Wallet, KeyPair, Network, Transaction, TransactionBuilder, WalletStorage, NonceStore};
use tempfile::TempDir;

#[test]
fn test_wallet_creation_and_signing() {
    // Generate wallet
    let wallet = Wallet::generate();
    
    // Verify address format
    assert!(!wallet.address().is_empty());
    // Base58 encoded Ed25519 public key is typically 43-44 characters
    assert!(wallet.address().len() >= 43);
    
    // Verify public key format
    assert_eq!(wallet.public_key().len(), 64); // Hex encoded
    
    // Sign and verify
    let message = b"Test message";
    let signature = wallet.sign(message).unwrap();
    assert_eq!(signature.len(), 64);
    
    let valid = wallet.verify(message, &signature).unwrap();
    assert!(valid);
}

#[test]
fn test_network_configuration() {
    let mainnet_wallet = Wallet::generate();
    assert_eq!(mainnet_wallet.network(), Network::Mainnet);
    
    let testnet_wallet = Wallet::with_network(KeyPair::generate(), Network::Testnet);
    assert_eq!(testnet_wallet.network(), Network::Testnet);
    
    let devnet_wallet = Wallet::with_network(KeyPair::generate(), Network::Devnet);
    assert_eq!(devnet_wallet.network(), Network::Devnet);
}

#[test]
fn test_keypair_import_export() {
    // Generate original keypair
    let original = KeyPair::generate();
    let original_address = original.public_key_base58();
    
    // Export private key
    let private_key = original.export_private_key();
    
    // Import from hex
    let imported_hex = KeyPair::from_hex(&private_key).unwrap();
    assert_eq!(imported_hex.public_key_base58(), original_address);
    
    // Import from bytes
    let private_bytes = original.export_private_key_bytes();
    let imported_bytes = KeyPair::from_bytes(&private_bytes).unwrap();
    assert_eq!(imported_bytes.public_key_base58(), original_address);
}

#[test]
fn test_transaction_lifecycle() {
    let sender = Wallet::generate();
    let recipient = Wallet::generate();
    
    // Create transaction
    let mut tx = TransactionBuilder::new()
        .from(sender.address())
        .to(recipient.address())
        .amount(1000)
        .fee(100)
        .nonce(1)
        .memo("Test transaction".to_string())
        .build()
        .unwrap();
    
    // Verify initial state
    assert_eq!(tx.amount, 1000);
    assert_eq!(tx.fee, 100);
    assert!(tx.signature.is_none());
    
    // Sign transaction
    tx.sign(sender.keypair()).unwrap();
    assert!(tx.signature.is_some());
    
    // Verify signature
    let valid = tx.verify(sender.keypair()).unwrap();
    assert!(valid);
    
    // Verify with wrong key fails
    let valid = tx.verify(recipient.keypair()).unwrap();
    assert!(!valid);
    
    // Serialize and deserialize
    let json = tx.to_json().unwrap();
    let loaded = Transaction::from_json(&json).unwrap();
    assert_eq!(tx.signature, loaded.signature);
}

#[test]
fn test_encrypted_storage() {
    let temp_dir = TempDir::new().unwrap();
    let storage = WalletStorage::new(temp_dir.path()).unwrap();

    let wallet = Wallet::generate();
    let address = wallet.address();
    let password = "test_password_123";

    // Save wallet
    let path = storage.save("test_wallet", wallet.keypair(), password).unwrap();
    assert!(path.exists());

    // Load wallet
    let loaded = storage.load("test_wallet", password).unwrap();
    assert_eq!(loaded.public_key_base58(), address);

    // Wrong password fails
    let result = storage.load("test_wallet", "wrong_password");
    assert!(result.is_err());

    // List wallets
    let wallets = storage.list().unwrap();
    assert_eq!(wallets.len(), 1);
    assert!(wallets.contains(&"test_wallet".to_string()));

    // Delete wallet
    storage.delete("test_wallet").unwrap();
    assert!(!storage.exists("test_wallet"));
}

#[test]
fn test_multiple_wallets_storage() {
    let temp_dir = TempDir::new().unwrap();
    let storage = WalletStorage::new(temp_dir.path()).unwrap();

    // Create multiple wallets
    for i in 1..=5 {
        let wallet = Wallet::generate();
        let name = format!("wallet_{}", i);
        storage.save(&name, wallet.keypair(), "password").unwrap();
    }

    // List all
    let wallets = storage.list().unwrap();
    assert_eq!(wallets.len(), 5);

    // Load each and verify
    for i in 1..=5 {
        let name = format!("wallet_{}", i);
        let keypair = storage.load(&name, "password").unwrap();
        assert!(!keypair.public_key_base58().is_empty());
    }
}

#[test]
fn test_signature_verification_edge_cases() {
    let keypair = KeyPair::generate();
    let message = b"Test message";
    
    // Empty message
    let empty_sig = keypair.sign(b"").unwrap();
    assert!(keypair.verify(b"", &empty_sig).unwrap());
    
    // Large message
    let large_message = vec![0u8; 10000];
    let large_sig = keypair.sign(&large_message).unwrap();
    assert!(keypair.verify(&large_message, &large_sig).unwrap());
    
    // Invalid signature length
    let result = keypair.verify(message, &[1u8; 32]);
    assert!(result.is_err());
    
    // Tampered signature
    let valid_sig = keypair.sign(message).unwrap();
    let mut tampered_sig = valid_sig.clone();
    tampered_sig[0] ^= 0xFF;
    let valid = keypair.verify(message, &tampered_sig).unwrap();
    assert!(!valid);
}

#[test]
fn test_transaction_hash_uniqueness() {
    let sender = Wallet::generate();
    
    // Create two transactions with different amounts
    let mut tx1 = TransactionBuilder::new()
        .from(sender.address())
        .to("recipient".to_string())
        .amount(1000)
        .fee(100)
        .nonce(1)
        .build()
        .unwrap();
    
    let mut tx2 = TransactionBuilder::new()
        .from(sender.address())
        .to("recipient".to_string())
        .amount(2000)
        .fee(100)
        .nonce(2)
        .build()
        .unwrap();
    
    tx1.sign(sender.keypair()).unwrap();
    tx2.sign(sender.keypair()).unwrap();
    
    let hash1 = tx1.hash().unwrap();
    let hash2 = tx2.hash().unwrap();
    
    assert_ne!(hash1, hash2);
}

#[test]
fn test_keypair_from_different_formats() {
    let original = KeyPair::generate();
    let original_hex = original.public_key_hex();
    
    // From hex
    let from_hex = KeyPair::from_hex(&original.export_private_key()).unwrap();
    assert_eq!(from_hex.public_key_hex(), original_hex);
    
    // From base58
    let private_base58 = bs58::encode(original.export_private_key_bytes()).into_string();
    let from_base58 = KeyPair::from_base58(&private_base58).unwrap();
    assert_eq!(from_base58.public_key_hex(), original_hex);
    
    // Invalid formats
    assert!(KeyPair::from_hex("invalid_hex!").is_err());
    assert!(KeyPair::from_bytes(&[1u8; 16]).is_err()); // Wrong length
}

#[test]
fn test_wallet_clone() {
    let wallet = Wallet::generate();
    let address = wallet.address();
    
    let cloned = wallet.clone();
    assert_eq!(cloned.address(), address);
    
    // Both should sign the same
    let message = b"Test";
    let sig1 = wallet.sign(message).unwrap();
    let sig2 = cloned.sign(message).unwrap();

    assert_eq!(sig1, sig2);
}

// ==================== Issue #728: Nonce Persistence & Replay Protection ====================

#[test]
fn test_nonce_persistence_across_storage_restart() {
    let temp_dir = TempDir::new().unwrap();
    let path = temp_dir.path();

    // Create storage, mark some nonces
    let test_address;
    {
        let mut storage = WalletStorage::new(path).unwrap();
        let wallet = Wallet::generate();
        test_address = wallet.address();

        // Mark several nonces
        storage.mark_nonce_used(&test_address, 0).unwrap();
        storage.mark_nonce_used(&test_address, 1).unwrap();
        storage.mark_nonce_used(&test_address, 5).unwrap();
        // Storage drops here, should persist to disk
    }

    // Create new storage instance (simulates application restart)
    let storage2 = WalletStorage::new(path).unwrap();

    // Verify nonces persisted across "restart"
    assert!(storage2.is_nonce_used(&test_address, 0));
    assert!(storage2.is_nonce_used(&test_address, 1));
    assert!(storage2.is_nonce_used(&test_address, 5));
    assert!(!storage2.is_nonce_used(&test_address, 2));
    assert_eq!(storage2.get_next_nonce(&test_address), 6);
}

#[test]
fn test_replay_protection_integration() {
    let temp_dir = TempDir::new().unwrap();
    let mut storage = WalletStorage::new(temp_dir.path()).unwrap();

    let sender = Wallet::generate();
    let recipient = Wallet::generate();
    let address = sender.address();

    // Create and sign transaction
    let mut tx = TransactionBuilder::new()
        .from(address.clone())
        .to(recipient.address())
        .amount(1000)
        .fee(100)
        .nonce(0)
        .build()
        .unwrap();
    tx.sign(sender.keypair()).unwrap();

    // First submission should succeed
    assert!(tx.verify_nonce(storage.nonce_store()).is_ok());
    storage.mark_nonce_used(&address, 0).unwrap();

    // Replay attempt should fail
    assert!(tx.verify_nonce(storage.nonce_store()).is_err());
}

#[test]
fn test_nonce_persistence_multiple_transactions_restart() {
    let temp_dir = TempDir::new().unwrap();
    let path = temp_dir.path();

    let sender = Wallet::generate();
    let recipient = Wallet::generate();
    let address = sender.address();

    // Session 1: Create and "submit" first transaction
    {
        let mut storage = WalletStorage::new(path).unwrap();
        let mut tx1 = TransactionBuilder::new()
            .from(address.clone())
            .to(recipient.address())
            .amount(1000)
            .fee(100)
            .nonce(0)
            .build()
            .unwrap();
        tx1.sign(sender.keypair()).unwrap();

        assert!(tx1.verify_nonce(storage.nonce_store()).is_ok());
        storage.mark_nonce_used(&address, 0).unwrap();
        // Storage drops, persists to disk
    }

    // Session 2: Create second transaction (should know about first)
    {
        let mut storage = WalletStorage::new(path).unwrap();

        // Verify nonce 0 is marked used
        assert!(storage.is_nonce_used(&address, 0));
        assert_eq!(storage.get_next_nonce(&address), 1);

        // Create transaction with nonce 1
        let mut tx2 = TransactionBuilder::new()
            .from(address.clone())
            .to(recipient.address())
            .amount(2000)
            .fee(100)
            .nonce(1)
            .build()
            .unwrap();
        tx2.sign(sender.keypair()).unwrap();

        // Should succeed
        assert!(tx2.verify_nonce(storage.nonce_store()).is_ok());
        storage.mark_nonce_used(&address, 1).unwrap();
    }

    // Session 3: Verify both nonces persisted
    {
        let storage = WalletStorage::new(path).unwrap();
        assert!(storage.is_nonce_used(&address, 0));
        assert!(storage.is_nonce_used(&address, 1));
        assert_eq!(storage.get_next_nonce(&address), 2);

        // Replay of either transaction should fail
        let mut replay_tx = TransactionBuilder::new()
            .from(address.clone())
            .to(recipient.address())
            .amount(1000)
            .fee(100)
            .nonce(0)
            .build()
            .unwrap();
        replay_tx.sign(sender.keypair()).unwrap();
        assert!(replay_tx.verify_nonce(storage.nonce_store()).is_err());
    }
}

#[test]
fn test_nonce_store_direct_persistence() {
    let temp_dir = TempDir::new().unwrap();
    let path = temp_dir.path().join("nonces.json");

    // Create and populate nonce store
    {
        let mut store = NonceStore::new();
        store.mark_used("address_a", 0);
        store.mark_used("address_a", 1);
        store.mark_used("address_b", 5);
        store.save(&path).unwrap();
    }

    // Load from disk
    let loaded = NonceStore::load_or_create(&path).unwrap();

    // Verify data
    assert!(loaded.is_used("address_a", 0));
    assert!(loaded.is_used("address_a", 1));
    assert!(loaded.is_used("address_b", 5));
    assert!(!loaded.is_used("address_a", 2));
    assert_eq!(loaded.get_next_nonce("address_a"), 2);
    assert_eq!(loaded.get_next_nonce("address_b"), 6);
}

#[test]
fn test_replay_protection_complete_verification() {
    let temp_dir = TempDir::new().unwrap();
    let mut storage = WalletStorage::new(temp_dir.path()).unwrap();

    let sender = Wallet::generate();
    let address = sender.address();

    let mut tx = Transaction::new(
        address.clone(),
        "recipient".to_string(),
        1000,
        100,
        0,
    );
    tx.sign(sender.keypair()).unwrap();

    // Complete verification should succeed initially
    assert!(tx.verify_complete(sender.keypair(), storage.nonce_store()).unwrap());

    // Mark nonce as used
    storage.mark_nonce_used(&address, 0).unwrap();

    // Complete verification should now fail (replay detected)
    assert!(tx.verify_complete(sender.keypair(), storage.nonce_store()).is_err());
}

#[test]
fn test_concurrent_nonce_different_addresses() {
    let temp_dir = TempDir::new().unwrap();
    let mut storage = WalletStorage::new(temp_dir.path()).unwrap();

    let wallet1 = Wallet::generate();
    let wallet2 = Wallet::generate();
    let wallet3 = Wallet::generate();

    // All use nonce 0 - should all succeed (different addresses)
    let mut tx1 = Transaction::new(wallet1.address(), "recipient".to_string(), 1000, 100, 0);
    let mut tx2 = Transaction::new(wallet2.address(), "recipient".to_string(), 1000, 100, 0);
    let mut tx3 = Transaction::new(wallet3.address(), "recipient".to_string(), 1000, 100, 0);

    tx1.sign(wallet1.keypair()).unwrap();
    tx2.sign(wallet2.keypair()).unwrap();
    tx3.sign(wallet3.keypair()).unwrap();

    assert!(tx1.verify_nonce(storage.nonce_store()).is_ok());
    assert!(tx2.verify_nonce(storage.nonce_store()).is_ok());
    assert!(tx3.verify_nonce(storage.nonce_store()).is_ok());

    // Mark all as used
    storage.mark_nonce_used(&wallet1.address(), 0).unwrap();
    storage.mark_nonce_used(&wallet2.address(), 0).unwrap();
    storage.mark_nonce_used(&wallet3.address(), 0).unwrap();

    // Each address should now have nonce 0 marked
    assert!(storage.is_nonce_used(&wallet1.address(), 0));
    assert!(storage.is_nonce_used(&wallet2.address(), 0));
    assert!(storage.is_nonce_used(&wallet3.address(), 0));

    // But nonce 0 for a new address should still be valid
    let wallet4 = Wallet::generate();
    let tx4 = Transaction::new(wallet4.address(), "recipient".to_string(), 1000, 100, 0);
    assert!(tx4.verify_nonce(storage.nonce_store()).is_ok());
}
