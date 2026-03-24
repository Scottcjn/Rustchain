//! Key management for RustChain Wallet
//!
//! This module provides secure key generation, storage, and signing capabilities
//! using Ed25519 elliptic curve cryptography.

use bs58;
use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use rand::rngs::OsRng;

use crate::error::{Result, WalletError};

/// A keypair containing both signing and verification keys
pub struct KeyPair {
    signing_key: SigningKey,
    verifying_key: VerifyingKey,
}

impl KeyPair {
    /// Generate a new random keypair
    pub fn generate() -> Self {
        let mut csprng = OsRng;
        let signing_key = SigningKey::generate(&mut csprng);
        let verifying_key = signing_key.verifying_key();

        Self {
            signing_key,
            verifying_key,
        }
    }

    /// Create a keypair from a raw secret key (32 bytes)
    pub fn from_bytes(bytes: &[u8]) -> Result<Self> {
        if bytes.len() != 32 {
            return Err(WalletError::InvalidKey(
                "Secret key must be 32 bytes".to_string(),
            ));
        }

        let mut key_bytes = [0u8; 32];
        key_bytes.copy_from_slice(bytes);

        let signing_key = SigningKey::from_bytes(&key_bytes);
        let verifying_key = signing_key.verifying_key();

        Ok(Self {
            signing_key,
            verifying_key,
        })
    }

    /// Create a keypair from a hex-encoded secret key
    pub fn from_hex(hex_str: &str) -> Result<Self> {
        let bytes = hex::decode(hex_str)?;
        Self::from_bytes(&bytes)
    }

    /// Create a keypair from a Base58-encoded secret key
    pub fn from_base58(base58_str: &str) -> Result<Self> {
        let bytes = bs58::decode(base58_str)
            .into_vec()
            .map_err(|e| WalletError::InvalidKey(format!("Invalid Base58: {}", e)))?;
        Self::from_bytes(&bytes)
    }

    /// Get the public key as a hex string
    pub fn public_key_hex(&self) -> String {
        hex::encode(self.verifying_key.as_bytes())
    }

    /// Get the public key as a Base58 string
    pub fn public_key_base58(&self) -> String {
        bs58::encode(self.verifying_key.as_bytes()).into_string()
    }

    /// Derive the RTC address: "RTC" + sha256(pubkey_bytes)[:40] (hex)
    pub fn rtc_address(&self) -> String {
        use sha2::{Digest, Sha256};
        let hash = Sha256::digest(self.verifying_key.as_bytes());
        let hex_hash = hex::encode(hash);
        format!("RTC{}", &hex_hash[..40])
    }

    /// Get the raw public key bytes
    pub fn public_key_bytes(&self) -> [u8; 32] {
        *self.verifying_key.as_bytes()
    }

    /// Sign a message with the private key
    pub fn sign(&self, message: &[u8]) -> Result<Vec<u8>> {
        let signature = self.signing_key.sign(message);
        Ok(signature.to_bytes().to_vec())
    }

    /// Verify a signature against a message
    pub fn verify(&self, message: &[u8], signature: &[u8]) -> Result<bool> {
        if signature.len() != 64 {
            return Err(WalletError::InvalidSignature(
                "Signature must be 64 bytes".to_string(),
            ));
        }

        let sig = Signature::from_slice(signature)
            .map_err(|e| WalletError::InvalidSignature(e.to_string()))?;

        match self.verifying_key.verify(message, &sig) {
            Ok(_) => Ok(true),
            Err(_) => Ok(false),
        }
    }

    /// Export the private key as a hex-encoded string
    pub fn export_private_key(&self) -> String {
        hex::encode(self.signing_key.as_bytes())
    }

    /// Export the private key as raw bytes
    pub fn export_private_key_bytes(&self) -> [u8; 32] {
        *self.signing_key.as_bytes()
    }

    /// Get a reference to the verifying key
    pub fn verifying_key(&self) -> &VerifyingKey {
        &self.verifying_key
    }
}

impl Clone for KeyPair {
    fn clone(&self) -> Self {
        let bytes = self.signing_key.as_bytes();
        Self::from_bytes(bytes).expect("Failed to clone keypair")
    }
}

impl Drop for KeyPair {
    fn drop(&mut self) {
        // Note: SigningKey from ed25519-dalek doesn't support zeroize directly
        // In production, consider using a wrapper or alternative implementation
    }
}

/// Derive a keypair from a mnemonic phrase using PBKDF2-HMAC-SHA512.
///
/// # Derivation Process
/// 1. **Seed generation**: PBKDF2 with 2048 iterations produces 64-byte seed
/// 2. **Path derivation**: HMAC-SHA512 applies the derivation path
/// 3. **Key extraction**: First 32 bytes of HMAC output become the secret key
/// 4. **Uniformity hash**: SHA512 ensures uniform key distribution
///
/// # Security Notes
/// - This is a **simplified** derivation (not full BIP32/BIP39 compliant)
/// - Production use should employ established libraries (bip32, bip39 crates)
/// - Optional passphrase support via salt: `format!("mnemonic{}", passphrase)`
///
/// # Arguments
/// * `mnemonic` - Space-separated mnemonic phrase (typically 12-24 words)
/// * `derivation_path` - Path string (e.g., "m/44'/0'/0'/0'/0'")
///
/// # Returns
/// * `Ok(KeyPair)` - Derived keypair
/// * `Err(WalletError::KeyDerivation)` - Invalid key length during derivation
pub fn derive_from_mnemonic(mnemonic: &str, derivation_path: &str) -> Result<KeyPair> {
    use hmac::{Hmac, Mac};
    use pbkdf2::pbkdf2_hmac;
    use sha2::{Digest, Sha512};

    type HmacSha512 = Hmac<Sha512>;

    // Generate seed from mnemonic
    let mut seed = [0u8; 64];
    let salt = format!("mnemonic{}", ""); // Can add passphrase here
    pbkdf2_hmac::<Sha512>(mnemonic.as_bytes(), salt.as_bytes(), 2048, &mut seed);

    // Simple derivation (not full BIP32)
    let mut mac = HmacSha512::new_from_slice(&seed)
        .map_err(|_| WalletError::KeyDerivation("Invalid key length".to_string()))?;
    mac.update(derivation_path.as_bytes());
    let result = mac.finalize();
    let derived = result.into_bytes();

    // Use first 32 bytes as secret key
    let mut secret_bytes = [0u8; 32];
    secret_bytes.copy_from_slice(&derived[..32]);

    // Hash to ensure uniform distribution
    let hash_output = Sha512::digest(secret_bytes);
    let mut key_bytes = [0u8; 32];
    key_bytes.copy_from_slice(&hash_output[..32]);

    KeyPair::from_bytes(&key_bytes)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_keypair_generation() {
        let keypair = KeyPair::generate();
        assert!(!keypair.public_key_hex().is_empty());
        assert!(!keypair.public_key_base58().is_empty());
        assert_eq!(keypair.public_key_hex().len(), 64); // 32 bytes hex
    }

    #[test]
    fn test_rtc_address_format() {
        let keypair = KeyPair::generate();
        let addr = keypair.rtc_address();
        assert!(addr.starts_with("RTC"));
        assert_eq!(addr.len(), 43); // "RTC" + 40 hex chars
        // Verify the hex portion is valid
        assert!(addr[3..].chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn test_rtc_address_deterministic() {
        let keypair = KeyPair::generate();
        let addr1 = keypair.rtc_address();
        let addr2 = keypair.rtc_address();
        assert_eq!(addr1, addr2);
    }

    #[test]
    fn test_keypair_from_hex() {
        // Generate a keypair and export it
        let original = KeyPair::generate();
        let hex = original.export_private_key();

        // Import from hex
        let imported = KeyPair::from_hex(&hex).unwrap();

        // Verify they match
        assert_eq!(original.public_key_hex(), imported.public_key_hex());
    }

    #[test]
    fn test_keypair_from_base58() {
        let original = KeyPair::generate();
        let base58 = bs58::encode(original.signing_key.as_bytes()).into_string();

        let imported = KeyPair::from_base58(&base58).unwrap();
        assert_eq!(original.public_key_hex(), imported.public_key_hex());
    }

    #[test]
    fn test_signing_and_verification() {
        let keypair = KeyPair::generate();
        let message = b"Test message for signing";

        let signature = keypair.sign(message).unwrap();
        assert_eq!(signature.len(), 64);

        let valid = keypair.verify(message, &signature).unwrap();
        assert!(valid);
    }

    #[test]
    fn test_invalid_signature_verification() {
        let keypair1 = KeyPair::generate();
        let keypair2 = KeyPair::generate();
        let message = b"Test message";

        let signature = keypair1.sign(message).unwrap();

        // Verify with wrong keypair should fail
        let valid = keypair2.verify(message, &signature).unwrap();
        assert!(!valid);
    }

    #[test]
    fn test_invalid_key_length() {
        let result = KeyPair::from_bytes(&[1u8; 16]); // Wrong length
        assert!(result.is_err());
    }

    #[test]
    fn test_derive_from_mnemonic() {
        let mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about";
        let keypair = derive_from_mnemonic(mnemonic, "m/44'/0'/0'/0'/0'").unwrap();
        assert!(!keypair.public_key_hex().is_empty());
    }
}
