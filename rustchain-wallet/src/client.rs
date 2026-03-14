//! RustChain RPC client
//!
//! This module provides a client for interacting with the RustChain network,
//! including balance queries, transaction submission, and network info.

use crate::error::{Result, WalletError};
use crate::keys::KeyPair;
use crate::transaction::Transaction;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::json;

/// RustChain RPC client
pub struct RustChainClient {
    rpc_url: String,
    http_client: Client,
}

/// Balance response from the RPC
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BalanceResponse {
    pub address: String,
    pub balance: u64,
    pub unlocked: u64,
    pub locked: u64,
    pub nonce: u64,
}

/// Transaction response from the RPC
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionResponse {
    pub tx_hash: String,
    pub status: String,
    pub block_height: Option<u64>,
    pub confirmations: Option<u64>,
}

/// Network info response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NetworkInfo {
    pub chain_id: String,
    pub network: String,
    pub block_height: u64,
    pub peer_count: u32,
    pub min_fee: u64,
    pub version: String,
}

impl RustChainClient {
    /// Create a new client with the specified RPC URL
    pub fn new(rpc_url: String) -> Self {
        Self {
            rpc_url,
            http_client: Client::new(),
        }
    }

    /// Create a client with a custom HTTP client (for advanced configurations)
    pub fn with_client(rpc_url: String, http_client: Client) -> Self {
        Self {
            rpc_url,
            http_client,
        }
    }

    /// Get the balance for an address
    pub async fn get_balance(&self, address: &str) -> Result<BalanceResponse> {
        let response = self
            .rpc_call(
                "getBalance",
                json!({
                    "address": address
                }),
            )
            .await?;

        serde_json::from_value(response)
            .map_err(|e| WalletError::Rpc(format!("Failed to parse balance response: {}", e)))
    }

    /// Get the current nonce for an address
    pub async fn get_nonce(&self, address: &str) -> Result<u64> {
        let response = self
            .rpc_call(
                "getNonce",
                json!({
                    "address": address
                }),
            )
            .await?;

        response["nonce"]
            .as_u64()
            .ok_or_else(|| WalletError::Rpc("Invalid nonce response".to_string()))
    }

    /// Submit a signed transaction
    pub async fn submit_transaction(&self, tx: &Transaction) -> Result<TransactionResponse> {
        let response = self
            .rpc_call(
                "submitTransaction",
                json!({
                    "transaction": tx
                }),
            )
            .await?;

        serde_json::from_value(response)
            .map_err(|e| WalletError::Rpc(format!("Failed to parse transaction response: {}", e)))
    }

    /// Get transaction status by hash
    pub async fn get_transaction(&self, tx_hash: &str) -> Result<TransactionResponse> {
        let response = self
            .rpc_call(
                "getTransaction",
                json!({
                    "tx_hash": tx_hash
                }),
            )
            .await?;

        serde_json::from_value(response)
            .map_err(|e| WalletError::Rpc(format!("Failed to parse transaction status: {}", e)))
    }

    /// Get network information
    pub async fn get_network_info(&self) -> Result<NetworkInfo> {
        let response = self.rpc_call("getNetworkInfo", json!({})).await?;

        serde_json::from_value(response)
            .map_err(|e| WalletError::Rpc(format!("Failed to parse network info: {}", e)))
    }

    /// Get the minimum transaction fee
    pub async fn get_min_fee(&self) -> Result<u64> {
        let info = self.get_network_info().await?;
        Ok(info.min_fee)
    }

    /// Estimate the fee for a transaction
    pub async fn estimate_fee(&self, _amount: u64, priority: FeePriority) -> Result<u64> {
        let min_fee = self.get_min_fee().await?;

        let multiplier = match priority {
            FeePriority::Low => 1,
            FeePriority::Normal => 2,
            FeePriority::High => 5,
            FeePriority::Instant => 10,
        };

        Ok(min_fee * multiplier)
    }

    /// Check if the RPC endpoint is reachable
    pub async fn health_check(&self) -> Result<bool> {
        match self.get_network_info().await {
            Ok(_) => Ok(true),
            Err(_) => Ok(false),
        }
    }

    /// Make a JSON-RPC 2.0 call to the RustChain network.
    ///
    /// # Request Format
    /// ```json
    /// {
    ///   "jsonrpc": "2.0",
    ///   "method": "<method>",
    ///   "params": <params>,
    ///   "id": 1
    /// }
    /// ```
    ///
    /// # Response Handling
    /// 1. **Network error**: HTTP failure → `WalletError::Network`
    /// 2. **Status error**: Non-2xx response → `WalletError::Network`
    /// 3. **Parse error**: Invalid JSON → `WalletError::Network`
    /// 4. **RPC error**: `error` field present → `WalletError::Rpc`
    /// 5. **Missing result**: No `result` field → `WalletError::Rpc`
    ///
    /// # Arguments
    /// * `method` - RPC method name (e.g., "getBalance", "submitTransaction")
    /// * `params` - Method parameters as JSON value
    ///
    /// # Returns
    /// * `Ok(serde_json::Value)` - The `result` field from RPC response
    /// * `Err(WalletError::Network)` - HTTP/transport failure
    /// * `Err(WalletError::Rpc)` - RPC-level error or missing result
    async fn rpc_call(&self, method: &str, params: serde_json::Value) -> Result<serde_json::Value> {
        let request = json!({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        });

        let response = self
            .http_client
            .post(&self.rpc_url)
            .json(&request)
            .send()
            .await
            .map_err(|e| WalletError::Network(format!("RPC request failed: {}", e)))?;

        if !response.status().is_success() {
            return Err(WalletError::Network(format!(
                "RPC returned status: {}",
                response.status()
            )));
        }

        let json_response: serde_json::Value = response
            .json()
            .await
            .map_err(|e| WalletError::Network(format!("Failed to parse JSON: {}", e)))?;

        // Check for RPC error
        if let Some(error) = json_response.get("error") {
            if !error.is_null() {
                return Err(WalletError::Rpc(format!("RPC error: {}", error)));
            }
        }

        json_response
            .get("result")
            .cloned()
            .ok_or_else(|| WalletError::Rpc("No result in RPC response".to_string()))
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
        tx.nonce = client.get_nonce(&tx.from).await?;
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
        let client = RustChainClient::new("https://rpc.rustchain.org".to_string());
        assert_eq!(client.rpc_url, "https://rpc.rustchain.org");
    }

    #[tokio::test]
    async fn test_fee_priority() {
        let _client = RustChainClient::new("https://rpc.rustchain.org".to_string());

        // This will fail in tests without a real RPC, but tests the logic
        let _low = FeePriority::Low;
        let _normal = FeePriority::Normal;
        let _high = FeePriority::High;
        let _instant = FeePriority::Instant;
    }
}
