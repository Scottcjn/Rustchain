//! RustChain Address Validator and Generator Library
//! 
//! This library provides utilities for validating and generating RTC addresses
//! on the RustChain network.

use ed25519_dalek::{SigningKey, VerifyingKey};
use rand::rngs::OsRng;
use sha2::{Digest, Sha256};

/// Prefix used for RustChain addresses
pub const ADDRESS_PREFIX: &str = "RTC";

/// Length of the address hash (without prefix)
pub const ADDRESS_HASH_LEN: usize = 32;

/// Validates an RTC address
/// 
/// # Arguments
/// * `address` - The address string to validate
/// 
/// # Returns
/// * `true` if the address is valid, `false` otherwise
pub fn validate_address(address: &str) -> bool {
    if !address.starts_with(ADDRESS_PREFIX) {
        return false;
    }
    
    let without_prefix = &address[3..];
    
    // Base58 decoded length should be: 32 (pubkey) + 4 (checksum) = 36
    let decoded = match bs58::decode(without_prefix).into_vec() {
        Ok(v) => v,
        Err(_) => return false,
    };
    
    if decoded.len() != 36 {
        return false;
    }
    
    // Split into pubkey and checksum
    let (pubkey, checksum) = decoded.split_at(32);
    
    // Calculate checksum on version byte + pubkey
    let mut payload = vec![0x00];
    payload.extend_from_slice(pubkey);
    let calculated_checksum = calculate_checksum(&payload);
    
    checksum == calculated_checksum.as_slice()
}

/// Generates a new random RTC address
/// 
/// # Returns
/// A tuple of (address, private_key_hex)
pub fn generate_address() -> (String, String) {
    let signing_key = SigningKey::generate(&mut OsRng);
    let verifying_key: VerifyingKey = (&signing_key).into();
    
    // Create payload with version byte + pubkey
    let mut payload = vec![0x00]; // Version byte
    payload.extend_from_slice(verifying_key.as_bytes());
    
    // Calculate checksum on the full payload (version + pubkey)
    let checksum = calculate_checksum(&payload);
    
    // Address is base58 of pubkey + checksum (no version byte in address)
    let address_bytes: Vec<u8> = verifying_key.as_bytes().iter().cloned().chain(checksum).collect();
    let address = format!("{}{}", ADDRESS_PREFIX, bs58::encode(&address_bytes).into_string());
    
    let private_key = hex::encode(signing_key.to_bytes());
    
    (address, private_key)
}

/// Generates address from a private key (hex)
/// 
/// # Arguments
/// * `private_key_hex` - The private key as a hex string
/// 
/// # Returns
/// The corresponding RTC address
pub fn address_from_private_key(private_key_hex: &str) -> Result<String, String> {
    let key_bytes = hex::decode(private_key_hex).map_err(|e| format!("Invalid hex: {}", e))?;
    
    if key_bytes.len() != 32 {
        return Err("Private key must be 32 bytes".to_string());
    }
    
    let key_array: [u8; 32] = key_bytes.try_into().map_err(|_| "Invalid key length")?;
    let signing_key = SigningKey::from_bytes(&key_array);
    let verifying_key: VerifyingKey = (&signing_key).into();
    
    // Create payload with version byte + pubkey
    let mut payload = vec![0x00]; // Version byte
    payload.extend_from_slice(verifying_key.as_bytes());
    
    // Calculate checksum on version + pubkey
    let checksum = calculate_checksum(&payload);
    
    // Address is base58 of pubkey + checksum
    let address_bytes: Vec<u8> = verifying_key.as_bytes().iter().cloned().chain(checksum).collect();
    let address = format!("{}{}", ADDRESS_PREFIX, bs58::encode(&address_bytes).into_string());
    
    Ok(address)
}

/// Calculates checksum for address payload
fn calculate_checksum(payload: &[u8]) -> Vec<u8> {
    let hash = Sha256::digest(payload);
    let hash2 = Sha256::digest(&hash);
    hash2[..4].to_vec()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_address() {
        let (address, private_key) = generate_address();
        assert!(address.starts_with("RTC"));
        assert_eq!(private_key.len(), 64);
    }

    #[test]
    fn test_validate_address() {
        let (address, _) = generate_address();
        assert!(validate_address(&address));
        
        assert!(!validate_address("INVALID"));
        assert!(!validate_address("RTCx"));
    }

    #[test]
    fn test_round_trip() {
        let (address, private_key) = generate_address();
        let derived = address_from_private_key(&private_key).unwrap();
        assert_eq!(address, derived);
    }
}
