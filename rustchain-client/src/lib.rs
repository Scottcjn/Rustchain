//! RustChain Client - HTTP client for RustChain node API
//!
//! A Rust library for interacting with the RustChain blockchain API.
//! Provides access to health checks, epoch data, miners, and wallet operations.
//!
//! # Example
//!
//! ```rust
//! use rustchain_client::RustChainClient;
//!
//! #[tokio::main]
//! async fn main() -> Result<(), Box<dyn std::error::Error>> {
//!     let client = RustChainClient::new();
//!     
//!     // Check network health
//!     let health = client.health().await?;
//!     println!("Network status: {}", health.status);
//!     
//!     // Get current epoch
//!     let epoch = client.epoch().await?;
//!     println!("Current epoch: {}", epoch.epoch);
//!     
//!     Ok(())
//! }
//! ```

use serde::{Deserialize, Serialize};
use reqwest::Client;
use std::error::Error;

pub mod types;
pub use types::*;

pub struct RustChainClient {
    client: Client,
    base_url: String,
}

impl RustChainClient {
    /// Create a new RustChain client with default settings
    pub fn new() -> Self {
        Self::with_base_url("https://rustchain.org")
    }

    /// Create a RustChain client with a custom base URL
    pub fn with_base_url(base_url: impl Into<String>) -> Self {
        let client = Client::builder()
            .danger_accept_invalid_certs(true)
            .build()
            .expect("Failed to create HTTP client");

        Self {
            client,
            base_url: base_url.into(),
        }
    }

    /// Check network health
    pub async fn health(&self) -> Result<HealthResponse, Box<dyn Error>> {
        let url = format!("{}/health", self.base_url);
        let response = self.client.get(&url).send().await?;
        let data = response.json::<HealthResponse>().await?;
        Ok(data)
    }

    /// Get current epoch information
    pub async fn epoch(&self) -> Result<EpochResponse, Box<dyn Error>> {
        let url = format!("{}/epoch", self.base_url);
        let response = self.client.get(&url).send().await?;
        let data = response.json::<EpochResponse>().await?;
        Ok(data)
    }

    /// List active miners
    pub async fn miners(&self) -> Result<MinersResponse, Box<dyn Error>> {
        let url = format!("{}/api/miners", self.base_url);
        let response = self.client.get(&url).send().await?;
        let data = response.json::<MinersResponse>().await?;
        Ok(data)
    }

    /// Check wallet balance
    pub async fn balance(&self, miner_id: &str) -> Result<BalanceResponse, Box<dyn Error>> {
        let url = format!("{}/wallet/balance?miner_id={}", self.base_url, miner_id);
        let response = self.client.get(&url).send().await?;
        let data = response.json::<BalanceResponse>().await?;
        Ok(data)
    }

    /// Get governance proposals
    pub async fn proposals(&self) -> Result<ProposalsResponse, Box<dyn Error>> {
        let url = format!("{}/governance/proposals", self.base_url);
        let response = self.client.get(&url).send().await?;
        let data = response.json::<ProposalsResponse>().await?;
        Ok(data)
    }

    /// Get a specific proposal by ID
    pub async fn proposal(&self, id: u64) -> Result<ProposalDetail, Box<dyn Error>> {
        let url = format!("{}/governance/proposal/{}", self.base_url, id);
        let response = self.client.get(&url).send().await?;
        let data = response.json::<ProposalDetail>().await?;
        Ok(data)
    }
}

impl Default for RustChainClient {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_client_creation() {
        let client = RustChainClient::new();
        assert_eq!(client.base_url, "https://rustchain.org");
    }

    #[test]
    fn test_custom_base_url() {
        let client = RustChainClient::with_base_url("http://localhost:8080");
        assert_eq!(client.base_url, "http://localhost:8080");
    }
}
