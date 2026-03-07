//! RustChain Native Miner
//! 
//! A native Rust implementation of the RustChain miner with support for:
//! - Hardware detection and attestation
//! - Epoch enrollment loop
//! - Balance checking
//! - Dry-run, show-payload, and test-only modes
//! 
//! Bounty #734 Phase-1 Implementation

mod api;
mod attestation;
mod hardware;
mod types;

use anyhow::Result;
use attestation::AttestationManager;
use clap::{Parser, Subcommand};
use tracing::{error, info, Level};
use tracing_subscriber::FmtSubscriber;

use types::MinerConfig;

/// RustChain Native Miner - Proof of Antiquity
#[derive(Parser)]
#[command(name = "rustchain-miner")]
#[command(author = "RustChain Contributors")]
#[command(version = "0.1.0")]
#[command(about = "Native Rust miner for RustChain PoA blockchain", long_about = None)]
struct Cli {
    /// Node URL
    #[arg(short, long, default_value = "https://rustchain.org", env = "RUSTCHAIN_NODE")]
    node: String,

    /// Wallet identifier
    #[arg(short, long, env = "RUSTCHAIN_WALLET")]
    wallet: Option<String>,

    /// Attestation interval in seconds
    #[arg(short, long, default_value = "300")]
    interval: u64,

    /// Enable verbose logging
    #[arg(short, long)]
    verbose: bool,

    /// Skip TLS certificate verification (for self-signed certs)
    #[arg(long)]
    insecure_skip_verify: bool,

    /// Subcommands
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Start mining (default behavior)
    Mine {
        /// Dry-run mode: simulate without making API calls
        #[arg(long)]
        dry_run: bool,

        /// Show payload: print request payloads without sending
        #[arg(long)]
        show_payload: bool,

        /// Test-only: validate locally without network calls
        #[arg(long)]
        test_only: bool,

        /// Run a single attestation cycle then exit
        #[arg(long)]
        once: bool,
    },

    /// Check wallet balance
    Balance {
        /// Wallet/miner ID to check
        #[arg(short, long)]
        miner_id: Option<String>,
    },

    /// Show hardware information
    Hardware,

    /// Run a single attestation cycle
    Attest {
        /// Dry-run mode
        #[arg(long)]
        dry_run: bool,

        /// Show payload
        #[arg(long)]
        show_payload: bool,
    },

    /// List active miners
    Miners,

    /// Check node health
    Health,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    // Initialize logging
    let log_level = if cli.verbose {
        Level::DEBUG
    } else {
        Level::INFO
    };
    let subscriber = FmtSubscriber::builder()
        .with_max_level(log_level)
        .with_target(false)
        .finish();
    tracing::subscriber::set_global_default(subscriber)?;

    // Build config
    let wallet = cli.wallet.clone().unwrap_or_default();
    let mut config = MinerConfig::new(wallet)
        .with_node_url(cli.node.clone())
        .with_verbose(cli.verbose)
        .with_insecure_skip_verify(cli.insecure_skip_verify);

    // Execute command
    match cli.command {
        Some(Commands::Mine {
            dry_run,
            show_payload,
            test_only,
            once,
        }) => {
            config = config
                .with_dry_run(dry_run)
                .with_show_payload(show_payload)
                .with_test_only(test_only);

            if once {
                cmd_mine_once(config).await?;
            } else {
                cmd_mine(config).await?;
            }
        }

        Some(Commands::Balance { miner_id }) => {
            cmd_balance(config, miner_id).await?;
        }

        Some(Commands::Hardware) => {
            cmd_hardware()?;
        }

        Some(Commands::Attest {
            dry_run,
            show_payload,
        }) => {
            config = config.with_dry_run(dry_run).with_show_payload(show_payload);
            cmd_attest(config).await?;
        }

        Some(Commands::Miners) => {
            cmd_miners(config).await?;
        }

        Some(Commands::Health) => {
            cmd_health(config).await?;
        }

        None => {
            // Default: start mining
            cmd_mine(config).await?;
        }
    }

    Ok(())
}

/// Start mining with attestation loop
async fn cmd_mine(config: MinerConfig) -> Result<()> {
    info!("Starting RustChain miner...");
    info!("Node: {}", config.node_url);

    if config.dry_run {
        info!("Mode: DRY-RUN (no actual API calls)");
    } else if config.show_payload {
        info!("Mode: SHOW-PAYLOAD (printing payloads)");
    } else if config.test_only {
        info!("Mode: TEST-ONLY (local validation only)");
    }

    let manager = AttestationManager::new(config).await?;

    println!("\n╔═══════════════════════════════════════════════════════════╗");
    println!("║         RustChain Miner - Proof of Antiquity              ║");
    println!("╠═══════════════════════════════════════════════════════════╣");
    println!("║ Miner ID: {:<52} ║", truncate(&manager.miner_id(), 52));
    println!("║ Node:     {:<52} ║", truncate(&manager.config().node_url, 52));
    println!("║ Hardware: {:<52} ║", truncate(&manager.hardware().model, 52));
    println!("║ Cores:    {:<52} ║", manager.hardware().cores.to_string());
    println!("║ RAM:      {:<52} ║", 
        format!("{} GB", manager.hardware().total_ram_bytes / (1024 * 1024 * 1024)));
    println!("╚═══════════════════════════════════════════════════════════╝\n");

    manager.run_loop().await?;

    Ok(())
}

/// Run a single attestation cycle
async fn cmd_mine_once(config: MinerConfig) -> Result<()> {
    info!("Running single attestation cycle...");

    let manager = AttestationManager::new(config).await?;
    
    match manager.attest_once().await {
        Ok(result) => {
            println!("\n✅ Attestation successful!");
            println!("   Epoch: {}", result.epoch);
            println!("   Weight: {}", result.weight);
            println!("   Message: {}", result.message);
        }
        Err(e) => {
            println!("\n❌ Attestation failed: {}", e);
            error!("Attestation failed: {}", e);
        }
    }

    Ok(())
}

/// Check wallet balance
async fn cmd_balance(config: MinerConfig, miner_id: Option<String>) -> Result<()> {
    let client = api::ApiClient::new(&config)?;
    
    let id = miner_id.filter(|s| !s.is_empty()).or_else(|| {
        if config.wallet.is_empty() {
            None
        } else {
            Some(config.wallet.clone())
        }
    }).ok_or_else(|| {
        anyhow::anyhow!("Miner ID required. Use --miner-id or set RUSTCHAIN_WALLET")
    })?;

    match client.get_balance(&id).await {
        Ok(balance) => {
            println!("\n╔═══════════════════════════════════════════════════════════╗");
            println!("║              RustChain Wallet Balance                     ║");
            println!("╠═══════════════════════════════════════════════════════════╣");
            println!("║ Miner ID: {:<52} ║", truncate(&balance.miner_id, 52));
            println!("║ Balance:  {:<52} ║", format!("{:.6} RTC", balance.amount_rtc));
            println!("║ Micro:    {:<52} ║", balance.amount_i64.to_string());
            println!("╚═══════════════════════════════════════════════════════════╝\n");
        }
        Err(e) => {
            println!("\n❌ Failed to fetch balance: {}", e);
            error!("Balance fetch failed: {}", e);
        }
    }

    Ok(())
}

/// Show hardware information
fn cmd_hardware() -> Result<()> {
    let hw = hardware::detect_hardware()?;

    println!("\n╔═══════════════════════════════════════════════════════════╗");
    println!("║              Hardware Information                         ║");
    println!("╠═══════════════════════════════════════════════════════════╣");
    println!("║ CPU Model:  {:<52} ║", truncate(&hw.model, 52));
    println!("║ Family:     {:<52} ║", hw.family.to_string());
    println!("║ Arch:       {:<52} ║", hw.arch.to_string());
    println!("║ Cores:      {:<52} ║", hw.cores.to_string());
    println!("║ RAM:        {:<52} ║", format!("{} GB", hw.total_ram_bytes / (1024 * 1024 * 1024)));
    println!("║ Platform:   {:<52} ║", truncate(&hw.platform, 52));
    println!("║ OS:         {:<52} ║", truncate(&hw.os_version, 52));
    println!("║ Serial:     {:<52} ║", hw.serial.as_deref().unwrap_or("N/A"));
    println!("╠═══════════════════════════════════════════════════════════╣");
    println!("║ Generated Miner ID:                                      ║");
    println!("║ {:<59} ║", truncate(&hardware::generate_miner_id(&hw), 59));
    println!("╚═══════════════════════════════════════════════════════════╝\n");

    Ok(())
}

/// Run single attestation
async fn cmd_attest(config: MinerConfig) -> Result<()> {
    let manager = AttestationManager::new(config).await?;

    match manager.attest_once().await {
        Ok(result) => {
            println!("\n✅ Attestation successful!");
            println!("   Epoch: {}", result.epoch);
            println!("   Weight: {}", result.weight);
            println!("   Message: {}", result.message);
        }
        Err(e) => {
            println!("\n❌ Attestation failed: {}", e);
        }
    }

    Ok(())
}

/// List active miners
async fn cmd_miners(config: MinerConfig) -> Result<()> {
    let client = api::ApiClient::new(&config)?;

    match client.get_miners().await {
        Ok(miners) => {
            println!("\n╔═══════════════════════════════════════════════════════════╗");
            println!("║              Active Miners ({:<3})                       ║", miners.len().to_string());
            println!("╠═══════════════════════════════════════════════════════════╣");
            
            if miners.is_empty() {
                println!("║ No active miners found                                  ║");
            } else {
                for (i, miner) in miners.iter().take(10).enumerate() {
                    println!("║ {:>2}. {:<16} {:<12} x{:<6} {:<10} ║",
                        i + 1,
                        truncate(&miner.miner, 16),
                        truncate(&miner.device_family, 12),
                        format!("{:.2}", miner.antiquity_multiplier),
                        truncate(&miner.hardware_type, 10)
                    );
                }
                if miners.len() > 10 {
                    println!("║ ... and {} more miners                                  ║", miners.len() - 10);
                }
            }
            println!("╚═══════════════════════════════════════════════════════════╝\n");
        }
        Err(e) => {
            println!("\n❌ Failed to fetch miners: {}", e);
            error!("Miners fetch failed: {}", e);
        }
    }

    Ok(())
}

/// Check node health
async fn cmd_health(config: MinerConfig) -> Result<()> {
    let client = api::ApiClient::new(&config)?;

    match client.health_check().await {
        Ok(health) => {
            let status = if health.ok { "✅ Healthy" } else { "❌ Unhealthy" };
            println!("\n╔═══════════════════════════════════════════════════════════╗");
            println!("║              Node Health Status                           ║");
            println!("╠═══════════════════════════════════════════════════════════╣");
            println!("║ Status:   {:<52} ║", status);
            println!("║ Version:  {:<52} ║", health.version.as_deref().unwrap_or("N/A"));
            println!("║ Uptime:   {:<52} ║", format!("{} seconds", health.uptime_s.unwrap_or(0)));
            println!("║ DB R/W:   {:<52} ║", if health.db_rw.unwrap_or(false) { "OK" } else { "FAIL" });
            println!("║ Backup:   {:<52} ║", format!("{} hours ago", health.backup_age_hours.unwrap_or(0.0)));
            println!("╚═══════════════════════════════════════════════════════════╝\n");
        }
        Err(e) => {
            println!("\n❌ Failed to check health: {}", e);
            error!("Health check failed: {}", e);
        }
    }

    Ok(())
}

/// Truncate string to max length with ellipsis
fn truncate(s: &str, max_len: usize) -> String {
    if s.len() <= max_len {
        s.to_string()
    } else {
        format!("{}...", &s[..max_len.saturating_sub(3)])
    }
}
