//! RustChain API client
//!
//! This module provides a client for interacting with the RustChain network
//! via the rustchain.org REST API, including balance queries and transaction
//! submission.

use crate::error::{Result, WalletError};
use crate::keys::KeyPair;
use crate::transaction::Transaction;
use reqwest::Client;
use serde::{Deserialize, Serialize};

/// RustChain API client
pub struct RustChainClient {
    api_url: String,
    http_client: Client,
}

/// Balance response from the API
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BalanceResponse {
    #[serde(default)]
    pub address: String,
    #[serde(alias = "amount_rtc", alias = "balance", default)]
    pub balance: f64,
    #[serde(default)]
    pub unlocked: f64,
    #[serde(default)]
    pub locked: f64,
    #[serde(default)]
    pub nonce: u64,
}

/// Transaction response from the API
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionResponse {
    #[serde(default)]
    pub tx_hash: String,
    #[serde(alias = "ok", default)]
    pub success: bool,
    #[serde(default)]
    pub status: String,
    #[serde(default)]
    pub block_height: Option<u64>,
    #[serde(default)]
    pub confirmations: Option<u64>,
    #[serde(default)]
    pub error: Option<String>,
}

/// Network info response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkInfo {
    #[serde(default)]
    pub chain_id: String,
    #[serde(default)]
    pub network: String,
    #[serde(default)]
    pub block_height: u64,
    #[serde(default)]
    pub peer_count: u32,
    #[serde(default)]
    pub min_fee: u64,
    #[serde(default)]
    pub version: String,
}

impl RustChainClient {
    /// Create a new client with the specified API URL
    pub fn new(api_url: String) -> Self {
        let http_client = Client::builder()
            .danger_accept_invalid_certs(true)
            .build()
            .unwrap_or_else(|_| Client::new());

        Self {
            api_url,
            http_client,
        }
    }

    /// Create a client with a custom HTTP client
    pub fn with_client(api_url: String, http_client: Client) -> Self {
        Self {
            api_url,
            http_client,
        }
    }

    /// Get the balance for an RTC address via the REST API.
    ///
    /// Queries: GET {api_url}/wallet/balance?miner_id={address}
    pub async fn get_balance(&self, address: &str) -> Result<BalanceResponse> {
        let url = format!("{}/wallet/balance?miner_id={}", self.api_url, address);

        let response = self
            .http_client
            .get(&url)
            .send()
            .await
            .map_err(|e| WalletError::Network(format!("Balance request failed: {}", e)))?;

        if !response.status().is_success() {
            return Err(WalletError::Network(format!(
                "Balance query returned HTTP {}",
                response.status()
            )));
        }

        let mut balance: BalanceResponse = response
            .json()
            .await
            .map_err(|e| WalletError::Network(format!("Failed to parse balance: {}", e)))?;

        balance.address = address.to_string();
        Ok(balance)
    }

    /// Get the current nonce for an address
    pub async fn get_nonce(&self, address: &str) -> Result<u64> {
        let balance = self.get_balance(address).await?;
        Ok(balance.nonce)
    }

    /// Submit a signed transaction to the network.
    ///
    /// Posts to: POST {api_url}/wallet/transfer/signed
    pub async fn submit_transaction(&self, tx: &Transaction) -> Result<TransactionResponse> {
        let url = format!("{}/wallet/transfer/signed", self.api_url);

        let payload = serde_json::json!({
            "from": tx.from,
            "to": tx.to,
            "amount": tx.amount,
            "fee": tx.fee,
            "nonce": tx.nonce,
            "timestamp": tx.timestamp.timestamp(),
            "memo": tx.memo,
            "signature": tx.signature,
            "public_key": tx.public_key,
        });

        let response = self
            .http_client
            .post(&url)
            .json(&payload)
            .send()
            .await
            .map_err(|e| WalletError::Network(format!("Transaction submission failed: {}", e)))?;

        if !response.status().is_success() {
            return Err(WalletError::Network(format!(
                "Transaction returned HTTP {}",
                response.status()
            )));
        }

        let result: TransactionResponse = response
            .json()
            .await
            .map_err(|e| WalletError::Network(format!("Failed to parse tx response: {}", e)))?;

        if let Some(ref err) = result.error {
            return Err(WalletError::Rpc(err.clone()));
        }

        Ok(result)
    }

    /// Get transaction status by hash
    pub async fn get_transaction(&self, tx_hash: &str) -> Result<TransactionResponse> {
        let url = format!("{}/wallet/tx/{}", self.api_url, tx_hash);

        let response = self
            .http_client
            .get(&url)
            .send()
            .await
            .map_err(|e| WalletError::Network(format!("TX query failed: {}", e)))?;

        response
            .json()
            .await
            .map_err(|e| WalletError::Network(format!("Failed to parse tx status: {}", e)))
    }

    /// Get network information
    pub async fn get_network_info(&self) -> Result<NetworkInfo> {
        let url = format!("{}/network/info", self.api_url);

        let response = self
            .http_client
            .get(&url)
            .send()
            .await
            .map_err(|e| WalletError::Network(format!("Network info request failed: {}", e)))?;

        response
            .json()
            .await
            .map_err(|e| WalletError::Network(format!("Failed to parse network info: {}", e)))
    }

    /// Get the minimum transaction fee
    pub async fn get_min_fee(&self) -> Result<u64> {
        let info = self.get_network_info().await?;
        Ok(info.min_fee)
    }

    /// Estimate the fee for a transaction
    pub async fn estimate_fee(&self, _amount: u64, priority: FeePriority) -> Result<u64> {
        let min_fee = self.get_min_fee().await.unwrap_or(1000);

        let multiplier = match priority {
            FeePriority::Low => 1,
            FeePriority::Normal => 2,
            FeePriority::High => 5,
            FeePriority::Instant => 10,
        };

        Ok(min_fee * multiplier)
    }

    /// Check if the API endpoint is reachable
    pub async fn health_check(&self) -> Result<bool> {
        match self
            .http_client
            .get(&self.api_url)
            .send()
            .await
        {
            Ok(resp) => Ok(resp.status().is_success()),
            Err(_) => Ok(false),
        }
    }
}

/// Fee priority levels
#[derive(Debug, Clone, Copy)]
pub enum FeePriority {
    Low,
    Normal,
    High,
    Instant,
}

/// Helper function to transfer tokens
pub async fn transfer(
    client: &RustChainClient,
    tx: &mut Transaction,
    keypair: &KeyPair,
) -> Result<TransactionResponse> {
    // Get current nonce if not set
    if tx.nonce == 0 {
        tx.nonce = client.get_nonce(&tx.from).await.unwrap_or(0);
    }

    // Sign the transaction
    tx.sign(keypair)?;

    // Submit to network
    client.submit_transaction(tx).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_client_creation() {
        let client = RustChainClient::new("https://rustchain.org".to_string());
        assert_eq!(client.api_url, "https://rustchain.org");
    }

    #[tokio::test]
    async fn test_fee_priority() {
        let _client = RustChainClient::new("https://rustchain.org".to_string());

        let _low = FeePriority::Low;
        let _normal = FeePriority::Normal;
        let _high = FeePriority::High;
        let _instant = FeePriority::Instant;
    }
}
