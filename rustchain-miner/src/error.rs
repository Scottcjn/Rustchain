//! Error types for RustChain Miner

use thiserror::Error;

/// Result type alias for miner operations
pub type Result<T> = std::result::Result<T, MinerError>;

/// Miner error types
#[derive(Error, Debug)]
pub enum MinerError {
    #[error("Configuration error: {0}")]
    Config(String),

    #[error("Hardware detection failed: {0}")]
    Hardware(String),

    #[error("Network error: {0}")]
    Network(String),

    #[error("Attestation failed: {0}")]
    Attestation(String),

    #[error("Enrollment failed: {0}")]
    Enrollment(String),

    #[error("Mining error: {0}")]
    Mining(String),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),
}
