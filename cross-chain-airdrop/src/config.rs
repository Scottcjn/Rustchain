//! Configuration management for RIP-305 Cross-Chain Airdrop

use serde::{Deserialize, Serialize};
use std::time::Duration;

/// Airdrop configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AirdropConfig {
    /// RustChain node URL for bridge operations
    #[serde(default = "default_node_url")]
    pub node_url: String,

    /// Bridge API base URL
    #[serde(default = "default_bridge_url")]
    pub bridge_url: String,

    /// Solana RPC URL (mainnet or devnet)
    #[serde(default = "default_solana_rpc")]
    pub solana_rpc_url: String,

    /// Base RPC URL (mainnet)
    #[serde(default = "default_base_rpc")]
    pub base_rpc_url: String,

    /// GitHub API base URL
    #[serde(default = "default_github_api")]
    pub github_api_url: String,

    /// GitHub OAuth token for API access
    #[serde(default)]
    pub github_token: Option<String>,

    /// wRTC Solana mint address
    #[serde(default)]
    pub wrtc_solana_mint: Option<String>,

    /// wRTC Base ERC-20 contract address
    #[serde(default)]
    pub wrtc_base_contract: Option<String>,

    /// Minimum SOL balance for eligibility (in lamports)
    #[serde(default = "default_min_sol_lamports")]
    pub min_sol_lamports: u64,

    /// Minimum ETH balance for eligibility (in wei)
    #[serde(default = "default_min_eth_wei")]
    pub min_eth_wei: u64,

    /// Minimum wallet age in seconds (7 days default)
    #[serde(default = "default_wallet_age_seconds")]
    pub min_wallet_age_seconds: u64,

    /// Minimum GitHub account age in seconds (30 days default)
    #[serde(default = "default_github_age_seconds")]
    pub min_github_age_seconds: u64,

    /// Request timeout in seconds
    #[serde(default = "default_timeout")]
    pub timeout_secs: u64,

    /// Enable dry-run mode (no actual transactions)
    #[serde(default)]
    pub dry_run: bool,

    /// Enable verbose logging
    #[serde(default)]
    pub verbose: bool,

    /// Admin key for bridge operations (optional, for admin CLI)
    #[serde(default)]
    pub admin_key: Option<String>,
}

fn default_node_url() -> String {
    "https://50.28.86.131".to_string()
}

fn default_bridge_url() -> String {
    "http://localhost:8096".to_string()
}

fn default_solana_rpc() -> String {
    "https://api.mainnet-beta.solana.com".to_string()
}

fn default_base_rpc() -> String {
    "https://mainnet.base.org".to_string()
}

fn default_github_api() -> String {
    "https://api.github.com".to_string()
}

fn default_min_sol_lamports() -> u64 {
    // 0.1 SOL = 100,000,000 lamports
    100_000_000
}

fn default_min_eth_wei() -> u64 {
    // 0.01 ETH = 10,000,000,000,000,000 wei
    10_000_000_000_000_000
}

fn default_wallet_age_seconds() -> u64 {
    // 7 days
    7 * 24 * 60 * 60
}

fn default_github_age_seconds() -> u64 {
    // 30 days
    30 * 24 * 60 * 60
}

fn default_timeout() -> u64 {
    30
}

impl Default for AirdropConfig {
    fn default() -> Self {
        Self {
            node_url: default_node_url(),
            bridge_url: default_bridge_url(),
            solana_rpc_url: default_solana_rpc(),
            base_rpc_url: default_base_rpc(),
            github_api_url: default_github_api(),
            github_token: None,
            wrtc_solana_mint: None,
            wrtc_base_contract: None,
            min_sol_lamports: default_min_sol_lamports(),
            min_eth_wei: default_min_eth_wei(),
            min_wallet_age_seconds: default_wallet_age_seconds(),
            min_github_age_seconds: default_github_age_seconds(),
            timeout_secs: default_timeout(),
            dry_run: false,
            verbose: false,
            admin_key: None,
        }
    }
}

impl AirdropConfig {
    /// Load configuration from environment variables
    pub fn from_env() -> crate::Result<Self> {
        let _ = dotenvy::dotenv();

        let mut config = AirdropConfig::default();

        if let Ok(val) = std::env::var("RUSTCHAIN_NODE_URL") {
            config.node_url = val;
        }

        if let Ok(val) = std::env::var("BRIDGE_URL") {
            config.bridge_url = val;
        }

        if let Ok(val) = std::env::var("SOLANA_RPC_URL") {
            config.solana_rpc_url = val;
        }

        if let Ok(val) = std::env::var("BASE_RPC_URL") {
            config.base_rpc_url = val;
        }

        if let Ok(val) = std::env::var("GITHUB_TOKEN") {
            config.github_token = Some(val);
        }

        if let Ok(val) = std::env::var("WRTC_SOLANA_MINT") {
            config.wrtc_solana_mint = Some(val);
        }

        if let Ok(val) = std::env::var("WRTC_BASE_CONTRACT") {
            config.wrtc_base_contract = Some(val);
        }

        if let Ok(val) = std::env::var("ADMIN_KEY") {
            config.admin_key = Some(val);
        }

        if let Ok(val) = std::env::var("DRY_RUN") {
            config.dry_run = val.to_lowercase() == "true" || val == "1";
        }

        if let Ok(val) = std::env::var("VERBOSE") {
            config.verbose = val.to_lowercase() == "true" || val == "1";
        }

        Ok(config)
    }

    /// Get request timeout as Duration
    pub fn timeout(&self) -> Duration {
        Duration::from_secs(self.timeout_secs)
    }

    /// Check if admin operations are available
    pub fn has_admin_key(&self) -> bool {
        self.admin_key.is_some()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = AirdropConfig::default();
        assert_eq!(config.node_url, "https://50.28.86.131");
        assert_eq!(config.bridge_url, "http://localhost:8096");
        assert_eq!(config.min_wallet_age_seconds, 7 * 24 * 60 * 60);
        assert_eq!(config.min_github_age_seconds, 30 * 24 * 60 * 60);
        assert!(!config.dry_run);
    }

    #[test]
    fn test_config_timeout() {
        let config = AirdropConfig::default();
        assert_eq!(config.timeout(), Duration::from_secs(30));
    }
}
