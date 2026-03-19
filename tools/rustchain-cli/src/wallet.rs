//! Wallet management — key generation, signing, address derivation
//!
//! ## Wallet Format
//!
//! Wallets are stored as YAML files with the following structure:
//!
//! ```yaml
//! version: 1
//! wallet: C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg
//! public_key: "ed25519:Abc..."
//! created: "2026-03-19T14:00:00Z"
//! chain: rustchain
//! ```
//!
//! The secret key is stored separately in a `.key` file (mode 0o600):
//!
//! ```yaml
//! version: 1
//! secret_key: "base58:..."

use crate::address::{self, RtcAddress};
use anyhow::Context;
use ed25519_dalek::{Signer, SigningKey};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

/// Wallet error types
#[derive(Debug, thiserror::Error)]
pub enum WalletError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Address error: {0}")]
    Address(#[from] address::AddressError),
    #[error("Wallet file not found: {0}")]
    NotFound(String),
    #[error("Invalid wallet format: {0}")]
    InvalidFormat(String),
    #[error("Signing error: {0}")]
    Signing(String),
}

/// A RustChain wallet — key pair + derived address
#[derive(Debug, Clone)]
pub struct Wallet {
    /// The RTC address (public key + checksum, base58)
    pub address: RtcAddress,
    /// The raw 32-byte Ed25519 signing key
    secret_bytes: [u8; 32],
    /// Creation timestamp
    pub created_at: chrono::DateTime<chrono::Utc>,
    /// Optional user-provided label
    pub label: Option<String>,
}

impl Wallet {
    /// Generate a brand-new random wallet
    pub fn generate() -> Self {
        let (address, secret_bytes) = RtcAddress::generate();
        Self {
            address,
            secret_bytes,
            created_at: chrono::Utc::now(),
            label: None,
        }
    }

    /// Create a wallet from a base58-encoded secret seed
    pub fn from_seed(seed: &str) -> Result<Self, WalletError> {
        let addr = RtcAddress::from_base58_seed(seed)
            .with_context(|| "Invalid base58 seed")?;
        let addr_clone = addr.clone();
        // Derive secret from seed (use seed directly as secret for deterministic wallets)
        let decoded = seed.from_base58()
            .map_err(|_| WalletError::InvalidFormat("Invalid base58 seed".to_string()))?;
        let secret_bytes: [u8; 32] = if decoded.len() >= 32 {
            decoded[..32].try_into().expect("first 32 bytes")
        } else {
            return Err(WalletError::InvalidFormat("Seed too short".to_string()));
        };
        Ok(Self {
            address: addr_clone,
            secret_bytes,
            created_at: chrono::Utc::now(),
            label: None,
        })
    }

    /// Load a wallet from a YAML file
    pub fn load(path: &Path) -> Result<Self, WalletError> {
        let content = fs::read_to_string(path)
            .with_context(|| format!("Failed to read wallet file: {}", path.display()))?;
        let meta: WalletFile = serde_yaml::from_str(&content)
            .with_context(|| "Failed to parse wallet YAML")?;

        let addr = RtcAddress::parse(&meta.wallet)
            .with_context(|| "Invalid wallet address in file")?;

        let created_at = meta.created
            .and_then(|c| chrono::DateTime::parse_from_rfc3339(&c).ok())
            .map(|dt| dt.with_timezone(&chrono::Utc))
            .unwrap_or_else(chrono::Utc::now);

        Ok(Self {
            address: addr,
            secret_bytes: [0u8; 32], // Not stored in wallet file for security
            created_at,
            label: meta.label,
        })
    }

    /// Save wallet metadata to a YAML file (no secret!)
    /// The secret key should be saved separately with restricted permissions.
    pub fn save(&self, path: &Path) -> Result<(), WalletError> {
        let meta = WalletFile {
            version: 1,
            wallet: self.address.as_string.clone(),
            public_key: format!("ed25519:{}", self.address.public_key_hex()),
            created: self.created_at.to_rfc3339(),
            chain: "rustchain".to_string(),
            label: self.label.clone(),
        };
        let yaml = serde_yaml::to_string(&meta)
            .with_context(|| "Failed to serialize wallet YAML")?;
        fs::write(path, yaml)
            .with_context(|| format!("Failed to write wallet file: {}", path.display()))?;
        Ok(())
    }

    /// Save the secret key to a separate file with mode 0o600
    pub fn save_secret(&self, path: &Path) -> Result<(), WalletError> {
        let secret_b58 = format!("base58:{}", self.secret_bytes.to_base58());
        let content = format!(
            "# RustChain secret key — KEEP THIS FILE PRIVATE!\n\
             version: 1\n\
             secret_key: {}\n",
            secret_b58
        );
        fs::write(path, content)
            .with_context(|| format!("Failed to write secret file: {}", path.display()))?;

        // Set file permissions to owner-read-only (0o600) where supported
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut perms = fs::Permissions::mode(0o600);
            fs::set_permissions(path, perms)?;
        }

        Ok(())
    }

    /// Get the signing key for transactions
    pub fn signing_key(&self) -> SigningKey {
        SigningKey::from_bytes(&self.secret_bytes)
    }

    /// Sign a message with this wallet's secret key
    pub fn sign(&self, message: &[u8]) -> Vec<u8> {
        let signing_key = self.signing_key();
        let signature = signing_key.sign(message);
        signature.to_bytes().to_vec()
    }

    /// Get the wallet's RTC address string
    pub fn address_string(&self) -> &str {
        &self.address.as_string
    }

    /// Set a human-readable label
    pub fn set_label(&mut self, label: &str) {
        self.label = Some(label.to_string());
    }
}

impl std::fmt::Display for Wallet {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        writeln!(f, "RustChain Wallet")?;
        writeln!(f, "  Address: {}", self.address)?;
        writeln!(f, "  PubKey:  {}…", &self.address.public_key_hex()[..16])?;
        writeln!(f, "  Created: {}", self.created_at.to_rfc3339())?;
        if let Some(ref l) = self.label {
            writeln!(f, "  Label:   {l}")?;
        }
        Ok(())
    }
}

/// Wallet file format (YAML)
#[derive(Debug, Serialize, Deserialize)]
struct WalletFile {
    version: u32,
    wallet: String,
    #[serde(rename = "public_key")]
    public_key: String,
    #[serde(rename = "created")]
    created: Option<String>,
    #[serde(rename = "chain")]
    chain: String,
    #[serde(rename = "label")]
    label: Option<String>,
}

// ─── CLI subcommands ───────────────────────────────────────────────────────

use clap::Subcommand;

pub enum WalletAction {
    Generate,
    FromSeed { seed: String },
    FromHex { private_key: String },
    PubkeyToAddress { pubkey: String },
}

pub fn run(action: WalletAction) -> anyhow::Result<()> {
    match action {
        WalletAction::Generate => {
            let wallet = Wallet::generate();
            println!("✅ New RustChain Wallet Generated");
            println!("{}", wallet);
            println!();
            println!("⚠️  IMPORTANT: Save your wallet file and secret key!");
            println!("   Wallet address: {}", wallet.address);
            println!();
            println!("To save:");
            println!("   rustchain wallet save --wallet {} --path ./wallet.yaml", wallet.address);
            Ok(())
        }
        WalletAction::FromSeed { seed } => {
            let wallet = Wallet::from_seed(&seed)?;
            println!("✅ Wallet loaded from seed");
            println!("{}", wallet);
            Ok(())
        }
        WalletAction::FromHex { private_key } => {
            let addr = address::RtcAddress::from_hex_private_key(&private_key)?;
            println!("✅ Address derived from hex private key");
            println!("  Address: {}", addr);
            println!("  PubKey:  {}…", &addr.public_key_hex()[..16]);
            Ok(())
        }
        WalletAction::PubkeyToAddress { pubkey } => {
            let hex_clean = pubkey.strip_prefix("0x").unwrap_or(&pubkey);
            let bytes = hex::decode(hex_clean)
                .with_context(|| "Invalid hex public key")?;
            if bytes.len() != 32 {
                anyhow::bail!("Public key must be 32 bytes (64 hex chars), got {}", bytes.len());
            }
            let pubkey_arr: [u8; 32] = bytes.try_into().expect("exact length");
            use ed25519_dalek::PublicKey;
            let pk = PublicKey::from_bytes(&pubkey_arr)
                .with_context(|| "Invalid Ed25519 public key")?;
            let addr = address::RtcAddress::from_public_key(pk);
            println!("{}", addr);
            Ok(())
        }
    }
}

// ─── Tests ─────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_wallet() {
        let wallet = Wallet::generate();
        assert!(!wallet.address.as_string.is_empty());
        assert!(wallet.address.as_string.len() >= 40);
    }

    #[test]
    fn test_sign_and_verify() {
        let wallet = Wallet::generate();
        let message = b"Hello from RustChain!";
        let sig = wallet.sign(message);
        assert_eq!(sig.len(), 64);
        assert!(wallet.address.verify(message, &sig));
    }

    #[test]
    fn test_wallet_display() {
        let wallet = Wallet::generate();
        let s = format!("{}", wallet);
        assert!(s.contains("RustChain Wallet"));
        assert!(s.contains(&wallet.address));
    }
}
