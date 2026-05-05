// SPDX-License-Identifier: Apache-2.0


use std::error::Error;
use std::fmt;
use rand::RngCore;
use rand::rngs::OsRng;
use sha2::{Sha256, Sha512, Digest};
use hmac::{Hmac, Mac};
use aes_gcm::{
    aead::{Aead, KeyInit, OsRng as AeadOsRng},
    Aes256Gcm, Nonce
};
use chacha20poly1305::{ChaCha20Poly1305, Key, Nonce as ChaNonce};
use serde::{Serialize, Deserialize};
use log::{info, warn, error};

/// Error type for encryption operations
#[derive(Debug)]
pub enum EncryptionError {
    KeyGenerationError(String),
    EncryptionError(String),
    DecryptionError(String),
    InvalidKeySize,
    InvalidNonceSize,
}

impl fmt::Display for EncryptionError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            EncryptionError::KeyGenerationError(msg) => write!(f, "Key generation error: {}", msg),
            EncryptionError::EncryptionError(msg) => write!(f, "Encryption error: {}", msg),
            EncryptionError::DecryptionError(msg) => write!(f, "Decryption error: {}", msg),
            EncryptionError::InvalidKeySize => write!(f, "Invalid key size"),
            EncryptionError::InvalidNonceSize => write!(f, "Invalid nonce size"),
        }
    }
}

impl Error for EncryptionError {}

/// Encryption module
pub struct Encryption;

impl Encryption {
    /// Generate a cryptographically secure random key
    pub fn generate_key(size: usize) -> Result<Vec<u8>, EncryptionError> {
        if size == 0 {
            return Err(EncryptionError::InvalidKeySize);
        }

        let mut key = vec![0u8; size];
        OsRng.fill_bytes(&mut key);

        Ok(key)
    }

    /// Generate a secure random nonce
    pub fn generate_nonce(size: usize) -> Result<Vec<u8>, EncryptionError> {
        if size == 0 {
            return Err(EncryptionError::InvalidNonceSize);
        }

        let mut nonce = vec![0u8; size];
        OsRng.fill_bytes(&mut nonce);

        Ok(nonce)
    }

    /// Hash data using SHA-256
    pub fn sha256(data: &[u8]) -> Vec<u8> {
        let mut hasher = Sha256::new();
        hasher.update(data);
        hasher.finalize().to_vec()
    }

    /// Hash data using SHA-512
    pub fn sha512(data: &[u8]) -> Vec<u8> {
        let mut hasher = Sha512::new();
        hasher.update(data);
        hasher.finalize().to_vec()
    }

    /// Generate HMAC using SHA-256
    pub fn hmac_sha256(key: &[u8], data: &[u8]) -> Result<Vec<u8>, EncryptionError> {
        type HmacSha256 = Hmac<Sha256>;

        let mut mac = HmacSha256::new_from_slice(key)
            .map_err(|_| EncryptionError::InvalidKeySize)?;

        mac.update(data);
        Ok(mac.finalize().into_bytes().to_vec())
    }

    /// Encrypt data using AES-256-GCM
    pub fn aes256gcm_encrypt(key: &[u8], plaintext: &[u8]) -> Result<(Vec<u8>, Vec<u8>), EncryptionError> {
        // Validate key size
        if key.len() != 32 {
            return Err(EncryptionError::InvalidKeySize);
        }

        // Generate a random nonce
        let nonce = AeadOsRng.gen::<[u8; 12]>();

        // Create cipher
        let cipher = Aes256Gcm::new_from_slice(key)
            .map_err(|_| EncryptionError::InvalidKeySize)?;

        // Encrypt
        let ciphertext = cipher.encrypt(Nonce::from_slice(&nonce), plaintext)
            .map_err(|e| EncryptionError::EncryptionError(e.to_string()))?;

        Ok((ciphertext, nonce.to_vec()))
    }

    /// Decrypt data using AES-256-GCM
    pub fn aes256gcm_decrypt(key: &[u8], ciphertext: &[u8], nonce: &[u8]) -> Result<Vec<u8>, EncryptionError> {
        // Validate key size
        if key.len() != 32 {
            return Err(EncryptionError::InvalidKeySize);
        }

        // Validate nonce size
        if nonce.len() != 12 {
            return Err(EncryptionError::InvalidNonceSize);
        }

        // Create cipher
        let cipher = Aes256Gcm::new_from_slice(key)
            .map_err(|_| EncryptionError::InvalidKeySize)?;

        // Decrypt
        let plaintext = cipher.decrypt(Nonce::from_slice(nonce), ciphertext)
            .map_err(|e| EncryptionError::DecryptionError(e.to_string()))?;

        Ok(plaintext)
    }

    /// Encrypt data using ChaCha20-Poly1305
    pub fn chacha20poly1305_encrypt(key: &[u8], plaintext: &[u8]) -> Result<(Vec<u8>, Vec<u8>), EncryptionError> {
        // Validate key size
        if key.len() != 32 {
            return Err(EncryptionError::InvalidKeySize);
        }

        // Generate a random nonce
        let mut nonce_bytes = [0u8; 12];
        OsRng.fill_bytes(&mut nonce_bytes);

        // Create cipher
        let key = Key::from_slice(key);
        let cipher = ChaCha20Poly1305::new(key);

        // Encrypt
        let ciphertext = cipher.encrypt(ChaNonce::from_slice(&nonce_bytes), plaintext)
            .map_err(|e| EncryptionError::EncryptionError(e.to_string()))?;

        Ok((ciphertext, nonce_bytes.to_vec()))
    }

    /// Decrypt data using ChaCha20-Poly1305
    pub fn chacha20poly1305_decrypt(key: &[u8], ciphertext: &[u8], nonce: &[u8]) -> Result<Vec<u8>, EncryptionError> {
        // Validate key size
        if key.len() != 32 {
            return Err(EncryptionError::InvalidKeySize);
        }

        // Validate nonce size
        if nonce.len() != 12 {
            return Err(EncryptionError::InvalidNonceSize);
        }

        // Create cipher
        let key = Key::from_slice(key);
        let cipher = ChaCha20Poly1305::new(key);

        // Decrypt
        let plaintext = cipher.decrypt(ChaNonce::from_slice(nonce), ciphertext)
            .map_err(|e| EncryptionError::DecryptionError(e.to_string()))?;

        Ok(plaintext)
    }

    /// Derive a key from a password using PBKDF2
    pub fn derive_key_from_password(password: &str, salt: &[u8], iterations: u32, key_length: usize) -> Vec<u8> {
        use pbkdf2::pbkdf2_hmac_array;

        let mut key = vec![0u8; key_length];
        pbkdf2_hmac_array::<Sha256, 32>(
            password.as_bytes(),
            salt,
            iterations,
            &mut key
        );

        key
    }

    /// Generate a secure random salt
    pub fn generate_salt(size: usize) -> Result<Vec<u8>, EncryptionError> {
        if size == 0 {
            return Err(EncryptionError::InvalidKeySize);
        }

        let mut salt = vec![0u8; size];
        OsRng.fill_bytes(&mut salt);

        Ok(salt)
    }
}

/// Secure data wrapper that automatically encrypts/decrypts sensitive data
#[derive(Debug, Serialize, Deserialize)]
pub struct SecureData<T: Serialize + for<'a> Deserialize<'a>> {
    ciphertext: Vec<u8>,
    nonce: Vec<u8>,
    _phantom: std::marker::PhantomData<T>,
}

impl<T: Serialize + for<'a> Deserialize<'a>> SecureData<T> {
    /// Create a new SecureData instance by encrypting the data
    pub fn new(data: &T, key: &[u8]) -> Result<Self, EncryptionError> {
        let serialized = serde_json::to_vec(data)
            .map_err(|e| EncryptionError::EncryptionError(e.to_string()))?;

        let (ciphertext, nonce) = Encryption::aes256gcm_encrypt(key, &serialized)?;

        Ok(SecureData {
            ciphertext,
            nonce,
            _phantom: std::marker::PhantomData,
        })
    }

    /// Decrypt the data
    pub fn decrypt(&self, key: &[u8]) -> Result<T, EncryptionError> {
        let decrypted = Encryption::aes256gcm_decrypt(key, &self.ciphertext, &self.nonce)?;

        serde_json::from_slice(&decrypted)
            .map_err(|e| EncryptionError::DecryptionError(e.to_string()))
    }
}

