//! `rustchain` — RustChain CLI wallet and utilities
//!
//! A command-line tool for interacting with the RustChain blockchain.
//!
//! # Quick Start
//!
//! ```bash
//! # Check wallet balance
//! rustchain balance --wallet C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg
//!
//! # Generate a new wallet
//! rustchain wallet generate
//!
//! # Validate an address
//! rustchain address validate C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg
//!
//! # Network stats
//! rustchain network stats
//!
//! # Miner info
//! rustchain miners list
//! ```

mod address;
mod api;
mod wallet;

use anyhow::Context;
use clap::{Parser, Subcommand};
use std::process;

/// RustChain CLI — interact with RustChain blockchain
#[derive(Parser, Debug)]
#[command(
    name = "rustchain",
    version,
    author,
    about = "RustChain CLI wallet and utilities",
    long_about = None,
)]
struct Cli {
    /// RPC node URL (or set RUSTCHAIN_RPC_URL env var)
    #[arg(short, long, env = "RUSTCHAIN_RPC_URL", default_value = "https://explorer.rustchain.org")]
    rpc_url: String,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Generate a new RTC wallet (Ed25519 key pair)
    Wallet {
        #[command(subcommand)]
        action: WalletAction,
    },

    /// Validate an RTC address
    Address {
        /// The RTC address to validate
        address: String,
    },

    /// Check wallet balance
    Balance {
        /// The wallet address to check
        #[arg(short, long)]
        wallet: String,
    },

    /// Show RustChain network stats
    Network {
        #[command(subcommand)]
        action: Option<NetworkAction>,
    },

    /// List and query miners
    Miners {
        #[command(subcommand)]
        action: Option<MinersAction>,
    },

    /// Epoch information
    Epoch {
        /// Show detailed epoch info
        #[arg(short, long)]
        detailed: bool,
    },

    /// Node health check
    Health {},

    /// Calculate epoch rewards for a given stake
    Rewards {
        /// Wallet or miner address
        #[arg(short, long)]
        wallet: String,

        /// Stake amount in RTC (default: query balance)
        #[arg(short, long)]
        stake: Option<f64>,
    },
}

#[derive(Subcommand, Debug)]
enum WalletAction {
    /// Generate a new Ed25519 key pair and RTC address
    Generate,
    /// Derive address from a secret seed (base58)
    FromSeed { seed: String },
    /// Derive address from a hex private key
    FromHex { private_key: String },
    /// Convert an Ed25519 public key to RTC address format
    PubkeyToAddress { pubkey: String },
}

#[derive(Subcommand, Debug)]
enum NetworkAction {
    /// Show overall network statistics
    Stats,
    /// Show all active nodes
    Nodes,
}

#[derive(Subcommand, Debug)]
enum MinersAction {
    /// List active miners
    List {
        /// Limit number of results
        #[arg(short, long, default_value_t = 20)]
        limit: usize,
    },
    /// Show details for a specific miner
    Info { miner_id: String },
    /// Show miner count
    Count {},
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

    let result = run(cli).await;

    if let Err(e) = &result {
        eprintln!("Error: {e}");
        eprintln!("{}", e.backtrace());
        process::exit(1);
    }

    Ok(result?)
}

// ─── Command dispatch ─────────────────────────────────────────────────────────

async fn run(cli: Cli) -> anyhow::Result<()> {
    match cli.command {
        Commands::Wallet { action } => wallet::run(action),
        Commands::Address { address } => address::validate_and_show(&address),
        Commands::Balance { wallet } => balance_cmd(&cli.rpc_url, &wallet).await,
        Commands::Network { action } => network_cmd(&cli.rpc_url, action).await,
        Commands::Miners { action } => miners_cmd(&cli.rpc_url, action).await,
        Commands::Epoch { detailed } => epoch_cmd(&cli.rpc_url, detailed).await,
        Commands::Health {} => health_cmd(&cli.rpc_url).await,
        Commands::Rewards { wallet, stake } => rewards_cmd(&cli.rpc_url, &wallet, stake).await,
    }
}

// ─── Commands ────────────────────────────────────────────────────────────────

async fn balance_cmd(rpc_url: &str, wallet: &str) -> anyhow::Result<()> {
    let client = api::Client::new(rpc_url)?;
    let balance = client.get_balance(wallet).await
        .with_context(|| format!("Failed to fetch balance for {wallet}"))?;

    println!("Wallet: {wallet}");
    println!("Balance: {balance} RTC");
    Ok(())
}

async fn network_cmd(rpc_url: &str, action: Option<NetworkAction>) -> anyhow::Result<()> {
    let client = api::Client::new(rpc_url)?;

    match action {
        Some(NetworkAction::Stats) => {
            let stats = client.get_network_stats().await?;
            println!("=== RustChain Network Stats ===");
            println!("Total Miners: {}", stats.miners_total);
            println!("Active Miners: {}", stats.miners_active);
            println!("Current Epoch: {}", stats.current_epoch);
            println!("Epoch Ends: {}", stats.epoch_end);
            println!("Total Supply: {} RTC", stats.total_supply_rtc);
            if let Some(v) = stats.avg_antiquity { println!("Avg Antiquity: {v:.2}x"); }
            println!("API Endpoint: {rpc_url}");
        }
        Some(NetworkAction::Nodes) => {
            let nodes = client.get_nodes().await?;
            println!("=== RustChain Nodes ===");
            for (i, node) in nodes.iter().enumerate() {
                println!("Node {}: {} ({})", i + 1, node.url, node.status);
            }
        }
        None => {
            let stats = client.get_network_stats().await?;
            println!("Network: {}", rpc_url);
            println!("Epoch: {} | Miners: {}/{} | Supply: {} RTC",
                stats.current_epoch, stats.miners_active, stats.miners_total, stats.total_supply_rtc);
        }
    }
    Ok(())
}

async fn miners_cmd(rpc_url: &str, action: Option<MinersAction>) -> anyhow::Result<()> {
    let client = api::Client::new(rpc_url)?;

    match action {
        Some(MinersAction::List { limit }) => {
            let miners = client.list_miners(limit).await?;
            println!("{:≤12} {:≤12} {:≥8} {:≥10} {:≥15}", "Status", "Arch", "Blocks", "Antiquity", "Last Attestation");
            println!("{}", "-".repeat(65));
            for m in miners {
                let age_mins = (chrono::Utc::now().timestamp() - m.last_attestation / 1000) / 60;
                let age_str = if age_mins < 1 { "<1m ago".to_string() }
                    else { format!("{}m ago", age_mins) };
                println!("{:≤12} {:≤12} {:≥8} {:≥10.2}x {:≥15}",
                    m.status, m.architecture, m.blocks_mined, m.antiquity, age_str);
            }
        }
        Some(MinersAction::Info { miner_id }) => {
            let info = client.get_miner_info(&miner_id).await?;
            println!("=== Miner: {miner_id} ===");
            println!("Architecture: {}", info.architecture);
            println!("Status: {}", info.status);
            println!("Antiquity: {}x", info.antiquity);
            println!("Blocks Mined: {}", info.blocks_mined);
            println!("Balance: {} RTC", info.balance);
            let ts = info.last_attestation / 1000;
            if ts > 0 {
                println!("Last Attestation: {} ({} ago)",
                    chrono::DateTime::from_timestamp(ts, 0).map(|dt| dt.to_rfc3339()).unwrap_or_default(),
                    humantime::format_duration(std::time::Duration::from_secs(
                        (chrono::Utc::now().timestamp() - ts).max(0) as u64
                    ))
                );
            }
        }
        Some(MinersAction::Count {}) => {
            let stats = client.get_network_stats().await?;
            println!("Active miners: {}", stats.miners_active);
            println!("Total miners: {}", stats.miners_total);
        }
        None => {
            let stats = client.get_network_stats().await?;
            println!("Miners: {}/{} (active/total)",
                stats.miners_active, stats.miners_total);
        }
    }
    Ok(())
}

async fn epoch_cmd(rpc_url: &str, detailed: bool) -> anyhow::Result<()> {
    let client = api::Client::new(rpc_url)?;
    let epoch = client.get_epoch().await?;

    println!("Epoch #{}", epoch.number);
    println!("Start: {}", epoch.start_time);
    println!("End: {}", epoch.end_time);

    if detailed {
        println!("Rewards per block: {} RTC", epoch.reward_per_block);
        println!("Total blocks: {}", epoch.total_blocks);
        println!("Miners participated: {}", epoch.active_miners);
        if let Some(dist) = &epoch.reward_distribution {
            println!("Reward distribution: {dist}");
        }
    }
    Ok(())
}

async fn health_cmd(rpc_url: &str) -> anyhow::Result<()> {
    let client = api::Client::new(rpc_url)?;
    let health = client.health_check().await?;

    let status_icon = if health.healthy { "✅" } else { "❌" };
    println!("{status_icon} RustChain Node: {}", if health.healthy { "HEALTHY" } else { "UNHEALTHY" });
    if let Some(msg) = &health.message {
        println!("  Message: {msg}");
    }
    println!("  Uptime: {}", humantime::format_duration(std::time::Duration::from_secs(health.uptime_secs as u64)));
    println!("  Peers: {}", health.peers);
    println!("  Block height: {}", health.block_height);

    Ok(())
}

async fn rewards_cmd(rpc_url: &str, wallet: &str, stake: Option<f64>) -> anyhow::Result<()> {
    let client = api::Client::new(rpc_url)?;
    let balance = client.get_balance(wallet).await.unwrap_or(0.0);
    let effective_stake = stake.unwrap_or(balance);
    let stats = client.get_network_stats().await?;
    let avg_antiq = stats.avg_antiquity.unwrap_or(1.0);

    // Rough reward estimate: base reward × stake × antiquity multiplier
    let base_reward_per_epoch = 10.0; // RTC per epoch (example)
    let estimated = effective_stake * avg_antiq * base_reward_per_epoch / stats.total_supply_rtc.max(1.0);

    println!("Wallet: {wallet}");
    println!("Effective stake: {effective_stake} RTC");
    println!("Antiquity multiplier: {avg_antiq:.2}x");
    println!("Estimated epoch reward: ~{:.4} RTC", estimated);

    Ok(())
}
