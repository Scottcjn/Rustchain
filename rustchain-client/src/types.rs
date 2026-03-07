//! RustChain API types
//!
//! Shared types for RustChain API responses including health, epoch,
//! miners, wallet, and governance data structures.

use serde::{Deserialize, Serialize};

/// Network health response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub timestamp: Option<i64>,
    #[serde(default)]
    pub version: Option<String>,
}

/// Epoch information response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EpochResponse {
    pub epoch: u64,
    pub start_time: Option<i64>,
    pub end_time: Option<i64>,
    pub reward_pool: Option<String>,
    pub total_miners: Option<u64>,
}

/// Miner information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Miner {
    pub id: String,
    pub wallet: String,
    pub hardware_type: Option<String>,
    pub antiquity: Option<f64>,
    pub last_attestation: Option<i64>,
    pub rewards: Option<String>,
}

/// List of active miners
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MinersResponse {
    pub miners: Vec<Miner>,
    pub total: Option<u64>,
}

/// Wallet balance response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BalanceResponse {
    pub miner_id: String,
    pub balance: String,
    pub pending_rewards: Option<String>,
    pub last_updated: Option<i64>,
}

/// Governance proposal
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Proposal {
    pub id: u64,
    pub title: String,
    pub description: String,
    pub status: String,
    pub created_at: Option<i64>,
    pub vote_yes: Option<String>,
    pub vote_no: Option<String>,
}

/// List of governance proposals
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProposalsResponse {
    pub proposals: Vec<Proposal>,
}

/// Detailed proposal information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProposalDetail {
    pub id: u64,
    pub title: String,
    pub description: String,
    pub status: String,
    pub creator: Option<String>,
    pub created_at: Option<i64>,
    pub ended_at: Option<i64>,
    pub vote_yes: String,
    pub vote_no: String,
    pub voters: Option<Vec<Vote>>,
}

/// Individual vote record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Vote {
    pub voter: String,
    pub vote: String,
    pub weight: String,
    pub timestamp: Option<i64>,
}
