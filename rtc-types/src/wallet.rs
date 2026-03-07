//! Wallet-related API types

use serde::{Deserialize, Serialize};

/// Wallet balance response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Balance {
    /// Wallet address
    pub address: String,
    /// Balance in RTC (wei format)
    pub balance: String,
    /// Balance in human-readable format
    #[serde(rename = "balanceFormatted")]
    pub balance_formatted: Option<String>,
}

/// Wallet nonce
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Nonce {
    /// Wallet address
    pub address: String,
    /// Current nonce
    pub nonce: u64,
}

/// Transfer request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransferRequest {
    /// From address
    pub from: String,
    /// To address
    pub to: String,
    /// Amount in RTC
    pub value: String,
    /// Gas price (optional, defaults to network gas price)
    #[serde(rename = "gasPrice")]
    pub gas_price: Option<String>,
    /// Gas limit (optional)
    #[serde(rename = "gasLimit")]
    pub gas_limit: Option<u64>,
}

/// Transfer response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransferResponse {
    /// Transaction hash
    pub hash: String,
    /// Transaction nonce
    pub nonce: u64,
    /// Gas used
    #[serde(rename = "gasUsed")]
    pub gas_used: Option<String>,
}

/// Wallet creation request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateWalletRequest {
    /// Optional seed phrase (will generate if not provided)
    #[serde(rename = "seedPhrase")]
    pub seed_phrase: Option<String>,
}

/// Wallet creation response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalletResponse {
    /// Wallet address
    pub address: String,
    /// Public key
    #[serde(rename = "publicKey")]
    pub public_key: String,
    /// Private key (only for new wallets, not stored)
    #[serde(rename = "privateKey")]
    pub private_key: Option<String>,
    /// Seed phrase (if generated)
    #[serde(rename = "seedPhrase")]
    pub seed_phrase: Option<String>,
}

/// Transaction history entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionHistory {
    /// Transaction hash
    pub hash: String,
    /// Block number
    #[serde(rename = "blockNumber")]
    pub block_number: u64,
    /// Timestamp
    pub timestamp: i64,
    /// From address
    pub from: String,
    /// To address
    pub to: String,
    /// Value transferred
    pub value: String,
    /// Transaction status
    pub status: String,
}

/// Staking information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StakingInfo {
    /// Staker address
    pub address: String,
    /// Staked amount
    pub staked: String,
    /// Rewards earned
    pub rewards: String,
    /// Lock end time (epoch seconds)
    #[serde(rename = "lockEnd")]
    pub lock_end: i64,
    /// Is active
    pub active: bool,
}
