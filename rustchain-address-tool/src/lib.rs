//! RustChain address generation library

use ed25519_dalek::{SigningKey, VerifyingKey};
use sha2::{Digest, Sha256};

/// Generate a new RustChain address from random bytes
pub fn generate_address() -> (String, String) {
    let mut csprng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut csprng);
    let public_key = signing_key.verifying_key();
    
    let address = address_from_public_key(&public_key);
    let private_key_hex = hex::encode(signing_key.to_bytes());
    let public_key_hex = hex::encode(public_key.to_bytes());
    
    (address, format!("{}:{}", private_key_hex, public_key_hex))
}

/// Generate address from a 32-byte private key hex
pub fn generate_from_private_key(private_key_hex: &str) -> Result<(String, String), String> {
    let bytes = hex::decode(private_key_hex).map_err(|e| format!("Invalid hex: {}", e))?;
    
    if bytes.len() != 32 {
        return Err("Private key must be 32 bytes".to_string());
    }
    
    let signing_key = SigningKey::from_bytes(bytes.as_slice().try_into().map_err(|_| "Invalid key")?);
    let public_key = signing_key.verifying_key();
    
    let address = address_from_public_key(&public_key);
    let public_key_hex = hex::encode(public_key.to_bytes());
    
    Ok((address, public_key_hex))
}

/// Generate address from a mnemonic phrase (simple derivation using double SHA256)
pub fn generate_from_mnemonic(mnemonic: &str) -> Result<(String, String), String> {
    let words: Vec<&str> = mnemonic.split_whitespace().collect();
    if words.len() < 12 {
        return Err("Mnemonic must be at least 12 words".to_string());
    }
    
    // Simple deterministic derivation: double SHA256 of mnemonic
    let mut hasher1 = Sha256::new();
    hasher1.update(mnemonic.as_bytes());
    let hash1 = hasher1.finalize();
    
    let mut hasher2 = Sha256::new();
    hasher2.update(&hash1);
    let seed = hasher2.finalize();
    
    let signing_key = SigningKey::from_bytes(seed.as_slice().try_into().map_err(|_| "Invalid seed")?);
    let public_key = signing_key.verifying_key();
    
    let address = address_from_public_key(&public_key);
    let public_key_hex = hex::encode(public_key.to_bytes());
    let private_key_hex = hex::encode(signing_key.to_bytes());
    
    Ok((address, private_key_hex))
}

/// Derive address from public key bytes
pub fn address_from_public_key(public_key: &VerifyingKey) -> String {
    let pub_bytes = public_key.to_bytes();
    let hash = Sha256::digest(&pub_bytes);
    let address_part = &hex::encode(hash)[..40];
    format!("RTC{}", address_part)
}

/// Validate a RustChain address format
pub fn validate_address(address: &str) -> bool {
    // Must start with RTC
    if !address.starts_with("RTC") {
        return false;
    }
    
    // Must be 43 characters (RTC + 40 hex chars)
    if address.len() != 43 {
        return false;
    }
    
    // Rest must be valid hex
    hex::decode(&address[3..]).is_ok()
}

/// Get address from public key hex
pub fn address_from_pubkey_hex(pub_hex: &str) -> Result<String, String> {
    let bytes = hex::decode(pub_hex).map_err(|e| format!("Invalid hex: {}", e))?;
    
    if bytes.len() != 32 {
        return Err("Public key must be 32 bytes".to_string());
    }
    
    let bytes32: [u8; 32] = bytes.try_into().map_err(|_| "Invalid key length")?;
    let verifying_key = VerifyingKey::from_bytes(&bytes32).map_err(|_| "Invalid key")?;
    Ok(address_from_public_key(&verifying_key))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_address() {
        let (address, keypair) = generate_address();
        assert!(address.starts_with("RTC"));
        assert_eq!(address.len(), 43);
        assert!(validate_address(&address));
        let parts: Vec<&str> = keypair.split(':').collect();
        assert_eq!(parts.len(), 2);
    }

    #[test]
    fn test_validate_address() {
        assert!(validate_address("RTC0000000000000000000000000000000000000000"));
        assert!(!validate_address("RTC000000000000000000000000000000000000000")); // too short
        assert!(!validate_address("RT0000000000000000000000000000000000000000")); // wrong prefix
        assert!(!validate_address("RTC000000000000000000000000000000000000000g")); // invalid hex
    }
}
