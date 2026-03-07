// RustChain Miner CLI
// ===================
// Native Rust miner for Proof-of-Antiquity consensus
// Integrates with RustChain node API endpoints

use std::sync::Arc;
use std::time::Duration;
use clap::Parser;
use tokio::time::sleep;
use tracing::{info, warn, error, Level};
use tracing_subscriber::FmtSubscriber;

use rustchain::{HardwareInfo, HardwareTier};
use rustchain::miner_client::{MinerClient, DEFAULT_NODE_URL, EPOCH_DURATION_SECS};

/// RustChain Miner - Native Rust miner for Proof-of-Antiquity
#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Wallet address/name for receiving rewards
    #[arg(short, long)]
    wallet: Option<String>,

    /// Node URL (default: https://rustchain.org)
    #[arg(short, long, default_value = DEFAULT_NODE_URL)]
    node: String,

    /// Hardware model description
    #[arg(short, long, default_value = "Auto-detect")]
    hardware: String,

    /// Hardware generation/family
    #[arg(short, long, default_value = "Auto-detect")]
    generation: String,

    /// Hardware age in years (overrides auto-detection)
    #[arg(short, long)]
    age: Option<u32>,

    /// Mining interval in seconds (default: epoch duration)
    #[arg(short, long, default_value_t = EPOCH_DURATION_SECS)]
    interval: u64,

    /// Enable verbose logging
    #[arg(short, long)]
    verbose: bool,

    /// Dry run - validate config without submitting
    #[arg(long)]
    dry_run: bool,

    /// Create a new wallet
    #[arg(long)]
    create_wallet: bool,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    // Initialize logging
    let log_level = if args.verbose { Level::DEBUG } else { Level::INFO };
    let subscriber = FmtSubscriber::builder()
        .with_max_level(log_level)
        .with_target(false)
        .finish();
    tracing::subscriber::set_global_default(subscriber)?;

    println!("╔═══════════════════════════════════════════════════════════╗");
    println!("║         RustChain Miner - Proof of Antiquity              ║");
    println!("║         Native Rust Miner v0.2.0                          ║");
    println!("╚═══════════════════════════════════════════════════════════╝");
    println!();

    // Handle wallet creation
    if args.create_wallet {
        let wallet = generate_wallet_name();
        println!("✓ Generated new wallet: {}", wallet);
        println!("  Save this name - it's your miner identity!");
        return Ok(());
    }

    // Get or generate wallet
    let wallet = args.wallet.unwrap_or_else(|| {
        let name = generate_wallet_name();
        info!("No wallet specified, using generated: {}", name);
        name
    });

    // Detect hardware info
    let hardware = detect_hardware(&args)?;
    println!("Hardware: {} ({})", hardware.model, hardware.generation);
    println!("Age: {} years | Tier: {:?} | Multiplier: {:.1}×", 
             hardware.age_years, hardware.tier, hardware.multiplier);
    println!();

    if args.dry_run {
        println!("🔍 DRY RUN MODE - No submissions will be made");
        println!("Configuration validated successfully.");
        return Ok(());
    }

    // Create miner client
    info!("Initializing miner client...");
    let mut client = match MinerClient::with_default_node(&wallet, hardware.clone()) {
        Ok(c) => c,
        Err(e) => {
            error!("Failed to initialize miner client: {}", e);
            return Err(Box::new(e));
        }
    };

    println!("Node: {}", args.node);
    println!("Wallet: {}", wallet);
    println!();

    // Check node health
    info!("Checking node health...");
    match client.check_health().await {
        Ok(health) => {
            println!("✓ Node healthy (v{}, uptime: {}s)", health.version, health.uptime_s);
        }
        Err(e) => {
            warn!("Node health check failed: {}", e);
            println!("⚠ Node may be offline, continuing anyway...");
        }
    }

    // Enroll miner
    info!("Enrolling miner...");
    match client.enroll().await {
        Ok(enrollment) => {
            println!("✓ Miner enrolled");
            println!("  Epoch: {} | Slot: {} | Multiplier: {:.2}×", 
                     enrollment.epoch, enrollment.slot, enrollment.multiplier);
        }
        Err(e) => {
            error!("Enrollment failed: {}", e);
            return Err(Box::new(e));
        }
    }

    println!();
    println!("🚀 Starting mining loop (interval: {}s)...", args.interval);
    println!("Press Ctrl+C to stop");
    println!();

    // Mining loop
    let mut iteration = 0u64;
    loop {
        iteration += 1;
        
        info!("Mining iteration {}", iteration);
        
        // Get epoch info
        match client.get_epoch_info().await {
            Ok(epoch) => {
                println!("Epoch {} | Slot {}/{} | Miners: {} | Pot: {:.2} RTC",
                         epoch.epoch, epoch.slot, epoch.blocks_per_epoch,
                         epoch.enrolled_miners, epoch.epoch_pot);
            }
            Err(e) => {
                warn!("Failed to get epoch info: {}", e);
            }
        }

        // Submit mining proof
        match client.submit_proof().await {
            Ok(result) => {
                if result.ok && result.accepted {
                    println!("✓ Proof accepted | Reward: {:.4} RTC", result.reward_rtc);
                } else {
                    warn!("Proof rejected: {:?}", result.message);
                }
            }
            Err(e) => {
                error!("Proof submission failed: {}", e);
            }
        }

        // Check balance periodically
        if iteration % 10 == 0 {
            match client.get_balance().await {
                Ok(balance) => {
                    println!("💰 Balance: {:.4} RTC", balance);
                }
                Err(e) => {
                    warn!("Balance check failed: {}", e);
                }
            }
        }

        // Refresh attestation if needed
        if !client.is_attestation_valid() {
            info!("Refreshing fingerprint attestation...");
            if let Err(e) = client.refresh_attestation().await {
                warn!("Attestation refresh failed: {}", e);
            }
        }

        // Wait for next iteration
        sleep(Duration::from_secs(args.interval)).await;
    }
}

/// Detect hardware information
fn detect_hardware(args: &Args) -> Result<HardwareInfo, Box<dyn std::error::Error>> {
    use sysinfo::System;

    let mut sys = System::new_all();
    sys.refresh_all();

    // Get CPU info
    let cpu = sys.cpus().first();
    let model = if args.hardware == "Auto-detect" {
        cpu.map(|c| c.brand().to_string())
            .unwrap_or_else(|| "Unknown CPU".to_string())
    } else {
        args.hardware.clone()
    };

    let generation = if args.generation == "Auto-detect" {
        detect_cpu_generation(&model)
    } else {
        args.generation.clone()
    };

    let age = args.age.unwrap_or_else(|| estimate_hardware_age(&model, &generation));
    let tier = HardwareTier::from_age(age);
    let multiplier = tier.multiplier();

    Ok(HardwareInfo::new(model, generation, age))
}

/// Detect CPU generation from model string
fn detect_cpu_generation(model: &str) -> String {
    let model_lower = model.to_lowercase();
    
    // PowerPC detection
    if model_lower.contains("powerpc") || model_lower.contains("ppc") {
        if model_lower.contains("g4") || model_lower.contains("74") {
            return "G4".to_string();
        } else if model_lower.contains("g5") || model_lower.contains("970") {
            return "G5".to_string();
        } else if model_lower.contains("g3") || model_lower.contains("750") {
            return "G3".to_string();
        }
        return "PowerPC".to_string();
    }
    
    // Intel detection
    if model_lower.contains("intel") {
        if model_lower.contains("486") {
            return "486".to_string();
        } else if model_lower.contains("pentium") {
            if model_lower.contains("pro") || model_lower.contains("ii") || model_lower.contains("iii") {
                return "P6".to_string();
            }
            return "Pentium".to_string();
        } else if model_lower.contains("core") {
            if model_lower.contains("2") {
                return "Core 2".to_string();
            } else if model_lower.contains("i7") {
                return "Core i7".to_string();
            } else if model_lower.contains("i5") {
                return "Core i5".to_string();
            } else if model_lower.contains("i3") {
                return "Core i3".to_string();
            }
            return "Core".to_string();
        } else if model_lower.contains("xeon") {
            return "Xeon".to_string();
        }
    }
    
    // AMD detection
    if model_lower.contains("amd") {
        if model_lower.contains("ryzen") {
            return "Ryzen".to_string();
        } else if model_lower.contains("athlon") {
            return "Athlon".to_string();
        } else if model_lower.contains("opteron") {
            return "Opteron".to_string();
        }
    }
    
    // Apple Silicon
    if model_lower.contains("apple") {
        if model_lower.contains("m3") {
            return "M3".to_string();
        } else if model_lower.contains("m2") {
            return "M2".to_string();
        } else if model_lower.contains("m1") {
            return "M1".to_string();
        }
        return "Apple Silicon".to_string();
    }
    
    // ARM
    if model_lower.contains("arm") {
        return "ARM".to_string();
    }
    
    "Unknown".to_string()
}

/// Estimate hardware age based on model/generation
fn estimate_hardware_age(model: &str, generation: &str) -> u32 {
    let current_year = 2025; // As per RIP-002
    
    // Release year estimates by generation
    let release_year = match generation {
        "486" => 1992,
        "Pentium" => 1995,
        "P6" => 1997,
        "Core 2" => 2006,
        "Core i7" => 2008,
        "Core i5" => 2009,
        "Core i3" => 2010,
        "Ryzen" => 2017,
        "G3" => 1997,
        "G4" => 1999,
        "G5" => 2003,
        "PowerPC" => 1995,
        "M1" => 2020,
        "M2" => 2022,
        "M3" => 2023,
        "Apple Silicon" => 2020,
        "ARM" => 2015,
        _ => {
            // Try to estimate from model string
            if model.contains("8645") || model.contains("7000") {
                2023 // Recent Ryzen
            } else if model.contains("13") || model.contains("14") {
                2022 // Recent Intel
            } else {
                2020 // Default to modern
            }
        }
    };
    
    current_year.saturating_sub(release_year)
}

/// Generate a random wallet name
fn generate_wallet_name() -> String {
    use rand::Rng;
    
    let adjectives = ["rusty", "vintage", "ancient", "sacred", "classic", 
                      "retro", "noble", "brave", "swift", "wise"];
    let nouns = ["miner", "keeper", "guardian", "preserver", "pioneer",
                 "explorer", "builder", "coder", "runner", "node"];
    
    let mut rng = rand::thread_rng();
    let adj = adjectives[rng.gen_range(0..adjectives.len())];
    let noun = nouns[rng.gen_range(0..nouns.len())];
    let num = rng.gen_range(100..999);
    
    format!("{}-{}-{}", adj, noun, num)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hardware_detection() {
        let args = Args {
            wallet: Some("test-wallet".to_string()),
            node: DEFAULT_NODE_URL.to_string(),
            hardware: "Test CPU".to_string(),
            generation: "Test".to_string(),
            age: Some(20),
            interval: 600,
            verbose: false,
            dry_run: true,
            create_wallet: false,
        };
        
        let hw = detect_hardware(&args).unwrap();
        assert_eq!(hw.model, "Test CPU");
        assert_eq!(hw.generation, "Test");
        assert_eq!(hw.age_years, 20);
        assert_eq!(hw.tier, HardwareTier::Vintage);
    }

    #[test]
    fn test_generation_detection() {
        assert_eq!(detect_cpu_generation("PowerPC G4"), "G4");
        assert_eq!(detect_cpu_generation("Intel Core i7"), "Core i7");
        assert_eq!(detect_cpu_generation("AMD Ryzen 9"), "Ryzen");
        assert_eq!(detect_cpu_generation("Apple M1"), "M1");
    }

    #[test]
    fn test_age_estimation() {
        assert_eq!(estimate_hardware_age("G4", "G4"), 2025 - 1999);
        assert_eq!(estimate_hardware_age("486", "486"), 2025 - 1992);
        assert_eq!(estimate_hardware_age("M1", "M1"), 2025 - 2020);
    }

    #[test]
    fn test_wallet_generation() {
        let wallet = generate_wallet_name();
        assert!(wallet.contains('-'));
        assert!(wallet.len() > 10);
    }
}
