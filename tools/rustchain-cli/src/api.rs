//! RustChain API client — typed bindings to RustChain REST endpoints

use anyhow::{anyhow, Context};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;

/// Default RPC timeout
const DEFAULT_TIMEOUT: Duration = Duration::from_secs(15);

/// API client for RustChain REST endpoints
#[derive(Debug, Clone)]
pub struct Client {
    base_url: String,
    http: Client,
}

impl Client {
    /// Create a new API client pointing at the given base URL
    pub fn new(base_url: &str) -> anyhow::Result<Self> {
        let http = Client::builder()
            .timeout(DEFAULT_TIMEOUT)
            .user_agent("rustchain-cli/0.1.0")
            .build()?;
        Ok(Self {
            base_url: base_url.trim_end_matches('/').to_string(),
            http,
        })
    }

    fn get<T: for<'de> Deserialize<'de>>(&self, path: &str) -> anyhow::Result<T> {
        let url = format!("{}/{}", self.base_url, path.trim_start_matches('/'));
        let resp = self.http.get(&url).send()
            .with_context(|| format!("GET {url} failed"))?;
        if !resp.status().is_success() {
            return Err(anyhow!("HTTP {} from {url}", resp.status()));
        }
        let body = resp.text()
            .with_context(|| format!("Failed to read response from {url}"))?;
        serde_json::from_str(&body)
            .with_context(|| format!("Failed to parse JSON from {url}: {body}"))
    }

    // ─── Balance ────────────────────────────────────────────────────────────

    /// Get RTC balance for a wallet address
    pub async fn get_balance(&self, wallet: &str) -> anyhow::Result<f64> {
        // Try the balance endpoint first
        #[derive(Deserialize)]
        struct BalanceResp {
            balance: Option<f64>,
            amount: Option<f64>,
            rtc_balance: Option<f64>,
            balance_rtc: Option<f64>,
        }

        let result: Result<BalanceResp, _> = self.get(&format!("/balance/{wallet}"));
        if let Ok(b) = result {
            return Ok(b.balance.or(b.amount).or(b.rtc_balance).or(b.balance_rtc).unwrap_or(0.0));
        }

        // Try as query param
        #[derive(Deserialize)]
        struct BalanceQuery {
            balance: Option<f64>,
            amount: Option<f64>,
        }
        let q: Result<BalanceQuery, _> = self.get(&format!("/balance?wallet={wallet}"));
        if let Ok(b) = q {
            return Ok(b.balance.or(b.amount).unwrap_or(0.0));
        }

        // Fallback: 0 (wallet may not exist on-chain yet)
        Ok(0.0)
    }

    // ─── Miners ────────────────────────────────────────────────────────────

    /// List active miners
    pub async fn list_miners(&self, limit: usize) -> anyhow::Result<Vec<Miner>> {
        #[derive(Deserialize)]
        struct MinersResp {
            miners: Option<Vec<Miner>>,
            data: Option<Vec<Miner>>,
            results: Option<Vec<Miner>>,
        }
        let resp: MinersResp = self.get(&format!("/api/miners?limit={limit}"))?;
        let miners = resp.miners.or(resp.data).or(resp.results)
            .ok_or_else(|| anyhow!("No miners data in response"))?;
        Ok(miners)
    }

    /// Get detailed info for a specific miner
    pub async fn get_miner_info(&self, miner_id: &str) -> anyhow::Result<MinerInfo> {
        self.get(&format!("/api/miners/{miner_id}")).await
            .or_else(|_| self.get(&format!("/miner/{miner_id}")))
            .with_context(|| format!("Failed to fetch miner info for {miner_id}"))
    }

    // ─── Network ───────────────────────────────────────────────────────────

    /// Get network-wide statistics
    pub async fn get_network_stats(&self) -> anyhow::Result<NetworkStats> {
        self.get("/api/stats")
            .or_else(|_| self.get("/stats"))
            .or_else(|_| self.get("/agent/stats"))
            .await
            .with_context(|| "Failed to fetch network stats")
    }

    /// Get list of network nodes
    pub async fn get_nodes(&self) -> anyhow::Result<Vec<NodeInfo>> {
        #[derive(Deserialize)]
        struct NodesResp {
            nodes: Option<Vec<NodeInfo>>,
            peers: Option<Vec<NodeInfo>>,
        }
        let resp: NodesResp = self.get("/api/nodes").await?;
        Ok(resp.nodes.or(resp.peers).unwrap_or_default())
    }

    // ─── Epoch ─────────────────────────────────────────────────────────────

    /// Get current epoch information
    pub async fn get_epoch(&self) -> anyhow::Result<EpochInfo> {
        self.get("/epoch")
            .or_else(|_| self.get("/api/epoch"))
            .await
            .with_context(|| "Failed to fetch epoch info")
    }

    // ─── Health ────────────────────────────────────────────────────────────

    /// Perform a health check on the RustChain node
    pub async fn health_check(&self) -> anyhow::Result<HealthStatus> {
        self.get("/health").await
            .or_else(|_| self.get("/api/health"))
            .with_context(|| "Failed to fetch health status")
    }
}

// ─── Data types ────────────────────────────────────────────────────────────

/// A miner on the RustChain network
#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct Miner {
    #[serde(rename = "miner_id")]
    pub miner_id: Option<String>,
    #[serde(rename = "id")]
    pub id: Option<String>,
    #[serde(rename = "wallet")]
    pub wallet: Option<String>,
    #[serde(rename = "architecture")]
    pub architecture: String,
    #[serde(rename = "antiquity")]
    pub antiquity: f64,
    #[serde(rename = "multiplier")]
    pub multiplier: Option<f64>,
    #[serde(rename = "status")]
    pub status: String,
    #[serde(rename = "blocks_mined")]
    pub blocks_mined: usize,
    #[serde(rename = "last_attestation")]
    pub last_attestation: i64,
    #[serde(rename = "balance")]
    pub balance: f64,
}

impl Miner {
    /// Get the primary identifier (miner_id or id or wallet)
    pub fn id(&self) -> &str {
        self.miner_id.as_deref()
            .or(self.id.as_deref())
            .or(self.wallet.as_deref())
            .unwrap_or("unknown")
    }

    /// Get effective antiquity (try multiplier field as fallback)
    pub fn antiquity(&self) -> f64 {
        if self.antiquity == 0.0 {
            self.multiplier.unwrap_or(1.0)
        } else {
            self.antiquity
        }
    }
}

/// Detailed miner information
#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct MinerInfo {
    #[serde(rename = "miner_id")]
    pub miner_id: Option<String>,
    #[serde(rename = "id")]
    pub id: Option<String>,
    #[serde(rename = "architecture")]
    pub architecture: String,
    #[serde(rename = "status")]
    pub status: String,
    #[serde(rename = "antiquity")]
    pub antiquity: f64,
    #[serde(rename = "blocks_mined")]
    pub blocks_mined: usize,
    #[serde(rename = "balance")]
    pub balance: f64,
    #[serde(rename = "last_attestation")]
    pub last_attestation: i64,
    #[serde(rename = "wallet")]
    pub wallet: Option<String>,
    #[serde(rename = "stake")]
    pub stake: Option<f64>,
}

/// Network-wide statistics
#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct NetworkStats {
    #[serde(rename = "miners_total")]
    pub miners_total: usize,
    #[serde(rename = "miners_active")]
    pub miners_active: usize,
    #[serde(rename = "current_epoch")]
    pub current_epoch: usize,
    #[serde(rename = "epoch_end")]
    pub epoch_end: Option<String>,
    #[serde(rename = "total_supply_rtc")]
    pub total_supply_rtc: f64,
    #[serde(rename = "avg_antiquity")]
    pub avg_antiquity: Option<f64>,
    #[serde(rename = "total_stake")]
    pub total_stake: Option<f64>,
    #[serde(rename = "network_hashrate")]
    pub network_hashrate: Option<String>,
}

impl Default for NetworkStats {
    fn default() -> Self {
        Self {
            miners_total: 0,
            miners_active: 0,
            current_epoch: 0,
            epoch_end: None,
            total_supply_rtc: 0.0,
            avg_antiquity: Some(1.0),
            total_stake: None,
            network_hashrate: None,
        }
    }
}

/// Epoch information
#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct EpochInfo {
    #[serde(rename = "number")]
    pub number: usize,
    #[serde(rename = "start_time")]
    pub start_time: String,
    #[serde(rename = "end_time")]
    pub end_time: String,
    #[serde(rename = "reward_per_block")]
    pub reward_per_block: f64,
    #[serde(rename = "total_blocks")]
    pub total_blocks: usize,
    #[serde(rename = "active_miners")]
    pub active_miners: usize,
    #[serde(rename = "reward_distribution")]
    pub reward_distribution: Option<String>,
}

impl Default for EpochInfo {
    fn default() -> Self {
        Self {
            number: 0,
            start_time: "".to_string(),
            end_time: "".to_string(),
            reward_per_block: 0.0,
            total_blocks: 0,
            active_miners: 0,
            reward_distribution: None,
        }
    }
}

/// Node information
#[derive(Debug, Clone, Deserialize)]
pub struct NodeInfo {
    pub url: String,
    pub status: String,
    #[serde(rename = "block_height")]
    pub block_height: Option<usize>,
    #[serde(rename = "peer_count")]
    pub peer_count: Option<usize>,
}

/// Health status response
#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct HealthStatus {
    pub healthy: bool,
    pub message: Option<String>,
    #[serde(rename = "uptime_secs")]
    pub uptime_secs: i64,
    pub peers: usize,
    #[serde(rename = "block_height")]
    pub block_height: usize,
    pub version: Option<String>,
}

impl Default for HealthStatus {
    fn default() -> Self {
        Self {
            healthy: true,
            message: None,
            uptime_secs: 0,
            peers: 0,
            block_height: 0,
            version: None,
        }
    }
}

/// Balance response
#[derive(Debug, Clone, Deserialize)]
pub struct BalanceResponse {
    pub balance: f64,
    #[serde(rename = "wallet")]
    pub wallet: Option<String>,
}

/// API error response
#[derive(Debug, thiserror::Error)]
pub enum ApiError {
    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),
    #[error("API error: {0}")]
    Api(String),
    #[error("Parse error: {0}")]
    Parse(String),
}

// ─── Tests ─────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_network_stats() {
        let stats = NetworkStats::default();
        assert_eq!(stats.miners_total, 0);
        assert_eq!(stats.current_epoch, 0);
    }

    #[test]
    fn test_miner_id_fallback() {
        let m = Miner {
            miner_id: None, id: Some("id123".to_string()),
            wallet: Some("wal456".to_string()),
            ..Default::default()
        };
        assert_eq!(m.id(), "id123");
    }

    #[test]
    fn test_default_health() {
        let h = HealthStatus::default();
        assert!(h.healthy);
    }
}
