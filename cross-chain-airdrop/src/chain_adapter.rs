//! Chain adapter interfaces for Solana and Base L2

use crate::error::Result;
use crate::models::{TargetChain, WalletTier, WalletVerification};
use async_trait::async_trait;
use chrono::{DateTime, Utc};

/// Chain adapter trait for cross-chain operations
#[async_trait]
pub trait ChainAdapter: Send + Sync {
    /// Get the chain identifier
    fn chain(&self) -> TargetChain;

    /// Get RPC URL
    fn rpc_url(&self) -> &str;

    /// Verify wallet balance and age
    async fn verify_wallet(&self, address: &str) -> Result<WalletVerification>;

    /// Get current balance in base units
    async fn get_balance(&self, address: &str) -> Result<u64>;

    /// Get wallet age from first transaction
    async fn get_wallet_age(&self, address: &str) -> Result<u64>;

    /// Validate address format
    fn validate_address(&self, address: &str) -> Result<()>;

    /// Calculate wallet tier from balance
    fn calculate_tier(&self, balance_base_units: u64) -> WalletTier;
}

/// Solana chain adapter
pub struct SolanaAdapter {
    rpc_url: String,
    min_balance_lamports: u64,
    min_age_seconds: u64,
}

impl SolanaAdapter {
    pub fn new(rpc_url: String, min_balance_lamports: u64, min_age_seconds: u64) -> Self {
        Self {
            rpc_url,
            min_balance_lamports,
            min_age_seconds,
        }
    }

    /// Create with default minimums (0.1 SOL, 7 days)
    pub fn with_defaults(rpc_url: String) -> Self {
        Self {
            rpc_url,
            min_balance_lamports: 100_000_000, // 0.1 SOL
            min_age_seconds: 7 * 24 * 60 * 60, // 7 days
        }
    }
}

#[async_trait]
impl ChainAdapter for SolanaAdapter {
    fn chain(&self) -> TargetChain {
        TargetChain::Solana
    }

    fn rpc_url(&self) -> &str {
        &self.rpc_url
    }

    async fn verify_wallet(&self, address: &str) -> Result<WalletVerification> {
        self.validate_address(address)?;

        let balance = self.get_balance(address).await?;
        let age_seconds = self.get_wallet_age(address).await?;

        let meets_balance = balance >= self.min_balance_lamports;
        let meets_age = age_seconds >= self.min_age_seconds;
        let tier = self.calculate_tier(balance);

        Ok(WalletVerification {
            address: address.to_string(),
            chain: TargetChain::Solana,
            balance_base_units: balance,
            wallet_age_seconds: age_seconds,
            first_tx_timestamp: None, // Would be set from actual RPC call
            meets_minimum_balance: meets_balance,
            meets_age_requirement: meets_age,
            tier,
        })
    }

    async fn get_balance(&self, address: &str) -> Result<u64> {
        let client = reqwest::Client::new();
        let response = client
            .post(&self.rpc_url)
            .json(&serde_json::json!({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [address]
            }))
            .send()
            .await
            .map_err(|e| {
                crate::error::AirdropError::WalletVerification(format!(
                    "Solana RPC request failed: {}",
                    e
                ))
            })?;
        let result: serde_json::Value = response.json().await.map_err(|e| {
            crate::error::AirdropError::WalletVerification(format!(
                "Solana RPC response parse failed: {}",
                e
            ))
        })?;
        Ok(result["result"]["value"].as_u64().unwrap_or(0))
    }

    async fn get_wallet_age(&self, _address: &str) -> Result<u64> {
        // Determining wallet age requires fetching the first transaction via
        // getSignaturesForAddress and correlating block timestamps.  This is
        // significantly more involved than a simple balance query and depends
        // on historical RPC availability.  Return 0 as a conservative default
        // so that the age gate must be satisfied by other means (or disabled
        // at the policy level) rather than being trivially bypassed.
        Ok(0)
    }

    fn validate_address(&self, address: &str) -> Result<()> {
        // Solana addresses are base58-encoded, 32-44 characters
        if address.len() < 32 || address.len() > 44 {
            return Err(crate::error::AirdropError::WalletVerification(format!(
                "Invalid Solana address length: {}",
                address.len()
            )));
        }

        // Basic base58 validation (no 0, O, I, l)
        let invalid_chars = ['0', 'O', 'I', 'l'];
        if address.chars().any(|c| invalid_chars.contains(&c)) {
            return Err(crate::error::AirdropError::WalletVerification(
                "Invalid base58 characters in Solana address".to_string(),
            ));
        }

        // Full base58 decode validation
        match bs58::decode(address).into_vec() {
            Ok(decoded) if decoded.len() == 32 => Ok(()),
            Ok(_) => Err(crate::error::AirdropError::WalletVerification(
                "Solana address must decode to 32 bytes".to_string(),
            )),
            Err(e) => Err(crate::error::AirdropError::WalletVerification(format!(
                "Invalid base58 encoding: {}",
                e
            ))),
        }
    }

    fn calculate_tier(&self, balance_base_units: u64) -> WalletTier {
        // SOL has 9 decimals, so 1 SOL = 1,000,000,000 lamports
        if balance_base_units >= 10_000_000_000 {
            // 10+ SOL
            WalletTier::High
        } else if balance_base_units >= 1_000_000_000 {
            // 1-10 SOL
            WalletTier::Mid
        } else {
            // 0.1-1 SOL
            WalletTier::Minimum
        }
    }
}

/// Base L2 chain adapter
pub struct BaseAdapter {
    rpc_url: String,
    min_balance_wei: u64,
    min_age_seconds: u64,
}

impl BaseAdapter {
    pub fn new(rpc_url: String, min_balance_wei: u64, min_age_seconds: u64) -> Self {
        Self {
            rpc_url,
            min_balance_wei,
            min_age_seconds,
        }
    }

    /// Create with default minimums (0.01 ETH, 7 days)
    pub fn with_defaults(rpc_url: String) -> Self {
        Self {
            rpc_url,
            min_balance_wei: 10_000_000_000_000_000, // 0.01 ETH
            min_age_seconds: 7 * 24 * 60 * 60,       // 7 days
        }
    }
}

#[async_trait]
impl ChainAdapter for BaseAdapter {
    fn chain(&self) -> TargetChain {
        TargetChain::Base
    }

    fn rpc_url(&self) -> &str {
        &self.rpc_url
    }

    async fn verify_wallet(&self, address: &str) -> Result<WalletVerification> {
        self.validate_address(address)?;

        let balance = self.get_balance(address).await?;
        let age_seconds = self.get_wallet_age(address).await?;

        let meets_balance = balance >= self.min_balance_wei;
        let meets_age = age_seconds >= self.min_age_seconds;
        let tier = self.calculate_tier(balance);

        Ok(WalletVerification {
            address: address.to_string(),
            chain: TargetChain::Base,
            balance_base_units: balance,
            wallet_age_seconds: age_seconds,
            first_tx_timestamp: None,
            meets_minimum_balance: meets_balance,
            meets_age_requirement: meets_age,
            tier,
        })
    }

    async fn get_balance(&self, address: &str) -> Result<u64> {
        let client = reqwest::Client::new();
        let response = client
            .post(&self.rpc_url)
            .json(&serde_json::json!({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getBalance",
                "params": [address, "latest"]
            }))
            .send()
            .await
            .map_err(|e| {
                crate::error::AirdropError::WalletVerification(format!(
                    "Base RPC request failed: {}",
                    e
                ))
            })?;
        let result: serde_json::Value = response.json().await.map_err(|e| {
            crate::error::AirdropError::WalletVerification(format!(
                "Base RPC response parse failed: {}",
                e
            ))
        })?;
        let balance_hex = result["result"].as_str().unwrap_or("0x0");
        u64::from_str_radix(balance_hex.trim_start_matches("0x"), 16).map_err(|e| {
            crate::error::AirdropError::WalletVerification(format!(
                "Base balance hex parse failed: {}",
                e
            ))
        })
    }

    async fn get_wallet_age(&self, _address: &str) -> Result<u64> {
        // Determining wallet age requires querying an Etherscan-like API
        // (e.g. Basescan) for the first transaction.  Return 0 as a
        // conservative default so the age gate is not trivially bypassed.
        Ok(0)
    }

    fn validate_address(&self, address: &str) -> Result<()> {
        // Base uses EVM addresses: 0x followed by 40 hex characters
        if !address.starts_with("0x") {
            return Err(crate::error::AirdropError::WalletVerification(
                "Base address must start with 0x".to_string(),
            ));
        }

        let hex_part = &address[2..];
        if hex_part.len() != 40 {
            return Err(crate::error::AirdropError::WalletVerification(format!(
                "Invalid Base address length: {} (expected 42)",
                address.len()
            )));
        }

        // Validate hex characters
        if !hex_part.chars().all(|c| c.is_ascii_hexdigit()) {
            return Err(crate::error::AirdropError::WalletVerification(
                "Base address contains invalid hex characters".to_string(),
            ));
        }

        Ok(())
    }

    fn calculate_tier(&self, balance_base_units: u64) -> WalletTier {
        // ETH has 18 decimals
        if balance_base_units >= 1_000_000_000_000_000_000 {
            // 1+ ETH
            WalletTier::High
        } else if balance_base_units >= 100_000_000_000_000_000 {
            // 0.1-1 ETH
            WalletTier::Mid
        } else {
            // 0.01-0.1 ETH
            WalletTier::Minimum
        }
    }
}

/// Factory function to create appropriate chain adapter
pub fn create_adapter(
    chain: TargetChain,
    rpc_url: String,
    min_balance: u64,
    min_age: u64,
) -> Box<dyn ChainAdapter> {
    match chain {
        TargetChain::Solana => Box::new(SolanaAdapter::new(rpc_url, min_balance, min_age)),
        TargetChain::Base => Box::new(BaseAdapter::new(rpc_url, min_balance, min_age)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_solana_address_validation_valid() {
        let adapter =
            SolanaAdapter::with_defaults("https://api.mainnet-beta.solana.com".to_string());

        // Valid Solana addresses
        assert!(adapter
            .validate_address("7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU")
            .is_ok());
        assert!(adapter
            .validate_address("9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM")
            .is_ok());
    }

    #[test]
    fn test_solana_address_validation_invalid() {
        let adapter =
            SolanaAdapter::with_defaults("https://api.mainnet-beta.solana.com".to_string());

        // Too short
        assert!(adapter.validate_address("tooshort").is_err());

        // Invalid base58 chars
        assert!(adapter
            .validate_address("0xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU")
            .is_err());
    }

    #[test]
    fn test_base_address_validation_valid() {
        let adapter = BaseAdapter::with_defaults("https://mainnet.base.org".to_string());

        // Valid Base addresses (0x + 40 hex chars = 42 total)
        assert!(adapter
            .validate_address("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1")
            .is_ok());
        assert!(adapter
            .validate_address("0x1234567890123456789012345678901234567890")
            .is_ok());
    }

    #[test]
    fn test_base_address_validation_invalid() {
        let adapter = BaseAdapter::with_defaults("https://mainnet.base.org".to_string());

        // Missing 0x prefix
        assert!(adapter
            .validate_address("742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
            .is_err());

        // Wrong length
        assert!(adapter.validate_address("0x1234").is_err());

        // Invalid hex
        assert!(adapter
            .validate_address("0xGGGG567890123456789012345678901234567890")
            .is_err());
    }

    #[test]
    fn test_solana_tier_calculation() {
        let adapter =
            SolanaAdapter::with_defaults("https://api.mainnet-beta.solana.com".to_string());

        // 0.05 SOL (below minimum)
        assert_eq!(adapter.calculate_tier(50_000_000), WalletTier::Minimum);

        // 0.5 SOL
        assert_eq!(adapter.calculate_tier(500_000_000), WalletTier::Minimum);

        // 5 SOL
        assert_eq!(adapter.calculate_tier(5_000_000_000), WalletTier::Mid);

        // 50 SOL
        assert_eq!(adapter.calculate_tier(50_000_000_000), WalletTier::High);
    }

    #[test]
    fn test_base_tier_calculation() {
        let adapter = BaseAdapter::with_defaults("https://mainnet.base.org".to_string());

        // 0.005 ETH (below minimum)
        assert_eq!(
            adapter.calculate_tier(5_000_000_000_000_000),
            WalletTier::Minimum
        );

        // 0.05 ETH
        assert_eq!(
            adapter.calculate_tier(50_000_000_000_000_000),
            WalletTier::Minimum
        );

        // 0.5 ETH
        assert_eq!(
            adapter.calculate_tier(500_000_000_000_000_000),
            WalletTier::Mid
        );

        // 5 ETH
        assert_eq!(
            adapter.calculate_tier(5_000_000_000_000_000_000),
            WalletTier::High
        );
    }

    // --- RPC balance tests (mocked HTTP) ---

    #[tokio::test]
    async fn test_solana_get_balance_from_rpc() {
        let mut mock = mockito::Server::new_async().await;
        let _m = mock
            .mock("POST", "/")
            .with_status(200)
            .with_header("content-type", "application/json")
            .with_body(
                r#"{"jsonrpc":"2.0","id":1,"result":{"context":{"slot":12345},"value":350000000}}"#,
            )
            .create_async()
            .await;

        let adapter = SolanaAdapter::new(mock.url(), 100_000_000, 7 * 24 * 60 * 60);
        let balance = adapter
            .get_balance("7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU")
            .await
            .unwrap();
        assert_eq!(balance, 350_000_000); // 0.35 SOL
    }

    #[tokio::test]
    async fn test_solana_get_balance_zero_on_missing() {
        let mut mock = mockito::Server::new_async().await;
        let _m = mock
            .mock("POST", "/")
            .with_status(200)
            .with_header("content-type", "application/json")
            .with_body(r#"{"jsonrpc":"2.0","id":1,"result":{"context":{"slot":12345},"value":0}}"#)
            .create_async()
            .await;

        let adapter = SolanaAdapter::new(mock.url(), 100_000_000, 7 * 24 * 60 * 60);
        let balance = adapter
            .get_balance("7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU")
            .await
            .unwrap();
        assert_eq!(balance, 0);
    }

    #[tokio::test]
    async fn test_solana_get_wallet_age_returns_zero() {
        let adapter =
            SolanaAdapter::with_defaults("https://api.mainnet-beta.solana.com".to_string());
        // Age is conservatively 0 since it requires historical tx data
        let age = adapter
            .get_wallet_age("7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU")
            .await
            .unwrap();
        assert_eq!(age, 0);
    }

    #[tokio::test]
    async fn test_base_get_balance_from_rpc() {
        let mut mock = mockito::Server::new_async().await;
        let _m = mock
            .mock("POST", "/")
            .with_status(200)
            .with_header("content-type", "application/json")
            .with_body(r#"{"jsonrpc":"2.0","id":1,"result":"0x16345785d8a0000"}"#)
            .create_async()
            .await;

        let adapter = BaseAdapter::new(mock.url(), 10_000_000_000_000_000, 7 * 24 * 60 * 60);
        let balance = adapter
            .get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1")
            .await
            .unwrap();
        assert_eq!(balance, 100_000_000_000_000_000); // 0.1 ETH
    }

    #[tokio::test]
    async fn test_base_get_balance_zero_on_empty() {
        let mut mock = mockito::Server::new_async().await;
        let _m = mock
            .mock("POST", "/")
            .with_status(200)
            .with_header("content-type", "application/json")
            .with_body(r#"{"jsonrpc":"2.0","id":1,"result":"0x0"}"#)
            .create_async()
            .await;

        let adapter = BaseAdapter::new(mock.url(), 10_000_000_000_000_000, 7 * 24 * 60 * 60);
        let balance = adapter
            .get_balance("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1")
            .await
            .unwrap();
        assert_eq!(balance, 0);
    }

    #[tokio::test]
    async fn test_base_get_wallet_age_returns_zero() {
        let adapter = BaseAdapter::with_defaults("https://mainnet.base.org".to_string());
        // Age is conservatively 0 since it requires historical tx data
        let age = adapter
            .get_wallet_age("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1")
            .await
            .unwrap();
        assert_eq!(age, 0);
    }
}
