//! RustChain Wallet - A robust native Rust wallet for RustChain
//!
//! This crate provides a complete wallet implementation for RustChain, including:
//! - Key generation and management (Ed25519)
//! - Secure key storage with encryption
//! - Transaction signing
//! - Balance queries and transfers
//! - CLI interface
//!
//! # Example
//!
//! ```rust,no_run
//! use rustchain_wallet::{Wallet, KeyPair};
//!
//! // Generate a new keypair
//! let keypair = KeyPair::generate();
//!
//! // Create a wallet
//! let wallet = Wallet::new(keypair);
//!
//! // Get the public address
//! let address = wallet.address();
//! println!("Wallet address: {}", address);
//! ```

pub mod error;
pub mod keys;
pub mod storage;
pub mod transaction;
pub mod client;
pub mod nonce_store;

pub use error::{Result, WalletError};
pub use keys::KeyPair;
pub use storage::WalletStorage;
pub use transaction::{Transaction, TransactionBuilder};
pub use client::RustChainClient;
pub use nonce_store::NonceStore;

/// Main wallet structure
#[derive(Clone)]
pub struct Wallet {
    keypair: KeyPair,
    network: Network,
}

/// Network types supported by the wallet
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Network {
    Mainnet,
    Testnet,
    Devnet,
}

impl Network {
    /// Get the RPC endpoint for this network
    pub fn rpc_url(&self) -> &'static str {
        match self {
            Network::Mainnet => "https://rpc.rustchain.org",
            Network::Testnet => "https://testnet-rpc.rustchain.org",
            Network::Devnet => "https://devnet-rpc.rustchain.org",
        }
    }

    /// Get the explorer URL for this network
    pub fn explorer_url(&self) -> &'static str {
        match self {
            Network::Mainnet => "https://explorer.rustchain.org",
            Network::Testnet => "https://testnet-explorer.rustchain.org",
            Network::Devnet => "https://devnet-explorer.rustchain.org",
        }
    }
}

impl std::fmt::Display for Network {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Network::Mainnet => write!(f, "mainnet"),
            Network::Testnet => write!(f, "testnet"),
            Network::Devnet => write!(f, "devnet"),
        }
    }
}

impl Wallet {
    /// Create a new wallet from a keypair
    pub fn new(keypair: KeyPair) -> Self {
        Self {
            keypair,
            network: Network::Mainnet,
        }
    }

    /// Create a new wallet with a specific network
    pub fn with_network(keypair: KeyPair, network: Network) -> Self {
        Self { keypair, network }
    }

    /// Generate a new wallet with a fresh keypair
    pub fn generate() -> Self {
        Self::new(KeyPair::generate())
    }

    /// Get the wallet's public address
    pub fn address(&self) -> String {
        self.keypair.public_key_base58()
    }

    /// Get the public key as hex
    pub fn public_key(&self) -> String {
        self.keypair.public_key_hex()
    }

    /// Get the network this wallet is configured for
    pub fn network(&self) -> Network {
        self.network
    }

    /// Sign a message with the wallet's private key
    pub fn sign(&self, message: &[u8]) -> Result<Vec<u8>> {
        self.keypair.sign(message)
    }

    /// Sign a message and return hex-encoded signature
    pub fn sign_hex(&self, message: &[u8]) -> Result<String> {
        let sig = self.sign(message)?;
        Ok(hex::encode(&sig))
    }

    /// Verify a signature against a message
    pub fn verify(&self, message: &[u8], signature: &[u8]) -> Result<bool> {
        self.keypair.verify(message, signature)
    }

    /// Export the private key (use with caution!)
    pub fn export_private_key(&self) -> String {
        self.keypair.export_private_key()
    }

    /// Get a reference to the keypair
    pub fn keypair(&self) -> &KeyPair {
        &self.keypair
    }

    /// Create a RustChain client for this wallet
    pub fn client(&self) -> RustChainClient {
        RustChainClient::new(self.network.rpc_url().to_string())
    }
}

impl std::fmt::Debug for Wallet {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Wallet")
            .field("address", &self.address())
            .field("network", &self.network)
            .finish()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_wallet_generation() {
        let wallet = Wallet::generate();
        assert!(!wallet.address().is_empty());
        // Base58 encoded Ed25519 public key is typically 43-44 characters
        assert!(wallet.address().len() >= 43);
    }

    #[test]
    fn test_wallet_signing() {
        let wallet = Wallet::generate();
        let message = b"Hello, RustChain!";

        let signature = wallet.sign(message).unwrap();
        assert_eq!(signature.len(), 64); // Ed25519 signature size

        let valid = wallet.verify(message, &signature).unwrap();
        assert!(valid);
    }

    #[test]
    fn test_wallet_network() {
        let wallet = Wallet::generate();
        assert_eq!(wallet.network(), Network::Mainnet);

        let wallet_testnet = Wallet::with_network(KeyPair::generate(), Network::Testnet);
        assert_eq!(wallet_testnet.network(), Network::Testnet);
    }

    #[test]
    fn test_network_rpc_urls() {
        assert_eq!(Network::Mainnet.rpc_url(), "https://rpc.rustchain.org");
        assert_eq!(Network::Testnet.rpc_url(), "https://testnet-rpc.rustchain.org");
        assert_eq!(Network::Devnet.rpc_url(), "https://devnet-rpc.rustchain.org");
    }

    #[test]
    fn test_network_explorer_urls() {
        assert_eq!(Network::Mainnet.explorer_url(), "https://explorer.rustchain.org");
        assert_eq!(Network::Testnet.explorer_url(), "https://testnet-explorer.rustchain.org");
        assert_eq!(Network::Devnet.explorer_url(), "https://devnet-explorer.rustchain.org");
    }

    #[test]
    fn test_network_display() {
        assert_eq!(format!("{}", Network::Mainnet), "mainnet");
        assert_eq!(format!("{}", Network::Testnet), "testnet");
        assert_eq!(format!("{}", Network::Devnet), "devnet");
    }
}
