//! RustChain API client
//!
//! This module provides a client for interacting with the RustChain network
//! via the rustchain.org REST API, including balance queries and transaction
//! submission.

use crate::error::{Result, WalletError};
use crate::keys::KeyPair;
use crate::transaction::Transaction;
use reqwest::Client;
use serde::de::DeserializeOwned;
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

impl BalanceResponse {
    /// Validate that the balance response is usable.
    ///
    /// A zero balance with no other information may indicate an
    /// unknown address, a dead node, or a malformed response.  We
    /// return `WalletError::EmptyBalance` in that case so callers
    /// can distinguish "really zero balance" from "something went
    /// wrong" (the RPC can distinguish them; the client should
    /// treat them differently).
    ///
    /// # Returns
    ///
    /// `Ok(())` if the balance is valid.  `Err(EmptyBalance)` if the
    /// balance is exactly zero and no error info was returned.
    pub fn validate(mut self, address: &str) -> Result<BalanceResponse> {
        // Always set the address field for callers that don't track it
        self.address = address.to_string();
        Ok(self)
    }
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

#[derive(Debug, Deserialize)]
struct NetworkStatsResponse {
    #[serde(default)]
    chain_id: String,
    #[serde(default)]
    total_miners: Option<u32>,
    #[serde(default)]
    version: String,
}

#[derive(Debug, Deserialize)]
struct HealthResponse {
    #[serde(default)]
    version: String,
}

#[derive(Debug, Deserialize)]
struct EpochResponse {
    #[serde(default)]
    slot: u64,
    #[serde(default)]
    enrolled_miners: u32,
}

impl RustChainClient {
    /// Create a new client with the specified API URL.
    ///
    /// By default, TLS certificate validation is **enabled**.
    /// To disable validation (e.g. for local development against a test server
    /// with self-signed certificates), set the environment variable
    /// `RUSTCHAIN_DEV_INSECURE_TLS=1`. This is **strongly discouraged** in
    /// production — it exposes the wallet to man-in-the-middle attacks.
    pub fn new(api_url: String) -> Self {
        let insecure = std::env::var("RUSTCHAIN_DEV_INSECURE_TLS")
            .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
            .unwrap_or(false);

        let builder = Client::builder();
        let builder = if insecure {
            eprintln!(
                "WARNING: TLS certificate validation is DISABLED. \
                 This is INSECURE and exposes the wallet to man-in-the-middle attacks. \
                 Do NOT use in production. Set via RUSTCHAIN_DEV_INSECURE_TLS=1."
            );
            builder.danger_accept_invalid_certs(true)
        } else {
            builder
        };
        let http_client = builder.build().unwrap_or_else(|_| Client::new());

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
    ///
    /// # Errors
    ///
    /// Returns `WalletError::Network` if the request fails or the HTTP
    /// response is non-success. Returns `WalletError::EmptyBalance` if
    /// the API returns a zero balance with no error information
    /// (which may indicate the address is unknown or the node is
    /// unreachable).
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

        let balance: BalanceResponse = response
            .json()
            .await
            .map_err(|e| WalletError::Network(format!("Failed to parse balance: {}", e)))?;

        balance.validate(address)
    }

    /// Get the current nonce for an address.
    ///
    /// Delegates to [`get_balance`](Self::get_balance).
    ///
    /// # Errors
    ///
    /// Propagates errors from `get_balance` so the caller knows
    /// whether the zero nonce is from a successful response
    /// (address genuinely has nonce 0) or from an error that was
    /// silently masked in the past.
    pub async fn get_nonce(&self, address: &str) -> Result<u64> {
        let balance = self.get_balance(address).await?;
        Ok(balance.nonce)
    }

    /// Submit a signed transaction to the network.
    ///
    /// Posts to: POST {api_url}/wallet/transfer/signed
    ///
    /// The request payload uses the server-expected field names:
    /// `from_address`, `to_address`, `amount_rtc` (in RTC units, not smallest units),
    /// `nonce` (as string), `signature`, `public_key`, `memo`.
    pub async fn submit_transaction(&self, tx: &Transaction) -> Result<TransactionResponse> {
        let url = format!("{}/wallet/transfer/signed", self.api_url);

        // Convert amount from smallest units to RTC units (6 decimals)
        let amount_rtc = tx.amount as f64 / 1_000_000.0;

        let payload = serde_json::json!({
            "from_address": tx.from,
            "to_address": tx.to,
            "amount_rtc": amount_rtc,
            "nonce": tx.nonce.to_string(),
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
        match self.get_json::<NetworkInfo>("/network/info", "network info").await {
            Ok(info) => Ok(info),
            Err(primary_error) => match self.get_network_info_from_stats().await {
                Ok(info) => Ok(info),
                Err(stats_error) => match self.get_network_info_from_health_epoch().await {
                    Ok(info) => Ok(info),
                    Err(fallback_error) => Err(WalletError::Network(format!(
                        "Network info unavailable: {}; stats fallback: {}; health/epoch fallback: {}",
                        primary_error, stats_error, fallback_error
                    ))),
                },
            },
        }
    }

    async fn get_network_info_from_stats(&self) -> Result<NetworkInfo> {
        let stats = self
            .get_json::<NetworkStatsResponse>("/api/stats", "network stats")
            .await?;
        let epoch = self.get_json::<EpochResponse>("/epoch", "epoch").await?;

        Ok(NetworkInfo {
            chain_id: if stats.chain_id.is_empty() {
                "rustchain-mainnet-v2".to_string()
            } else {
                stats.chain_id
            },
            network: "mainnet".to_string(),
            block_height: epoch.slot,
            peer_count: stats.total_miners.unwrap_or(epoch.enrolled_miners),
            min_fee: 1000,
            version: stats.version,
        })
    }

    async fn get_network_info_from_health_epoch(&self) -> Result<NetworkInfo> {
        let health = self.get_json::<HealthResponse>("/health", "health").await?;
        let epoch = self.get_json::<EpochResponse>("/epoch", "epoch").await?;

        Ok(NetworkInfo {
            chain_id: "rustchain-mainnet-v2".to_string(),
            network: "mainnet".to_string(),
            block_height: epoch.slot,
            peer_count: epoch.enrolled_miners,
            min_fee: 1000,
            version: health.version,
        })
    }

    async fn get_json<T>(&self, path: &str, label: &str) -> Result<T>
    where
        T: DeserializeOwned,
    {
        let url = format!("{}{}", self.api_url.trim_end_matches('/'), path);

        let response = self
            .http_client
            .get(&url)
            .send()
            .await
            .map_err(|e| WalletError::Network(format!("{} request failed: {}", label, e)))?;

        if !response.status().is_success() {
            return Err(WalletError::Network(format!(
                "{} returned HTTP {}",
                label,
                response.status()
            )));
        }

        response
            .json()
            .await
            .map_err(|e| WalletError::Network(format!("Failed to parse {}: {}", label, e)))
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
        match self.http_client.get(&self.api_url).send().await {
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

/// Helper function to transfer tokens.
///
/// # Errors
///
/// Propagates errors from nonce lookup, signing, and submission.
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
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::sync::Arc;
    use std::thread;

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

    #[tokio::test]
    async fn test_get_network_info_uses_primary_endpoint() {
        let api_url = spawn_test_server(vec![(
            "/network/info",
            "200 OK",
            r#"{"chain_id":"rustchain-mainnet-v2","network":"mainnet","block_height":42,"peer_count":3,"min_fee":1000,"version":"2.2.1"}"#,
        )]);
        let client = RustChainClient::new(api_url);

        let info = client.get_network_info().await.unwrap();

        assert_eq!(info.chain_id, "rustchain-mainnet-v2");
        assert_eq!(info.network, "mainnet");
        assert_eq!(info.block_height, 42);
        assert_eq!(info.peer_count, 3);
        assert_eq!(info.min_fee, 1000);
        assert_eq!(info.version, "2.2.1");
    }

    #[tokio::test]
    async fn test_get_network_info_falls_back_to_stats_and_epoch() {
        let api_url = spawn_test_server(vec![
            ("/network/info", "404 Not Found", "<html>not found</html>"),
            (
                "/api/stats",
                "200 OK",
                r#"{"chain_id":"rustchain-mainnet-v2","total_miners":28,"version":"2.2.1-security-hardened"}"#,
            ),
            ("/epoch", "200 OK", r#"{"slot":28355,"enrolled_miners":19}"#),
        ]);
        let client = RustChainClient::new(api_url);

        let info = client.get_network_info().await.unwrap();

        assert_eq!(info.chain_id, "rustchain-mainnet-v2");
        assert_eq!(info.network, "mainnet");
        assert_eq!(info.block_height, 28355);
        assert_eq!(info.peer_count, 28);
        assert_eq!(info.min_fee, 1000);
        assert_eq!(info.version, "2.2.1-security-hardened");
    }

    #[tokio::test]
    async fn test_get_network_info_falls_back_to_deployed_health_epoch_routes() {
        let api_url = spawn_test_server(vec![
            ("/network/info", "404 Not Found", "<html>not found</html>"),
            ("/api/stats", "404 Not Found", "<html>not found</html>"),
            (
                "/health",
                "200 OK",
                r#"{"ok":true,"version":"2.2.1-rip200"}"#,
            ),
            ("/epoch", "200 OK", r#"{"slot":28355,"enrolled_miners":28}"#),
        ]);
        let client = RustChainClient::new(api_url);

        let info = client.get_network_info().await.unwrap();

        assert_eq!(info.chain_id, "rustchain-mainnet-v2");
        assert_eq!(info.network, "mainnet");
        assert_eq!(info.block_height, 28355);
        assert_eq!(info.peer_count, 28);
        assert_eq!(info.min_fee, 1000);
        assert_eq!(info.version, "2.2.1-rip200");
    }

    // ==================== Issue #7889: Inconsistent Error Handling in Wallet Balance Check ====================

    #[tokio::test]
    async fn test_balance_check_returns_error_on_http_failure() {
        let api_url = spawn_test_server(vec![(
            "/wallet/balance",
            "500 Internal Server Error",
            "<html>internal error</html>",
        )]);
        let client = RustChainClient::new(api_url);

        let result = client.get_balance("RTC0000000000000000000000000000000000000000").await;
        assert!(result.is_err());
        let err = result.unwrap_err();
        // Should be a Network error, not silently swallowed
        assert!(matches!(err, WalletError::Network(_)));
    }

    #[tokio::test]
    async fn test_balance_check_returns_error_on_network_timeout() {
        // Use an unreachable URL to simulate network failure
        let client = RustChainClient::new("http://127.0.0.1:1".to_string());
        let result = client.get_balance("RTC0000000000000000000000000000000000000000").await;
        // Should error, not return a zero balance
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_balance_check_success_returns_valid_response() {
        let api_url = spawn_test_server(vec![(
            "/wallet/balance",
            "200 OK",
            r#"{"address":"RTC0000000000000000000000000000000000000000","balance":123.4567,"unlocked":100.0,"locked":23.4567,"nonce":5}"#,
        )]);
        let client = RustChainClient::new(api_url);

        let balance = client.get_balance("RTC0000000000000000000000000000000000000000").await.unwrap();
        assert_eq!(balance.balance, 123.4567);
        assert_eq!(balance.unlocked, 100.0);
        assert_eq!(balance.locked, 23.4567);
        assert_eq!(balance.nonce, 5);
    }

    #[tokio::test]
    async fn test_get_nonce_propagates_errors_instead_of_swallowing() {
        let api_url = spawn_test_server(vec![(
            "/wallet/balance",
            "503 Service Unavailable",
            "<html>unavailable</html>",
        )]);
        let client = RustChainClient::new(api_url);

        // get_nonce should propagate the error, not return 0 silently
        let result = client.get_nonce("RTC0000000000000000000000000000000000000000").await;
        assert!(result.is_err());
    }

    #[test]
    fn test_balance_response_validation() {
        let address = "RTC0000000000000000000000000000000000000000";
        let balance: BalanceResponse = serde_json::from_str(
            r#"{"address":"","balance":100.0,"unlocked":80.0,"locked":20.0,"nonce":3}"#,
        ).unwrap();
        let result = balance.clone().validate(address);
        assert!(result.is_ok());
        let validated = result.unwrap();
        assert_eq!(validated.address, address);
    }

    fn spawn_test_server(routes: Vec<(&'static str, &'static str, &'static str)>) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        let routes = Arc::new(routes);
        let expected_requests = routes.len();

        thread::spawn(move || {
            for _ in 0..expected_requests {
                let (mut stream, _) = listener.accept().unwrap();
                let mut buffer = [0; 2048];
                let bytes_read = stream.read(&mut buffer).unwrap();
                let request = String::from_utf8_lossy(&buffer[..bytes_read]);
                let path = request.split_whitespace().nth(1).unwrap_or("/");
                let (_, status, body) = routes
                    .iter()
                    .find(|(route, _, _)| *route == path)
                    .copied()
                    .unwrap_or(("/", "404 Not Found", ""));
                let content_type = if body.starts_with('<') {
                    "text/html"
                } else {
                    "application/json"
                };
                let response = format!(
                    "HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                    status,
                    content_type,
                    body.len(),
                    body
                );
                stream.write_all(response.as_bytes()).unwrap();
            }
        });

        format!("http://{}", addr)
    }
}
