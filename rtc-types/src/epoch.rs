//! Epoch-related API types for Proof-of-Antiquity

use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

/// Epoch information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Epoch {
    /// Epoch number
    pub number: u64,
    /// Start timestamp
    #[serde(with = "chrono::serde::ts_seconds")]
    pub start_time: DateTime<Utc>,
    /// End timestamp
    #[serde(with = "chrono::serde::ts_seconds")]
    pub end_time: DateTime<Utc>,
    /// Total transactions in epoch
    pub transactions: u64,
    /// Total rewards distributed
    pub rewards: String,
    /// Number of blocks produced
    pub blocks: u64,
    /// Number of active miners
    pub miners: u32,
}

/// Epoch leaderboard entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EpochLeaderboardEntry {
    /// Rank
    pub rank: u32,
    /// Miner address
    pub address: String,
    /// Blocks produced
    pub blocks: u64,
    /// Total rewards earned
    pub rewards: String,
    /// Hardware fingerprint
    #[serde(rename = "hardwareFingerprint")]
    pub hardware_fingerprint: Option<String>,
    /// CPU architecture
    pub architecture: Option<String>,
    /// Vintage CPU multiplier
    pub multiplier: f64,
}

/// Antiquity attestation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Attestation {
    /// Attestation ID
    pub id: String,
    /// Validator address
    pub validator: String,
    /// Hardware fingerprint
    #[serde(rename = "hardwareFingerprint")]
    pub hardware_fingerprint: String,
    /// CPU architecture
    pub architecture: String,
    /// Epoch attested
    pub epoch: u64,
    /// Attestation timestamp
    #[serde(with = "chrono::serde::ts_seconds")]
    pub timestamp: DateTime<Utc>,
    /// Signature
    pub signature: String,
    /// Multiplier applied
    pub multiplier: f64,
}

/// Proof-of-Antiquity data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofOfAntiquity {
    /// Epoch number
    pub epoch: u64,
    /// Hardware fingerprint
    #[serde(rename = "hardwareFingerprint")]
    pub hardware_fingerprint: String,
    /// Age in days
    pub age_days: u64,
    /// Attestations
    pub attestations: Vec<Attestation>,
    /// Combined signature
    pub signature: String,
    /// Multiplier (based on CPU vintage)
    pub multiplier: f64,
}

/// Hardware fingerprint profile
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareProfile {
    /// Fingerprint hash
    pub fingerprint: String,
    /// CPU model
    pub model: String,
    /// CPU architecture
    pub architecture: String,
    /// Family
    pub family: Option<String>,
    /// Vendor
    pub vendor: Option<String>,
    /// Frequency in MHz
    pub frequency_mhz: Option<u32>,
    /// Core count
    pub cores: Option<u32>,
    /// Age estimate in years
    pub age_years: Option<f64>,
    /// Vintage multiplier
    pub multiplier: f64,
    /// Classification
    pub classification: String,
}

/// Epoch settlement
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EpochSettlement {
    /// Epoch number
    pub epoch: u64,
    /// Settlement timestamp
    #[serde(with = "chrono::serde::ts_seconds")]
    pub timestamp: DateTime<Utc>,
    /// Total rewards distributed
    pub total_rewards: String,
    /// Number of validators
    pub validators: u32,
    /// Block rewards
    #[serde(rename = "blockRewards")]
    pub block_rewards: String,
    /// Vintage bonuses
    #[serde(rename = "vintageBonuses")]
    pub vintage_bonuses: String,
    /// Settlement status
    pub status: String,
}
