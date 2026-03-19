//! RTC Address generation and validation (Ed25519 + Base58)
//!
//! RustChain uses Ed25519 public keys encoded as base58check strings
//! for wallet addresses.
//!
//! ## Address Format
//! - Version byte: 0x00 (mainnet)
//! - Public key: 32 bytes Ed25519
//! - Checksum: 4 bytes SHA256(SHA256(version + pubkey))
//! - Encoding: Base58 with checksum appended

use anyhow::{anyhow, Context};
use base58::{FromBase58, ToBase58};
use ed25519_dalek::{PublicKey, SecretKey, Signer, SigningKey};
use rand::rngs::OsRng;
use sha2::{Digest, Sha256};

/// Length of an Ed25519 public key in bytes
pub const PUBKEY_LEN: usize = 32;
/// Length of an Ed25519 secret key in bytes
pub const SECRET_LEN: usize = 32;
/// Length of an RTC address in bytes (version + pubkey + checksum)
pub const ADDRESS_LEN: usize = 1 + PUBKEY_LEN + 4;

/// Error types for address operations
#[derive(Debug, thiserror::Error)]
pub enum AddressError {
    #[error("Invalid base58 encoding: {0}")]
    InvalidBase58(String),
    #[error("Invalid address length: expected {expected} bytes, got {got}")]
    InvalidLength { expected: usize, got: usize },
    #[error("Invalid checksum: expected {expected:?}, got {got:?}")]
    InvalidChecksum { expected: Vec<u8>, got: Vec<u8> },
    #[error("Invalid Ed25519 public key: {0}")]
    InvalidPublicKey(String),
    #[error("Invalid hex string: {0}")]
    InvalidHex(String),
    #[error("Invalid seed length: expected 32 or 64 bytes, got {0}")]
    InvalidSeedLength(usize),
}

/// An RTC blockchain address (base58-encoded Ed25519 public key with checksum)
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct RtcAddress {
    /// The base58-encoded address string
    pub as_string: String,
    /// Raw bytes (version + pubkey + checksum)
    pub bytes: [u8; ADDRESS_LEN],
    /// The underlying Ed25519 public key
    pub public_key: PublicKey,
}

impl RtcAddress {
    /// Generate a new random wallet (key pair)
    pub fn generate() -> (RtcAddress, [u8; SECRET_LEN]) {
        let signing_key = SigningKey::generate(&mut OsRng);
        let public_key = signing_key.verifying_key();
        let address = Self::from_public_key(public_key);
        (address, signing_key.to_bytes())
    }

    /// Create an address from an Ed25519 public key
    pub fn from_public_key(public_key: PublicKey) -> Self {
        let pubkey_bytes = public_key.as_bytes();
        let version_byte = [0x00]; // mainnet version
        let mut preimage = Vec::with_capacity(1 + PUBKEY_LEN);
        preimage.extend_from_slice(&version_byte);
        preimage.extend_from_slice(pubkey_bytes);

        let checksum = double_sha256(&preimage)[..4].to_vec();

        let mut bytes = [0u8; ADDRESS_LEN];
        bytes[0] = 0x00;
        bytes[1..1 + PUBKEY_LEN].copy_from_slice(pubkey_bytes);
        bytes[1 + PUBKEY_LEN..].copy_from_slice(&checksum);

        let as_string = bytes.to_base58();

        Self { as_string, bytes, public_key }
    }

    /// Create an address from a raw 32-byte secret key
    pub fn from_secret(secret: [u8; SECRET_LEN]) -> Self {
        let signing_key = SigningKey::from_bytes(&secret);
        Self::from_public_key(signing_key.verifying_key())
    }

    /// Parse an address from a base58 string
    pub fn parse(s: &str) -> Result<Self, AddressError> {
        let decoded = s.from_base58()
            .map_err(|e| AddressError::InvalidBase58(e.to_string()))?;

        if decoded.len() != ADDRESS_LEN {
            return Err(AddressError::InvalidLength {
                expected: ADDRESS_LEN,
                got: decoded.len(),
            });
        }

        let mut bytes = [0u8; ADDRESS_LEN];
        bytes.copy_from_slice(&decoded);

        // Verify checksum
        let preimage = &bytes[..1 + PUBKEY_LEN];
        let checksum_given = &bytes[1 + PUBKEY_LEN..];
        let checksum_expected = &double_sha256(preimage)[..4];

        if checksum_given != checksum_expected {
            return Err(AddressError::InvalidChecksum {
                expected: checksum_expected.to_vec(),
                got: checksum_given.to_vec(),
            });
        }

        // Reconstruct public key
        let pubkey_bytes: [u8; PUBKEY_LEN] = bytes[1..1 + PUBKEY_LEN]
            .try_into()
            .expect("pubkey slice has correct length");

        let public_key = PublicKey::from_bytes(&pubkey_bytes)
            .map_err(|e| AddressError::InvalidPublicKey(e.to_string()))?;

        Ok(Self {
            as_string: s.to_string(),
            bytes,
            public_key,
        })
    }

    /// Parse from hex private key
    pub fn from_hex_private_key(hex_key: &str) -> Result<Self, AddressError> {
        let hex_clean = hex_key.strip_prefix("0x").unwrap_or(hex_key);
        let bytes = hex::decode(hex_clean)
            .map_err(|e| AddressError::InvalidHex(e.to_string()))?;

        let secret: [u8; SECRET_LEN] = match bytes.len() {
            SECRET_LEN => bytes.try_into().expect("exact length"),
            64 => bytes[..SECRET_LEN].try_into().expect("first 32 bytes"),
            _ => return Err(AddressError::InvalidSeedLength(bytes.len())),
        };

        Ok(Self::from_secret(secret))
    }

    /// Parse from base58-encoded seed
    pub fn from_base58_seed(seed: &str) -> Result<Self, AddressError> {
        let decoded = seed.from_base58()
            .map_err(|e| AddressError::InvalidBase58(e.to_string()))?;

        let secret: [u8; SECRET_LEN] = match decoded.len() {
            SECRET_LEN => decoded.clone().try_into().expect("exact length"),
            64 => decoded[..SECRET_LEN].try_into().expect("first 32 bytes"),
            _ => return Err(AddressError::InvalidSeedLength(decoded.len())),
        };

        Ok(Self::from_secret(secret))
    }

    /// Get the underlying public key as a hex string
    pub fn public_key_hex(&self) -> String {
        self.public_key.as_bytes().iter().map(|b| format!("{:02x}", b)).collect()
    }

    /// Get a short representation of the address (first 6 + last 4 chars)
    pub fn short(&self) -> String {
        let s = &self.as_string;
        if s.len() <= 12 {
            s.to_string()
        } else {
            format!("{}…{}", &s[..6], &s[s.len() - 4..])
        }
    }

    /// Verify a signature made with this address's key
    pub fn verify(&self, message: &[u8], signature: &[u8]) -> bool {
        use ed25519_dalek::Signature;
        if signature.len() != 64 {
            return false;
        }
        let sig_array: [u8; 64] = match signature.try_into() {
            Ok(a) => a,
            Err(_) => return false,
        };
        let sig = Signature::from_bytes(&sig_array);
        self.public_key.verify(message, &sig).is_ok()
    }
}

impl std::fmt::Display for RtcAddress {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_string)
    }
}

/// Double SHA256 hash
fn double_sha256(data: &[u8]) -> Vec<u8> {
    let h1 = Sha256::digest(data);
    Sha256::digest(h1.as_slice()).to_vec()
}

/// Validate and display information about an address
pub fn validate_and_show(address: &str) -> anyhow::Result<()> {
    let addr = RtcAddress::parse(address)
        .with_context(|| format!("Invalid RTC address: {address}"))?;

    println!("✅ Valid RTC Address");
    println!("  Address:   {}", addr.as_string);
    println!("  Short:     {}", addr.short());
    println!("  PubKey:    {}…", &addr.public_key_hex()[..16]);
    println!("  Checksum:  OK (verified)");
    Ok(())
}

/// Validate an address string without displaying details
pub fn is_valid(s: &str) -> bool {
    RtcAddress::parse(s).is_ok()
}

// ─── Tests ─────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_address() {
        let (addr, secret) = RtcAddress::generate();
        assert_eq!(addr.as_string.len(), 44..=48); // base58 length for 37 bytes
        assert_eq!(secret.len(), 32);
    }

    #[test]
    fn test_address_roundtrip() {
        let (addr, _) = RtcAddress::generate();
        let parsed = RtcAddress::parse(&addr.as_string).unwrap();
        assert_eq!(addr.as_string, parsed.as_string);
        assert_eq!(addr.public_key.as_bytes(), parsed.public_key.as_bytes());
    }

    #[test]
    fn test_from_secret() {
        let (_, secret) = RtcAddress::generate();
        let addr = RtcAddress::from_secret(secret);
        assert!(is_valid(&addr.as_string));
    }

    #[test]
    fn test_invalid_address() {
        assert!(RtcAddress::parse("invalid").is_err());
        assert!(RtcAddress::parse("11111111111111111111111111111111").is_err()); // bad checksum
    }

    #[test]
    fn test_checksum_verification() {
        // Tamper with an address and verify checksum fails
        let (addr, _) = RtcAddress::generate();
        let mut chars: Vec<char> = addr.as_string.chars().collect();
        if chars[10].is_lowercase() { chars[10] = 'A'; } else { chars[10] = 'a'; }
        let tampered: String = chars.into_iter().collect();
        assert!(RtcAddress::parse(&tampered).is_err());
    }

    #[test]
    fn test_short_address() {
        let (addr, _) = RtcAddress::generate();
        let short = addr.short();
        assert!(short.contains("…") || short.len() <= 12);
        assert!(short.len() < addr.as_string.len());
    }
}
