//! RustChain Miner - Production-ready Rust implementation
//!
//! This crate provides a complete miner implementation for RustChain, including:
//! - Hardware fingerprint attestation (RIP-PoA)
//! - Challenge/response protocol
//! - Epoch enrollment
//! - Mining loop with health checks
//!
//! # Example
//!
//! ```rust,no_run
//! use rustchain_miner::{Miner, Config};
//!
//! #[tokio::main]
//! async fn main() -> anyhow::Result<()> {
//!     let config = Config::from_env()?;
//!     let miner = Miner::new(config).await?;
//!     miner.run().await?;
//!     Ok(())
//! }
//! ```

pub mod attestation;
pub mod config;
pub mod error;
pub mod hardware;
pub mod miner;
pub mod transport;

#[cfg(test)]
mod arch_tests;

pub use attestation::AttestationReport;
pub use config::Config;
pub use error::{MinerError, Result};
pub use hardware::HardwareInfo;
pub use miner::Miner;
pub use transport::NodeTransport;
