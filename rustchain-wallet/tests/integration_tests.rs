//! Integration tests for RustChain Wallet
//!
//! These tests verify the complete wallet functionality.

use rustchain_wallet::{Wallet, KeyPair, Network, Transaction, TransactionBuilder, WalletStorage};
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
    let storage = WalletStorage::new(temp_dir.path());
    
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
    let storage = WalletStorage::new(temp_dir.path());
    
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
