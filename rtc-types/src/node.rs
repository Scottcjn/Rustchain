//! Node-related API types

use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

/// Node information response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeInfo {
    /// Node software version
    pub version: String,
    /// Chain identifier
    pub chain_id: String,
    /// Current epoch number
    pub current_epoch: u64,
    /// Number of connected peers
    pub peers: u32,
    /// Node uptime in seconds
    #[serde(rename = "uptimeSeconds")]
    pub uptime_seconds: u64,
}

/// Health check response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthResponse {
    /// Service status
    pub status: String,
    /// Timestamp of health check
    #[serde(with = "chrono::serde::ts_seconds")]
    pub timestamp: DateTime<Utc>,
    /// Optional database status
    #[serde(rename = "dbStatus")]
    pub db_status: Option<String>,
}

/// Block information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Block {
    /// Block hash
    pub hash: String,
    /// Block number/height
    pub number: u64,
    /// Timestamp
    #[serde(with = "chrono::serde::ts_seconds")]
    pub timestamp: DateTime<Utc>,
    /// Number of transactions
    pub tx_count: u32,
    /// Miner address
    pub miner: String,
    /// Previous block hash
    #[serde(rename = "parentHash")]
    pub parent_hash: String,
}

/// Transaction information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    /// Transaction hash
    pub hash: String,
    /// From address
    pub from: String,
    /// To address
    pub to: String,
    /// Amount in RTC
    pub value: String,
    /// Gas price
    #[serde(rename = "gasPrice")]
    pub gas_price: String,
    /// Transaction nonce
    pub nonce: u64,
    /// Block number
    #[serde(rename = "blockNumber")]
    pub block_number: u64,
    /// Transaction status
    pub status: String,
}

/// Network statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkStats {
    /// Total transactions
    #[serde(rename = "totalTx")]
    pub total_tx: u64,
    /// Total blocks
    #[serde(rename = "totalBlocks")]
    pub total_blocks: u64,
    /// Current gas price
    #[serde(rename = "gasPrice")]
    pub gas_price: String,
    /// Network hashrate (optional)
    #[serde(rename = "hashRate")]
    pub hash_rate: Option<String>,
}

/// Peer information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Peer {
    /// Peer ID
    pub id: String,
    /// Peer address
    pub address: String,
    /// Peer version
    pub version: String,
    /// Latency in milliseconds
    pub latency: u32,
    /// Connection status
    pub connected: bool,
}

/// Miner statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinerStats {
    /// Miner wallet address
    pub address: String,
    /// Total blocks mined
    pub blocks_mined: u64,
    /// Total rewards earned
    pub rewards: String,
    /// Current hashrate
    #[serde(rename = "hashRate")]
    pub hash_rate: String,
    /// Hardware fingerprint
    #[serde(rename = "hardwareFingerprint")]
    pub hardware_fingerprint: Option<String>,
    /// CPU architecture
    pub architecture: Option<String>,
}
