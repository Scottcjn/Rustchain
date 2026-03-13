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

pub mod config;
pub mod error;
pub mod hardware;
pub mod transport;
pub mod attestation;
pub mod miner;

pub use config::Config;
pub use error::{Result, MinerError};
pub use hardware::HardwareInfo;
pub use transport::NodeTransport;
pub use attestation::AttestationReport;
pub use miner::Miner;
