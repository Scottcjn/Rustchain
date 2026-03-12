//! Error types for RIP-305 Cross-Chain Airdrop

use thiserror::Error;

/// Result type alias for airdrop operations
pub type Result<T> = std::result::Result<T, AirdropError>;

/// Airdrop error types
#[derive(Error, Debug)]
pub enum AirdropError {
    #[error("Configuration error: {0}")]
    Config(String),

    #[error("GitHub API error: {0}")]
    GitHub(String),

    #[error("GitHub verification failed: {0}")]
    GitHubVerification(String),

    #[error("Solana RPC error: {0}")]
    SolanaRpc(String),

    #[error("Base RPC error: {0}")]
    BaseRpc(String),

    #[error("Wallet verification failed: {0}")]
    WalletVerification(String),

    #[error("Bridge error: {0}")]
    Bridge(String),

    #[error("Claim error: {0}")]
    Claim(String),

    #[error("Eligibility check failed: {0}")]
    Eligibility(String),

    #[error("Network error: {0}")]
    Network(String),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),

    #[error("Parse error: {0}")]
    Parse(String),

    #[error("Validation error: {0}")]
    Validation(String),
}

impl From<String> for AirdropError {
    fn from(s: String) -> Self {
        AirdropError::Validation(s)
    }
}

impl From<&str> for AirdropError {
    fn from(s: &str) -> Self {
        AirdropError::Validation(s.to_string())
    }
}
