//! RustChain CLI - Command line wallet and toolkit
//! 
//! A Rust implementation of RustChain utilities for the bounty:
//! [BOUNTY: 25-150 RTC] Build RustChain Tools & Features in Rust

use clap::{Parser, Subcommand};
use rand::Rng;
use reqwest::Client;
use serde::Deserialize;
use std::collections::HashMap;

// API Base URL
const API_BASE: &str = "https://rustchain.org";

/// Health check response
#[derive(Debug, Deserialize)]
struct HealthResponse {
    ok: bool,
    version: String,
    #[serde(rename = "uptime_s")]
    uptime_s: u64,
    #[serde(rename = "db_rw")]
    db_rw: bool,
}

/// Epoch info response
#[derive(Debug, Deserialize)]
struct EpochResponse {
    epoch: u64,
    slot: u64,
    #[serde(rename = "blocks_per_epoch")]
    blocks_per_epoch: u64,
    #[serde(rename = "enrolled_miners")]
    enrolled_miners: u64,
    #[serde(rename = "epoch_pot")]
    epoch_pot: f64,
    #[serde(rename = "total_supply_rtc")]
    total_supply_rtc: f64,
}

/// Miner info
#[derive(Debug, Deserialize)]
struct Miner {
    miner: String,
    #[serde(rename = "antiquity_multiplier")]
    antiquity_multiplier: f64,
    #[serde(rename = "hardware_type")]
    hardware_type: String,
    #[serde(rename = "entropy_score")]
    entropy_score: f64,
}

/// Wallet balance response
#[derive(Debug, Deserialize)]
struct BalanceResponse {
    #[serde(rename = "miner_id")]
    miner_id: String,
    #[serde(rename = "amount_rtc")]
    amount_rtc: Option<f64>,
    #[serde(rename = "amount_i64")]
    amount_i64: Option<i64>,
    // For API responses that use different field names
    #[serde(default)]
    balance: f64,
    #[serde(default)]
    wallet: String,
}

/// CLI Arguments
#[derive(Parser)]
#[command(name = "rustchain")]
#[command(about = "RustChain CLI - Wallet and node utilities", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Check node health status
    Health,
    /// Get current epoch information
    Epoch,
    /// List active miners
    Miners {
        /// Number of miners to display (default: 10)
        #[arg(short, long, default_value = "10")]
        limit: usize,
    },
    /// Check wallet balance
    Balance {
        /// Wallet address to check
        wallet: String,
    },
    /// Get node statistics
    Stats,
    /// Generate or validate RTC wallet addresses
    Address {
        #[command(subcommand)]
        action: AddressCommands,
    },
}

#[derive(Subcommand)]
enum AddressCommands {
    /// Generate a new RTC wallet address
    Generate {
        /// Length of the random part (default: 16)
        #[arg(short, long, default_value = "16")]
        length: usize,
        /// Include prefix (default: RTC)
        #[arg(short, long, default_value = "RTC")]
        prefix: String,
    },
    /// Validate an RTC address format
    Validate {
        /// Wallet address to validate
        address: String,
    },
    /// Verify an address exists on the network
    Verify {
        /// Wallet address to verify
        address: String,
    },
}

/// Get HTTP client
fn get_client() -> Client {
    Client::builder()
        .danger_accept_invalid_certs(true)
        .build()
        .expect("Failed to create HTTP client")
}

/// Print health info
async fn cmd_health(client: &Client) -> Result<(), Box<dyn std::error::Error>> {
    let url = format!("{}/health", API_BASE);
    let response = client.get(&url).send().await?;
    let health: HealthResponse = response.json().await?;
    
    println!("\n🟢 RustChain Node Health");
    println!("=========================");
    println!("Status:    {}", if health.ok { "Healthy ✓" } else { "Unhealthy ✗" });
    println!("Version:   {}", health.version);
    println!("Uptime:    {} seconds", health.uptime_s);
    println!("Database:  {}", if health.db_rw { "Read/Write" } else { "Read-only" });
    
    Ok(())
}

/// Print epoch info
async fn cmd_epoch(client: &Client) -> Result<(), Box<dyn std::error::Error>> {
    let url = format!("{}/epoch", API_BASE);
    let response = client.get(&url).send().await?;
    let epoch: EpochResponse = response.json().await?;
    
    println!("\n⏱️  Current Epoch Information");
    println!("=============================");
    println!("Epoch:           {}", epoch.epoch);
    println!("Slot:            {}", epoch.slot);
    println!("Blocks/Epoch:    {}", epoch.blocks_per_epoch);
    println!("Enrolled Miners: {}", epoch.enrolled_miners);
    println!("Epoch PoT:       {}", epoch.epoch_pot);
    
    Ok(())
}

/// Print miners list
async fn cmd_miners(client: &Client, limit: usize) -> Result<(), Box<dyn std::error::Error>> {
    let url = format!("{}/api/miners", API_BASE);
    let response = client.get(&url).send().await?;
    let miners: Vec<Miner> = response.json().await?;
    
    println!("\n⛏️  Active Miners (Top {})", limit);
    println!("{}", "-".repeat(40));
    println!("{:<4} {:<30} {:<15} {:<10}", "#", "Miner", "Hardware", "Multiplier");
    println!("{}", "-".repeat(65));
    
    for (i, miner) in miners.iter().take(limit).enumerate() {
        let i = i + 1;
        let miner_short = if miner.miner.len() > 28 {
            format!("{}...", &miner.miner[..25])
        } else {
            miner.miner.clone()
        };
        println!("{:<4} {:<30} {:<15} {:.2}x", 
            i, 
            miner_short, 
            miner.hardware_type, 
            miner.antiquity_multiplier
        );
    }
    
    // Statistics
    let total = miners.len();
    let multipliers: Vec<f64> = miners.iter().map(|m| m.antiquity_multiplier).collect();
    let avg_mult = multipliers.iter().sum::<f64>() / total as f64;
    
    // Hardware distribution
    let mut hw_counts: HashMap<String, usize> = HashMap::new();
    for miner in &miners {
        *hw_counts.entry(miner.hardware_type.clone()).or_insert(0) += 1;
    }
    
    let mut hw_vec: Vec<_> = hw_counts.iter().collect();
    hw_vec.sort_by(|a, b| b.1.cmp(a.1));
    
    println!("\n📊 Statistics");
    println!("Total Miners: {}", total);
    println!("Avg Multiplier: {:.2}x", avg_mult);
    println!("\nHardware Distribution:");
    for (hw, count) in hw_vec {
        println!("  {}: {}", hw, count);
    }
    
    Ok(())
}

/// Print wallet balance
async fn cmd_balance(client: &Client, wallet: &str) -> Result<(), Box<dyn std::error::Error>> {
    let url = format!("{}/api/balance/{}", API_BASE, wallet);
    let response = client.get(&url).send().await?;
    
    if response.status() == 404 {
        println!("\n⚠️  Wallet not found or has no balance");
        return Ok(());
    }
    
    let balance: BalanceResponse = response.json().await?;
    
    println!("\n💰 Wallet Balance");
    println!("==================");
    println!("Wallet:  {}", balance.wallet);
    println!("Balance: {:.8} RTC", balance.balance);
    
    Ok(())
}

/// Print node statistics
async fn cmd_stats(client: &Client) -> Result<(), Box<dyn std::error::Error>> {
    // Get epoch
    let epoch_url = format!("{}/epoch", API_BASE);
    let epoch_response = client.get(&epoch_url).send().await?;
    let epoch: EpochResponse = epoch_response.json().await?;
    
    // Get miners
    let miners_url = format!("{}/api/miners", API_BASE);
    let miners_response = client.get(&miners_url).send().await?;
    let miners: Vec<Miner> = miners_response.json().await?;
    
    println!("\n📈 RustChain Node Statistics");
    println!("============================");
    println!("Current Epoch:    {}", epoch.epoch);
    println!("Current Slot:      {}", epoch.slot);
    println!("Blocks/Epoch:     {}", epoch.blocks_per_epoch);
    println!("Enrolled Miners:  {}", epoch.enrolled_miners);
    println!("Total Miners:     {}", miners.len());
    println!("Epoch PoT:         {}", epoch.epoch_pot);
    
    // Calculate total score
    let total_score: f64 = miners.iter().map(|m| m.entropy_score).sum();
    println!("Total Network Score: {:.2}", total_score);
    
    Ok(())
}

/// Generate a random RTC wallet address
fn cmd_address_generate(length: usize, prefix: &str) -> Result<(), Box<dyn std::error::Error>> {
    let mut rng = rand::thread_rng();
    let chars: Vec<char> = "abcdefghijklmnopqrstuvwxyz0123456789-_".chars().collect();
    let random_part: String = (0..length)
        .map(|_| chars[rng.gen_range(0..chars.len())])
        .collect();
    
    let address = format!("{}-{}", prefix.to_uppercase(), random_part);
    
    println!("\n� Generated RTC Wallet Address");
    println!("===============================");
    println!("Address: {}", address);
    println!("Prefix:  {}", prefix.to_uppercase());
    println!("Length:  {} characters", length);
    println!("\n⚠️  IMPORTANT: Save this address securely!");
    println!("     This is your wallet identifier on the RustChain network.");
    
    Ok(())
}

/// Validate RTC address format
fn cmd_address_validate(address: &str) -> Result<(), Box<dyn std::error::Error>> {
    let parts: Vec<&str> = address.split('-').collect();
    
    println!("\n🔍 RTC Address Validation");
    println!("===========================");
    println!("Address: {}", address);
    
    // Check format
    if parts.len() < 2 {
        println!("❌ Invalid: Address must contain a prefix and identifier separated by '-'");
        println!("   Expected format: PREFIX-identifier (e.g., RTC-abc123)");
        return Ok(());
    }
    
    let prefix = parts[0];
    let identifier = parts[1..].join("-");
    
    // Validate prefix
    let valid_prefixes = ["RTC", "WALLET", "NODE", "MINER"];
    let prefix_upper = prefix.to_uppercase();
    
    if !valid_prefixes.contains(&prefix_upper.as_str()) {
        println!("⚠️  Warning: Prefix '{}' is not standard.", prefix);
        println!("   Standard prefixes: {}", valid_prefixes.join(", "));
    } else {
        println!("✓ Prefix: {} (valid)", prefix_upper);
    }
    
    // Validate identifier
    let valid_chars = identifier.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_');
    
    if identifier.len() < 3 {
        println!("❌ Invalid: Identifier too short (minimum 3 characters)");
    } else if identifier.len() > 64 {
        println!("❌ Invalid: Identifier too long (maximum 64 characters)");
    } else if !valid_chars {
        println!("❌ Invalid: Identifier contains invalid characters");
    } else {
        println!("✓ Identifier: {} (valid)", identifier);
    }
    
    // Overall result
    let is_valid = parts.len() >= 2 && identifier.len() >= 3 && identifier.len() <= 64 && valid_chars;
    
    println!("\nResult: {}", if is_valid { "✅ VALID" } else { "❌ INVALID" });
    
    Ok(())
}

/// Verify address exists on the network
async fn cmd_address_verify(client: &Client, address: &str) -> Result<(), Box<dyn std::error::Error>> {
    let url = format!("{}/wallet/balance?miner_id={}", API_BASE, address);
    let response = client.get(&url).send().await?;
    
    println!("\n🔗 Network Address Verification");
    println!("===================================");
    println!("Address: {}", address);
    println!("Network: {}", API_BASE);
    
    if response.status() == 404 {
        println!("\n⚠️  Address not found on network");
        println!("   The address may not be registered yet.");
    } else if response.status() == 200 {
        let balance: BalanceResponse = response.json().await?;
        let amount = balance.amount_rtc.unwrap_or(balance.balance);
        println!("\n✅ Address verified on network!");
        println!("   Miner ID: {}", balance.miner_id);
        println!("   Balance: {:.8} RTC", amount);
    } else {
        println!("\n❌ Error: Unexpected response status: {}", response.status());
    }
    
    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    let client = get_client();
    
    match cli.command {
        Commands::Health => {
            cmd_health(&client).await?;
        }
        Commands::Epoch => {
            cmd_epoch(&client).await?;
        }
        Commands::Miners { limit } => {
            cmd_miners(&client, limit).await?;
        }
        Commands::Balance { wallet } => {
            cmd_balance(&client, &wallet).await?;
        }
        Commands::Stats => {
            cmd_stats(&client).await?;
        }
        Commands::Address { action } => {
            match action {
                AddressCommands::Generate { length, prefix } => {
                    cmd_address_generate(length, &prefix)?;
                }
                AddressCommands::Validate { address } => {
                    cmd_address_validate(&address)?;
                }
                AddressCommands::Verify { address } => {
                    cmd_address_verify(&client, &address).await?;
                }
            }
        }
    }
    
    Ok(())
}
