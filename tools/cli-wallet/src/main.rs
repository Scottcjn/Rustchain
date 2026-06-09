// SPDX-License-Identifier: MIT

use anyhow::{anyhow, Result};
use clap::{Parser, Subcommand};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::Path;

#[derive(Parser)]
#[command(name = "rustchain-wallet")]
#[command(about = "RustChain CLI Wallet", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Generate a new wallet address
    Generate {
        /// Output file for the wallet
        #[arg(short, long, default_value = "wallet.json")]
        output: String,
    },
    /// Check wallet balance
    Balance {
        /// Wallet file path
        #[arg(short, long, default_value = "wallet.json")]
        wallet: String,
        /// RustChain node URL
        #[arg(short, long, default_value = "http://localhost:8080")]
        node: String,
    },
    /// Send RTC tokens
    Send {
        /// Wallet file path
        #[arg(short, long, default_value = "wallet.json")]
        wallet: String,
        /// Recipient address
        #[arg(short, long)]
        to: String,
        /// Amount to send
        #[arg(short, long)]
        amount: u64,
        /// RustChain node URL
        #[arg(short, long, default_value = "http://localhost:8080")]
        node: String,
    },
    /// Receive tokens (display address)
    Receive {
        /// Wallet file path
        #[arg(short, long, default_value = "wallet.json")]
        wallet: String,
    },
    /// Validate an address
    Validate {
        /// Address to validate
        address: String,
    },
}

#[derive(Serialize, Deserialize, Debug)]
struct Wallet {
    address: String,
    private_key: String,
    public_key: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct Transaction {
    from: String,
    to: String,
    amount: u64,
    timestamp: u64,
    signature: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct BalanceResponse {
    address: Option<String>,
    miner_id: Option<String>,
    balance: Option<f64>,
    amount_i64: Option<i64>,
    amount_rtc: Option<f64>,
}

#[derive(Serialize, Deserialize, Debug)]
struct TransactionResponse {
    success: bool,
    message: String,
    transaction_id: Option<String>,
}

impl Wallet {
    fn new() -> Result<Self> {
        use rand::rngs::OsRng;
        use rand::RngCore;
        use secp256k1::{PublicKey, Secp256k1, SecretKey};

        let secp = Secp256k1::new();
        let mut rng = OsRng;
        let secret_key = loop {
            let mut secret_bytes = [0u8; 32];
            rng.fill_bytes(&mut secret_bytes);
            if let Ok(secret_key) = SecretKey::from_slice(&secret_bytes) {
                break secret_key;
            }
        };
        let public_key = PublicKey::from_secret_key(&secp, &secret_key);
        
        let private_key = hex::encode(secret_key.as_ref());
        let public_key_bytes = public_key.serialize();
        let public_key_hex = hex::encode(public_key_bytes);
        
        // Keep this legacy CLI aligned with the canonical RustChain address format:
        // RTC + the first 40 hex characters of SHA-256(public key bytes).
        let mut hasher = Sha256::new();
        hasher.update(&public_key_bytes);
        let hash = hasher.finalize();
        let address = format!("RTC{}", &hex::encode(hash)[..40]);
        
        Ok(Wallet {
            address,
            private_key,
            public_key: public_key_hex,
        })
    }
    
    fn load_from_file<P: AsRef<Path>>(path: P) -> Result<Self> {
        let content = fs::read_to_string(path)?;
        let wallet: Wallet = serde_json::from_str(&content)?;
        Ok(wallet)
    }
    
    fn save_to_file<P: AsRef<Path>>(&self, path: P) -> Result<()> {
        let content = serde_json::to_string_pretty(self)?;
        fs::write(path, content)?;
        Ok(())
    }
    
    fn sign_transaction(&self, transaction: &Transaction) -> Result<String> {
        // Create transaction hash
        let tx_data = format!(
            "{}{}{}{}",
            transaction.from, transaction.to, transaction.amount, transaction.timestamp
        );
        
        let mut hasher = Sha256::new();
        hasher.update(tx_data.as_bytes());
        let hash = hasher.finalize();
        
        // In a real implementation, this would use the private key to sign
        // For this demo, we'll create a mock signature
        let signature = hex::encode(hash);
        Ok(signature)
    }
}

fn validate_address(address: &str) -> bool {
    if !address.starts_with("RTC") {
        return false;
    }

    let addr_part = &address[3..];
    addr_part.len() == 40 && addr_part.chars().all(|c| c.is_ascii_hexdigit())
}

impl BalanceResponse {
    fn balance_rtc(&self) -> Option<f64> {
        self.amount_rtc
            .or_else(|| self.amount_i64.map(|amount| amount as f64 / 1_000_000.0))
            .or(self.balance)
    }
}

fn balance_url(node_url: &str, address: &str) -> Result<reqwest::Url> {
    let base = node_url.trim_end_matches('/');
    let mut url = reqwest::Url::parse(&format!("{}/wallet/balance", base))?;
    url.query_pairs_mut().append_pair("miner_id", address);
    Ok(url)
}

async fn get_balance(node_url: &str, address: &str) -> Result<f64> {
    let client = reqwest::Client::new();
    let url = balance_url(node_url, address)?;
    
    match client.get(url).send().await {
        Ok(response) => {
            if response.status().is_success() {
                let balance_response: BalanceResponse = response.json().await?;
                balance_response
                    .balance_rtc()
                    .ok_or_else(|| anyhow!("Balance response missing amount_rtc/amount_i64"))
            } else {
                // If API doesn't exist, return mock balance
                println!("Note: Using mock balance (node API not available)");
                Ok(1000.0) // Mock balance
            }
        }
        Err(_) => {
            println!("Note: Using mock balance (node not reachable)");
            Ok(1000.0) // Mock balance when node is not available
        }
    }
}

async fn send_transaction(
    node_url: &str,
    wallet: &Wallet,
    to: &str,
    amount: u64,
) -> Result<String> {
    let transaction = Transaction {
        from: wallet.address.clone(),
        to: to.to_string(),
        amount,
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_secs(),
        signature: String::new(),
    };
    
    let signature = wallet.sign_transaction(&transaction)?;
    let mut signed_transaction = transaction;
    signed_transaction.signature = signature;

    let client = reqwest::Client::new();
    let url = format!("{}/api/transaction", node_url.trim_end_matches('/'));
    
    let response = client
        .post(&url)
        .json(&signed_transaction)
        .send()
        .await
        .map_err(|err| anyhow!("Transaction submission failed: {}", err))?;

    let status = response.status();
    if !status.is_success() {
        return Err(anyhow!("Transaction endpoint returned HTTP {}", status));
    }

    let tx_response: TransactionResponse = response.json().await?;
    if tx_response.success {
        Ok(tx_response.transaction_id.unwrap_or_else(|| "unknown".to_string()))
    } else {
        Err(anyhow!("Transaction failed: {}", tx_response.message))
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    
    match &cli.command {
        Some(Commands::Generate { output }) => {
            println!("Generating new wallet...");
            let wallet = Wallet::new()?;
            wallet.save_to_file(output)?;
            println!("✅ Wallet generated successfully!");
            println!("Address: {}", wallet.address);
            println!("Saved to: {}", output);
        }
        
        Some(Commands::Balance { wallet, node }) => {
            let wallet_data = Wallet::load_from_file(wallet)?;
            println!("Checking balance for: {}", wallet_data.address);
            
            let balance = get_balance(node, &wallet_data.address).await?;
            println!("💰 Balance: {:.6} RTC", balance);
        }
        
        Some(Commands::Send { wallet, to, amount, node }) => {
            if !validate_address(to) {
                return Err(anyhow!("Invalid recipient address: {}", to));
            }
            
            let wallet_data = Wallet::load_from_file(wallet)?;
            println!("Sending {} RTC from {} to {}", amount, wallet_data.address, to);
            
            // Check balance first
            let balance = get_balance(node, &wallet_data.address).await?;
            if balance < *amount as f64 {
                return Err(anyhow!(
                    "Insufficient balance. Available: {:.6} RTC, Required: {} RTC",
                    balance,
                    amount
                ));
            }
            
            let tx_id = send_transaction(node, &wallet_data, to, *amount).await?;
            println!("✅ Transaction sent successfully!");
            println!("Transaction ID: {}", tx_id);
        }
        
        Some(Commands::Receive { wallet }) => {
            let wallet_data = Wallet::load_from_file(wallet)?;
            println!("📨 Your RustChain address:");
            println!("{}", wallet_data.address);
            println!("");
            println!("Share this address to receive RTC tokens.");
        }
        
        Some(Commands::Validate { address }) => {
            if validate_address(address) {
                println!("✅ Valid RustChain address: {}", address);
            } else {
                println!("❌ Invalid RustChain address: {}", address);
            }
        }
        
        None => {
            println!("RustChain CLI Wallet");
            println!("Use --help for available commands");
        }
    }
    
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_address_validation() {
        assert!(validate_address("RTC0123456789abcdef0123456789abcdef01234567"));
        assert!(!validate_address("invalid_address"));
        assert!(!validate_address("BTC0123456789abcdef0123456789abcdef01234567"));
        assert!(!validate_address("RTC1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"));
        assert!(!validate_address("RTC0123456789abcdef0123456789abcdef0123456"));
        assert!(!validate_address("RTC0123456789abcdef0123456789abcdef012345678"));
        assert!(!validate_address("RTC0123456789abcdef0123456789abcdef0123456z"));
    }
    
    #[test]
    fn test_wallet_generation() {
        let wallet = Wallet::new().unwrap();
        assert!(wallet.address.starts_with("RTC"));
        assert!(validate_address(&wallet.address));
        assert!(!wallet.private_key.is_empty());
        assert!(!wallet.public_key.is_empty());
    }

    #[test]
    fn test_balance_url_uses_current_wallet_endpoint() {
        let url = balance_url(
            "https://rustchain.org/",
            "RTC0123456789abcdef0123456789abcdef01234567",
        )
        .unwrap();

        assert_eq!(
            url.as_str(),
            "https://rustchain.org/wallet/balance?miner_id=RTC0123456789abcdef0123456789abcdef01234567"
        );
    }

    #[test]
    fn test_balance_response_parses_current_schema() {
        let response: BalanceResponse = serde_json::from_str(
            r#"{"amount_i64":118357193,"amount_rtc":118.357193,"miner_id":"alice"}"#,
        )
        .unwrap();

        assert_eq!(response.balance_rtc(), Some(118.357193));
    }

    #[test]
    fn test_balance_response_falls_back_to_micro_units() {
        let response: BalanceResponse =
            serde_json::from_str(r#"{"amount_i64":1250000,"miner_id":"alice"}"#).unwrap();

        assert_eq!(response.balance_rtc(), Some(1.25));
    }

    #[test]
    fn test_balance_response_keeps_legacy_balance_compatible() {
        let response: BalanceResponse =
            serde_json::from_str(r#"{"address":"alice","balance":42}"#).unwrap();

        assert_eq!(response.balance_rtc(), Some(42.0));
    }
    
    #[tokio::test]
    async fn test_transaction_signing() {
        let wallet = Wallet::new().unwrap();
        let transaction = Transaction {
            from: wallet.address.clone(),
            to: "RTC89abcdef0123456789abcdef0123456789abcdef".to_string(),
            amount: 100,
            timestamp: 1234567890,
            signature: String::new(),
        };
        
        let signature = wallet.sign_transaction(&transaction).unwrap();
        assert!(!signature.is_empty());
        assert_eq!(signature.len(), 64); // SHA256 hash as hex
    }
}
