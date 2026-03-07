//! rtc-types - Shared types for RustChain API responses
//! 
//! This crate provides Serde-serializable types for interacting with
//! the RustChain blockchain API, including node endpoints, wallet operations,
//! and Proof-of-Antiquity data structures.
//!
//! ## Usage
//!
//! ```rust
//! use rtc_types::{NodeInfo, Balance, Epoch};
//! use serde_json::json;
//!
//! let node_info = NodeInfo {
//!     version: "2.2.1".to_string(),
//!     chain_id: "rustchain-mainnet".to_string(),
//!     current_epoch: 1337,
//!     peers: 42,
//!     uptime_seconds: 86400,
//! };
//! ```

pub mod node;
pub mod wallet;
pub mod epoch;
pub mod badges;

pub use node::*;
pub use wallet::*;
pub use badges::*;

/// Convenience re-export for common serialization
pub use serde::{Serialize, Deserialize};
