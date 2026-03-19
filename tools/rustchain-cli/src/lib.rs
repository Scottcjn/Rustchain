//! `rustchain-cli` library — shared types and API client for RustChain

pub mod address;
pub mod api;
pub mod wallet;

// Re-export commonly used types
pub use address::{RtcAddress, AddressError};
pub use api::{Client, ApiError, Miner, EpochInfo, NetworkStats, HealthStatus, BalanceResponse};
pub use wallet::{Wallet, WalletError};
