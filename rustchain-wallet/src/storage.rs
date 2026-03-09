//! Secure wallet storage
//!
//! This module provides encrypted storage for wallet keypairs,
//! using AES-256-GCM encryption with a user-provided password.
//! It also manages persistent nonce storage for replay protection.

use std::fs;
use std::path::{Path, PathBuf};
use serde::{Serialize, Deserialize};
use aes_gcm::aead::Aead;

use crate::error::{Result, WalletError};
use crate::keys::KeyPair;
use crate::nonce_store::NonceStore;

/// Encrypted wallet file structure
#[derive(Serialize, Deserialize)]
struct EncryptedWallet {
    version: u8,
    ciphertext: Vec<u8>,
    nonce: Vec<u8>,
    salt: Vec<u8>,
}

/// Wallet storage manager
pub struct WalletStorage {
    storage_path: PathBuf,
    nonce_store_path: PathBuf,
    nonce_store: NonceStore,
}

impl WalletStorage {
    /// Create a new wallet storage at the specified path
    pub fn new<P: AsRef<Path>>(path: P) -> Result<Self> {
        let storage_path = path.as_ref().to_path_buf();
        let nonce_store_path = storage_path.join("nonces.json");
        
        // Load existing nonce store or create new one (migration support)
        let nonce_store = NonceStore::load_or_create(&nonce_store_path)?;
        
        Ok(Self {
            storage_path,
            nonce_store_path,
            nonce_store,
        })
    }

    /// Get the default wallet storage directory
    pub fn default_path() -> Result<PathBuf> {
        let base = dirs::home_dir()
            .ok_or_else(|| WalletError::Storage("Could not determine home directory".to_string()))?;
        Ok(base.join(".rustchain").join("wallets"))
    }

    /// Create storage at the default location
    pub fn default() -> Result<Self> {
        let path = Self::default_path()?;
        fs::create_dir_all(&path)?;
        Self::new(path)
    }

    /// Save a keypair to an encrypted file
    pub fn save(&self, name: &str, keypair: &KeyPair, password: &str) -> Result<PathBuf> {
        let private_key = keypair.export_private_key();
        let private_bytes = hex::decode(&private_key)?;
        
        // Generate random salt
        let mut salt = [0u8; 32];
        getrandom::getrandom(&mut salt).map_err(|e| {
            WalletError::Encryption(format!("Failed to generate salt: {}", e))
        })?;

        // Derive encryption key from password
        let key = derive_key(password, &salt)?;

        // Generate random nonce
        let mut nonce = [0u8; 12];
        getrandom::getrandom(&mut nonce).map_err(|e| {
            WalletError::Encryption(format!("Failed to generate nonce: {}", e))
        })?;

        // Encrypt the private key
        let ciphertext = encrypt_aes_gcm(&key, &nonce, &private_bytes)?;

        let encrypted = EncryptedWallet {
            version: 1,
            ciphertext,
            nonce: nonce.to_vec(),
            salt: salt.to_vec(),
        };

        // Create wallet directory if it doesn't exist
        fs::create_dir_all(&self.storage_path)?;

        // Save to file
        let file_path = self.storage_path.join(format!("{}.wallet", name));
        let data = serde_json::to_vec_pretty(&encrypted)?;
        fs::write(&file_path, data)?;

        // Set restrictive permissions (Unix only)
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut perms = fs::metadata(&file_path)?.permissions();
            perms.set_mode(0o600);
            fs::set_permissions(&file_path, perms)?;
        }

        Ok(file_path)
    }

    /// Load a keypair from an encrypted file
    pub fn load(&self, name: &str, password: &str) -> Result<KeyPair> {
        let file_path = self.storage_path.join(format!("{}.wallet", name));
        
        if !file_path.exists() {
            return Err(WalletError::Storage(
                format!("Wallet file not found: {}", file_path.display())
            ));
        }

        let data = fs::read(&file_path)?;
        let encrypted: EncryptedWallet = serde_json::from_slice(&data)?;

        // Derive decryption key from password
        let key = derive_key(password, &encrypted.salt)?;

        // Decrypt the private key
        let private_bytes = decrypt_aes_gcm(
            &key,
            &encrypted.nonce,
            &encrypted.ciphertext
        )?;

        KeyPair::from_bytes(&private_bytes)
    }

    /// List all stored wallets
    pub fn list(&self) -> Result<Vec<String>> {
        let mut wallets = Vec::new();
        
        if !self.storage_path.exists() {
            return Ok(wallets);
        }

        for entry in fs::read_dir(&self.storage_path)? {
            let entry = entry?;
            let path = entry.path();
            
            if path.extension().and_then(|s| s.to_str()) == Some("wallet") {
                if let Some(name) = path.file_stem().and_then(|s| s.to_str()) {
                    wallets.push(name.to_string());
                }
            }
        }

        wallets.sort();
        Ok(wallets)
    }

    /// Check if a wallet exists
    pub fn exists(&self, name: &str) -> bool {
        self.storage_path.join(format!("{}.wallet", name)).exists()
    }

    /// Delete a wallet
    pub fn delete(&self, name: &str) -> Result<()> {
        let file_path = self.storage_path.join(format!("{}.wallet", name));
        
        if !file_path.exists() {
            return Err(WalletError::Storage(
                format!("Wallet file not found: {}", file_path.display())
            ));
        }

        fs::remove_file(&file_path)?;
        Ok(())
    }

    /// Get the storage path
    pub fn path(&self) -> &Path {
        &self.storage_path
    }

    // ==================== Nonce Management ====================

    /// Mark a nonce as used for an address and persist to disk
    pub fn mark_nonce_used(&mut self, address: &str, nonce: u64) -> Result<bool> {
        let is_new = self.nonce_store.mark_used(address, nonce);
        self.save_nonce_store()?;
        Ok(is_new)
    }

    /// Check if a nonce has been used for an address
    pub fn is_nonce_used(&self, address: &str, nonce: u64) -> bool {
        self.nonce_store.is_used(address, nonce)
    }

    /// Get the next suggested nonce for an address
    pub fn get_next_nonce(&self, address: &str) -> u64 {
        self.nonce_store.get_next_nonce(address)
    }

    /// Validate that a nonce hasn't been used (replay protection)
    pub fn validate_nonce(&self, address: &str, nonce: u64) -> Result<()> {
        self.nonce_store.validate_nonce(address, nonce)
    }

    /// Get the count of used nonces for an address
    pub fn used_nonce_count(&self, address: &str) -> usize {
        self.nonce_store.used_count(address)
    }

    /// Persist the nonce store to disk
    pub fn save_nonce_store(&self) -> Result<()> {
        self.nonce_store.save(&self.nonce_store_path)
    }

    /// Get a reference to the internal nonce store
    pub fn nonce_store(&self) -> &NonceStore {
        &self.nonce_store
    }

    /// Get a mutable reference to the internal nonce store
    pub fn nonce_store_mut(&mut self) -> &mut NonceStore {
        &mut self.nonce_store
    }
}

/// Derive an AES-256 key from a password using PBKDF2
fn derive_key(password: &str, salt: &[u8]) -> Result<[u8; 32]> {
    use pbkdf2::pbkdf2_hmac;
    use sha2::Sha256;

    let mut key = [0u8; 32];
    pbkdf2_hmac::<Sha256>(
        password.as_bytes(),
        salt,
        100_000, // Iterations for strong key derivation
        &mut key,
    );
    Ok(key)
}

/// Encrypt data using AES-256-GCM
fn encrypt_aes_gcm(key: &[u8; 32], nonce: &[u8], plaintext: &[u8]) -> Result<Vec<u8>> {
    use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
    
    let cipher = Aes256Gcm::new_from_slice(key)
        .map_err(|e| WalletError::Encryption(e.to_string()))?;
    
    let nonce = Nonce::from_slice(nonce);
    let ciphertext = cipher.encrypt(nonce, plaintext)
        .map_err(|e| WalletError::Encryption(e.to_string()))?;
    
    Ok(ciphertext)
}

/// Decrypt data using AES-256-GCM
fn decrypt_aes_gcm(key: &[u8; 32], nonce: &[u8], ciphertext: &[u8]) -> Result<Vec<u8>> {
    use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
    
    let cipher = Aes256Gcm::new_from_slice(key)
        .map_err(|e| WalletError::Decryption(e.to_string()))?;
    
    let nonce = Nonce::from_slice(nonce);
    let plaintext = cipher.decrypt(nonce, ciphertext)
        .map_err(|_| WalletError::Decryption("Invalid password or corrupted data".to_string()))?;
    
    Ok(plaintext)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn test_wallet_storage_save_and_load() {
        let temp_dir = TempDir::new().unwrap();
        let storage = WalletStorage::new(temp_dir.path()).unwrap();

        let keypair = KeyPair::generate();
        let public_key = keypair.public_key_hex();
        let password = "test_password_123";

        // Save the wallet
        let path = storage.save("test_wallet", &keypair, password).unwrap();
        assert!(path.exists());

        // Load the wallet
        let loaded = storage.load("test_wallet", password).unwrap();
        assert_eq!(loaded.public_key_hex(), public_key);
    }

    #[test]
    fn test_wallet_storage_wrong_password() {
        let temp_dir = TempDir::new().unwrap();
        let storage = WalletStorage::new(temp_dir.path()).unwrap();

        let keypair = KeyPair::generate();
        let password = "correct_password";

        storage.save("test_wallet", &keypair, password).unwrap();

        // Try to load with wrong password
        let result = storage.load("test_wallet", "wrong_password");
        assert!(result.is_err());
    }

    #[test]
    fn test_wallet_storage_list() {
        let temp_dir = TempDir::new().unwrap();
        let storage = WalletStorage::new(temp_dir.path()).unwrap();

        let keypair = KeyPair::generate();
        storage.save("wallet1", &keypair, "password1").unwrap();
        storage.save("wallet2", &keypair, "password2").unwrap();

        let wallets = storage.list().unwrap();
        assert_eq!(wallets.len(), 2);
        assert!(wallets.contains(&"wallet1".to_string()));
        assert!(wallets.contains(&"wallet2".to_string()));
    }

    #[test]
    fn test_wallet_storage_delete() {
        let temp_dir = TempDir::new().unwrap();
        let mut storage = WalletStorage::new(temp_dir.path()).unwrap();

        let keypair = KeyPair::generate();
        storage.save("test_wallet", &keypair, "password").unwrap();

        assert!(storage.exists("test_wallet"));

        storage.delete("test_wallet").unwrap();
        assert!(!storage.exists("test_wallet"));
    }

    // ==================== Nonce Persistence Tests ====================

    #[test]
    fn test_nonce_persistence_basic() {
        let temp_dir = TempDir::new().unwrap();
        let mut storage = WalletStorage::new(temp_dir.path()).unwrap();
        let address = "test_address_123";

        // Initially nonce should not be used
        assert!(!storage.is_nonce_used(address, 0));
        assert_eq!(storage.get_next_nonce(address), 0);

        // Mark nonce as used
        let is_new = storage.mark_nonce_used(address, 0).unwrap();
        assert!(is_new);
        assert!(storage.is_nonce_used(address, 0));
        assert_eq!(storage.get_next_nonce(address), 1);

        // Mark same nonce again - should return false (already used)
        let is_new = storage.mark_nonce_used(address, 0).unwrap();
        assert!(!is_new);
    }

    #[test]
    fn test_nonce_replay_detection() {
        let mut storage = WalletStorage::new(TempDir::new().unwrap().path()).unwrap();
        let address = "test_address";

        // First use should succeed
        assert!(storage.validate_nonce(address, 0).is_ok());
        storage.mark_nonce_used(address, 0).unwrap();

        // Replay should be detected
        assert!(storage.validate_nonce(address, 0).is_err());
        assert!(storage.is_nonce_used(address, 0));

        // Different nonce should still be valid
        assert!(storage.validate_nonce(address, 1).is_ok());
    }

    #[test]
    fn test_nonce_persistence_across_restart() {
        let temp_dir = TempDir::new().unwrap();
        let path = temp_dir.path();

        // Create storage and mark nonces
        {
            let mut storage = WalletStorage::new(path).unwrap();
            storage.mark_nonce_used("addr1", 0).unwrap();
            storage.mark_nonce_used("addr1", 1).unwrap();
            storage.mark_nonce_used("addr2", 5).unwrap();
            // Storage drops here, should persist
        }

        // Create new storage instance (simulates restart)
        let storage2 = WalletStorage::new(path).unwrap();

        // Verify nonces persisted
        assert!(storage2.is_nonce_used("addr1", 0));
        assert!(storage2.is_nonce_used("addr1", 1));
        assert!(storage2.is_nonce_used("addr2", 5));
        assert!(!storage2.is_nonce_used("addr1", 2));
        assert_eq!(storage2.get_next_nonce("addr1"), 2);
        assert_eq!(storage2.get_next_nonce("addr2"), 6);
    }

    #[test]
    fn test_nonce_count() {
        let mut storage = WalletStorage::new(TempDir::new().unwrap().path()).unwrap();
        let address = "test_address";

        assert_eq!(storage.used_nonce_count(address), 0);

        storage.mark_nonce_used(address, 0).unwrap();
        storage.mark_nonce_used(address, 1).unwrap();
        storage.mark_nonce_used(address, 5).unwrap();

        assert_eq!(storage.used_nonce_count(address), 3);
    }
}
