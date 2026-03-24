//! Error types for RustChain Wallet

use thiserror::Error;

/// Result type alias for wallet operations
pub type Result<T> = std::result::Result<T, WalletError>;

/// Wallet error types
#[derive(Error, Debug)]
pub enum WalletError {
    #[error("Cryptographic error: {0}")]
    Crypto(String),

    #[error("Invalid key format: {0}")]
    InvalidKey(String),

    #[error("Invalid signature: {0}")]
    InvalidSignature(String),

    #[error("Invalid address: {0}")]
    InvalidAddress(String),

    #[error("Storage error: {0}")]
    Storage(String),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("Network error: {0}")]
    Network(String),

    #[error("Transaction error: {0}")]
    Transaction(String),

    #[error("Insufficient balance: required {required}, available {available}")]
    InsufficientBalance { required: u64, available: u64 },

    #[error("RPC error: {0}")]
    Rpc(String),

    #[error("Key derivation error: {0}")]
    KeyDerivation(String),

    #[error("Encryption error: {0}")]
    Encryption(String),

    #[error("Decryption error: {0}")]
    Decryption(String),

    #[error("Hex decode error: {0}")]
    HexDecode(#[from] hex::FromHexError),
}

impl From<ed25519_dalek::SignatureError> for WalletError {
    fn from(err: ed25519_dalek::SignatureError) -> Self {
        WalletError::Crypto(err.to_string())
    }
}
