//! Configuration management with environment variable support

use serde::{Deserialize, Serialize};
use std::time::Duration;

/// Miner configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    /// Node URL (HTTPS direct or HTTP proxy)
    #[serde(default = "default_node_url")]
    pub node_url: String,

    /// Optional HTTP proxy URL for legacy systems
    #[serde(default)]
    pub proxy_url: Option<String>,

    /// Wallet address (auto-generated if not provided)
    #[serde(default)]
    pub wallet: Option<String>,

    /// Custom miner ID (auto-generated if not provided)
    #[serde(default)]
    pub miner_id: Option<String>,

    /// Block time in seconds (default: 600 = 10 minutes)
    #[serde(default = "default_block_time")]
    pub block_time_secs: u64,

    /// Attestation TTL in seconds (default: 580)
    #[serde(default = "default_attestation_ttl")]
    pub attestation_ttl_secs: u64,

    /// Health check interval in seconds
    #[serde(default = "default_health_interval")]
    pub health_interval_secs: u64,

    /// Request timeout in seconds
    #[serde(default = "default_timeout")]
    pub timeout_secs: u64,

    /// Enable dry-run mode (no network calls)
    #[serde(default)]
    pub dry_run: bool,

    /// Enable verbose logging
    #[serde(default)]
    pub verbose: bool,
}

fn default_node_url() -> String {
    "https://50.28.86.131".to_string()
}

fn default_block_time() -> u64 {
    600
}

fn default_attestation_ttl() -> u64 {
    580
}

fn default_health_interval() -> u64 {
    30
}

fn default_timeout() -> u64 {
    15
}

impl Default for Config {
    fn default() -> Self {
        Self {
            node_url: default_node_url(),
            proxy_url: None,
            wallet: None,
            miner_id: None,
            block_time_secs: default_block_time(),
            attestation_ttl_secs: default_attestation_ttl(),
            health_interval_secs: default_health_interval(),
            timeout_secs: default_timeout(),
            dry_run: false,
            verbose: false,
        }
    }
}

impl Config {
    /// Load configuration from environment variables
    ///
    /// Environment variables:
    /// - RUSTCHAIN_NODE_URL: Node URL
    /// - RUSTCHAIN_PROXY_URL: HTTP proxy URL
    /// - RUSTCHAIN_WALLET: Wallet address
    /// - RUSTCHAIN_MINER_ID: Custom miner ID
    /// - RUSTCHAIN_BLOCK_TIME: Block time in seconds
    /// - RUSTCHAIN_ATTESTATION_TTL: Attestation TTL in seconds
    /// - RUSTCHAIN_DRY_RUN: Enable dry-run mode (true/false)
    /// - RUSTCHAIN_VERBOSE: Enable verbose logging (true/false)
    pub fn from_env() -> crate::Result<Self> {
        // Load .env file if present
        let _ = dotenvy::dotenv();

        let mut config = Config::default();

        if let Ok(val) = std::env::var("RUSTCHAIN_NODE_URL") {
            config.node_url = val;
        }

        if let Ok(val) = std::env::var("RUSTCHAIN_PROXY_URL") {
            config.proxy_url = Some(val);
        }

        if let Ok(val) = std::env::var("RUSTCHAIN_WALLET") {
            config.wallet = Some(val);
        }

        if let Ok(val) = std::env::var("RUSTCHAIN_MINER_ID") {
            config.miner_id = Some(val);
        }

        if let Ok(val) = std::env::var("RUSTCHAIN_BLOCK_TIME") {
            if let Ok(secs) = val.parse() {
                config.block_time_secs = secs;
            }
        }

        if let Ok(val) = std::env::var("RUSTCHAIN_ATTESTATION_TTL") {
            if let Ok(secs) = val.parse() {
                config.attestation_ttl_secs = secs;
            }
        }

        if let Ok(val) = std::env::var("RUSTCHAIN_DRY_RUN") {
            config.dry_run = val.to_lowercase() == "true" || val == "1";
        }

        if let Ok(val) = std::env::var("RUSTCHAIN_VERBOSE") {
            config.verbose = val.to_lowercase() == "true" || val == "1";
        }

        Ok(config)
    }

    /// Get request timeout as Duration
    pub fn timeout(&self) -> Duration {
        Duration::from_secs(self.timeout_secs)
    }

    /// Get health check interval as Duration
    pub fn health_interval(&self) -> Duration {
        Duration::from_secs(self.health_interval_secs)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = Config::default();
        assert_eq!(config.node_url, "https://50.28.86.131");
        assert_eq!(config.block_time_secs, 600);
        assert_eq!(config.attestation_ttl_secs, 580);
        assert!(!config.dry_run);
    }
}
