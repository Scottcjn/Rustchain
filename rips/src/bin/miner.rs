//! RustChain Miner - Vintage Hardware Mining Client
//!
//! Mining client for the RustChain blockchain that:
//! - Collects hardware information
//! - Performs deep entropy verification
//! - Submits mining proofs to the network
//! - Manages reward collection

use rustchain::{
    HardwareInfo, HardwareCharacteristics, CacheSizes,
    MiningProof, WalletAddress, ProofOfAntiquity,
    deep_entropy::{DeepEntropyVerifier, Challenge, EntropyProof},
};
use std::collections::HashMap;
use std::time::{Duration, SystemTime, UNIX_EPOCH, Instant};
use std::thread;

/// Miner configuration
#[derive(Debug, Clone)]
pub struct MinerConfig {
    /// Wallet address to receive rewards
    pub wallet: WalletAddress,
    /// Node URL to connect to
    pub node_url: String,
    /// Hardware model description
    pub hardware_model: String,
    /// Hardware generation/family
    pub hardware_generation: String,
    /// Hardware age in years (auto-detected if not set)
    pub hardware_age_years: Option<u32>,
    /// Enable deep entropy verification
    pub enable_deep_entropy: bool,
    /// Mining interval in seconds
    pub mining_interval_secs: u64,
}

impl Default for MinerConfig {
    fn default() -> Self {
        MinerConfig {
            wallet: WalletAddress::new("RTC1MinerDefault0000000000000000"),
            node_url: "http://localhost:8085".to_string(),
            hardware_model: "Unknown".to_string(),
            hardware_generation: "Unknown".to_string(),
            hardware_age_years: None,
            enable_deep_entropy: true,
            mining_interval_secs: 10,
        }
    }
}

/// RustChain miner
pub struct RustChainMiner {
    /// Miner configuration
    config: MinerConfig,
    /// Deep entropy verifier
    entropy_verifier: DeepEntropyVerifier,
    /// Current challenge
    current_challenge: Option<Challenge>,
    /// Mining statistics
    stats: MiningStats,
    /// Shutdown flag
    shutdown: bool,
}

/// Mining statistics
#[derive(Debug, Clone, Default)]
pub struct MiningStats {
    /// Proofs submitted
    pub proofs_submitted: u64,
    /// Proofs accepted
    pub proofs_accepted: u64,
    /// Proofs rejected
    pub proofs_rejected: u64,
    /// Total rewards earned (in smallest unit)
    pub total_rewards: u64,
    /// Average multiplier
    pub average_multiplier: f64,
    /// Uptime in seconds
    pub uptime_secs: u64,
}

impl RustChainMiner {
    /// Create a new miner
    pub fn new(config: MinerConfig) -> Self {
        RustChainMiner {
            config,
            entropy_verifier: DeepEntropyVerifier::new(),
            current_challenge: None,
            stats: MiningStats::default(),
            shutdown: false,
        }
    }

    /// Start mining
    pub fn start(&mut self) -> Result<(), MinerError> {
        println!("⛏️  Starting RustChain Miner...");
        println!("   Wallet: {}", self.config.wallet.0);
        println!("   Node: {}", self.config.node_url);
        println!("   Hardware: {} ({})", self.config.hardware_model, self.config.hardware_generation);
        println!("   Deep Entropy: {}", if self.config.enable_deep_entropy { "Enabled" } else { "Disabled" });
        println!();

        // Detect hardware
        let hardware = self.detect_hardware()?;
        println!("📟 Detected Hardware:");
        println!("   Model: {}", hardware.model);
        println!("   Generation: {}", hardware.generation);
        println!("   Age: {} years", hardware.age_years);
        println!("   Tier: {:?}", hardware.tier);
        println!("   Multiplier: {:.2}x", hardware.multiplier);
        println!();

        // Start mining loop
        self.mining_loop(hardware)?;

        Ok(())
    }

    /// Stop mining
    pub fn stop(&mut self) {
        println!("🛑 Stopping miner...");
        self.shutdown = true;
    }

    /// Detect local hardware
    fn detect_hardware(&self) -> Result<HardwareInfo, MinerError> {
        let age_years = self.config.hardware_age_years
            .unwrap_or_else(|| self.estimate_hardware_age());

        let mut hardware = HardwareInfo::new(
            self.config.hardware_model.clone(),
            self.config.hardware_generation.clone(),
            age_years,
        );

        // Try to get detailed hardware characteristics
        if let Ok(chars) = self.collect_hardware_characteristics() {
            hardware.characteristics = Some(chars);
        }

        Ok(hardware)
    }

    /// Estimate hardware age based on generation
    fn estimate_hardware_age(&self) -> u32 {
        let current_year = 2025;
        
        // Parse year from generation string or model
        let gen = self.config.hardware_generation.to_lowercase();
        let model = self.config.hardware_model.to_lowercase();
        
        // Rough estimates based on common hardware generations
        if gen.contains("486") || model.contains("486") {
            return current_year - 1992;
        } else if gen.contains("pentium") && !gen.contains("ii") && !gen.contains("iii") {
            return current_year - 1994;
        } else if gen.contains("pentium ii") || gen.contains("p2") {
            return current_year - 1997;
        } else if gen.contains("pentium iii") || gen.contains("p3") {
            return current_year - 1999;
        } else if gen.contains("powerpc") || gen.contains("ppc") {
            if gen.contains("g4") {
                return current_year - 1999;
            } else if gen.contains("g5") {
                return current_year - 2003;
            } else {
                return current_year - 1995;
            }
        } else if gen.contains("alpha") {
            return current_year - 1998;
        } else if gen.contains("sparc") {
            return current_year - 1997;
        } else if gen.contains("mips") {
            return current_year - 1996;
        }
        
        // Default to 10 years if unknown
        10
    }

    /// Collect detailed hardware characteristics
    fn collect_hardware_characteristics(&self) -> Result<HardwareCharacteristics, MinerError> {
        // In a real implementation, this would query actual hardware
        // For now, we'll create representative characteristics
        
        let gen = self.config.hardware_generation.to_lowercase();
        
        let (cpu_family, cpu_flags, cache_sizes) = if gen.contains("486") {
            (4, vec!["fpu".to_string()], CacheSizes {
                l1_data: 8,
                l1_instruction: 8,
                l2: 0,
                l3: None,
            })
        } else if gen.contains("pentium") && !gen.contains("ii") && !gen.contains("iii") {
            (5, vec!["fpu".to_string(), "vme".to_string()], CacheSizes {
                l1_data: 16,
                l1_instruction: 16,
                l2: 256,
                l3: None,
            })
        } else if gen.contains("pentium ii") || gen.contains("p2") || gen.contains("pentium iii") || gen.contains("p3") {
            (6, vec!["fpu".to_string(), "vme".to_string(), "de".to_string()], CacheSizes {
                l1_data: 16,
                l1_instruction: 16,
                l2: 512,
                l3: None,
            })
        } else if gen.contains("g4") {
            (74, vec!["altivec".to_string(), "ppc".to_string()], CacheSizes {
                l1_data: 32,
                l1_instruction: 32,
                l2: 512,
                l3: None,
            })
        } else if gen.contains("g5") {
            (75, vec!["altivec".to_string(), "ppc".to_string()], CacheSizes {
                l1_data: 32,
                l1_instruction: 32,
                l2: 512,
                l3: None,
            })
        } else if gen.contains("alpha") {
            (21, vec!["alpha".to_string()], CacheSizes {
                l1_data: 64,
                l1_instruction: 64,
                l2: 1024,
                l3: None,
            })
        } else {
            // Generic fallback
            (6, vec!["fpu".to_string()], CacheSizes {
                l1_data: 32,
                l1_instruction: 32,
                l2: 256,
                l3: None,
            })
        };

        // Measure instruction timings
        let mut instruction_timings = HashMap::new();
        instruction_timings.insert("mul".to_string(), self.measure_instruction_time("mul"));
        instruction_timings.insert("div".to_string(), self.measure_instruction_time("div"));
        instruction_timings.insert("fadd".to_string(), self.measure_instruction_time("fadd"));

        Ok(HardwareCharacteristics {
            cpu_model: self.config.hardware_model.clone(),
            cpu_family,
            cpu_flags,
            cache_sizes,
            instruction_timings,
            unique_id: self.generate_hardware_id(),
        })
    }

    /// Measure instruction timing (simplified simulation)
    fn measure_instruction_time(&self, instruction: &str) -> u64 {
        // In real implementation, this would use RDTSC or similar
        // For now, return representative values based on instruction type
        match instruction {
            "mul" => 10 + rand::random::<u64>() % 5,
            "div" => 30 + rand::random::<u64>() % 10,
            "fadd" => 5 + rand::random::<u64>() % 3,
            _ => 10,
        }
    }

    /// Generate unique hardware ID
    fn generate_hardware_id(&self) -> String {
        use sha2::{Sha256, Digest};
        
        let mut hasher = Sha256::new();
        hasher.update(self.config.hardware_model.as_bytes());
        hasher.update(self.config.hardware_generation.as_bytes());
        hasher.update(std::process::id().to_le_bytes());
        
        let hash = hasher.finalize();
        hex::encode(&hash[..16])
    }

    /// Main mining loop
    fn mining_loop(&mut self, hardware: HardwareInfo) -> Result<(), MinerError> {
        println!("🚀 Starting mining loop...");
        println!("   Press Ctrl+C to stop");
        println!();

        let start_time = Instant::now();
        let mut last_proof = Instant::now();

        while !self.shutdown {
            // Check if it's time to submit a proof
            if last_proof.elapsed() >= Duration::from_secs(self.config.mining_interval_secs) {
                match self.submit_mining_proof(&hardware) {
                    Ok(accepted) => {
                        if accepted {
                            self.stats.proofs_accepted += 1;
                            println!("✅ Proof accepted! (Total: {})", self.stats.proofs_accepted);
                        } else {
                            self.stats.proofs_rejected += 1;
                            println!("❌ Proof rejected");
                        }
                        self.stats.proofs_submitted += 1;
                    }
                    Err(e) => {
                        self.stats.proofs_rejected += 1;
                        eprintln!("❌ Error submitting proof: {}", e);
                    }
                }
                last_proof = Instant::now();
            }

            // Update uptime
            self.stats.uptime_secs = start_time.elapsed().as_secs();

            // Small sleep
            thread::sleep(Duration::from_millis(100));
        }

        Ok(())
    }

    /// Submit a mining proof
    fn submit_mining_proof(&mut self, hardware: &HardwareInfo) -> Result<bool, MinerError> {
        // Generate anti-emulation hash
        let anti_emulation_hash = self.generate_anti_emulation_hash(hardware)?;

        // Create mining proof
        let proof = MiningProof {
            wallet: self.config.wallet.clone(),
            hardware: hardware.clone(),
            anti_emulation_hash,
            timestamp: current_timestamp(),
            nonce: rand::random::<u64>(),
        };

        // In real implementation, submit to node via RPC
        // For now, simulate acceptance based on hardware tier
        let accepted = hardware.multiplier >= 1.0;

        if accepted {
            // Calculate simulated reward
            let reward = (100_000_000.0 * hardware.multiplier / 10.0) as u64;
            self.stats.total_rewards += reward;
            self.stats.average_multiplier = hardware.multiplier;
        }

        Ok(accepted)
    }

    /// Generate anti-emulation hash
    fn generate_anti_emulation_hash(&mut self, hardware: &HardwareInfo) -> Result<[u8; 32], MinerError> {
        if !self.config.enable_deep_entropy {
            // Simple hash without deep entropy
            use sha2::{Sha256, Digest};
            let mut hasher = Sha256::new();
            hasher.update(&hardware.model);
            hasher.update(&hardware.generation);
            hasher.update(&hardware.age_years.to_le_bytes());
            return Ok(hasher.finalize().into());
        }

        // Generate and solve deep entropy challenge
        let challenge = self.entropy_verifier.generate_challenge();
        
        // Measure computation time
        let start = Instant::now();
        
        // Simulate solving the challenge (in real implementation, this runs on actual hardware)
        let mut result = 0u64;
        for op in &challenge.operations {
            match op.op.as_str() {
                "mul" => result = result.wrapping_mul(op.value as u64),
                "div" => if op.value > 0.0 { result = result.wrapping_div(op.value as u64) },
                "fadd" => result = result.wrapping_add(op.value as u64),
                "memory" => {
                    // Simulate memory access pattern test
                    let _data: Vec<u8> = vec![0; op.value as usize * 1024];
                }
                _ => {}
            }
        }
        
        let computation_time_us = start.elapsed().as_micros() as u64;

        // Collect hardware characteristics if available
        if let Some(ref chars) = hardware.characteristics {
            let entropy_proof = self.entropy_verifier.characteristics_to_proof(
                chars,
                &challenge,
                computation_time_us,
            );

            // Verify the proof
            let verification = self.entropy_verifier.verify(
                &entropy_proof,
                &hardware.generation,
            );

            if !verification.valid {
                eprintln!("⚠️  Deep entropy verification failed: {:?}", verification.issues);
            }

            // Use proof signature hash
            use sha2::{Sha256, Digest};
            let mut hasher = Sha256::new();
            hasher.update(&entropy_proof.signature_hash);
            hasher.update(&computation_time_us.to_le_bytes());
            return Ok(hasher.finalize().into());
        }

        // Fallback without characteristics
        use sha2::{Sha256, Digest};
        let mut hasher = Sha256::new();
        hasher.update(&challenge.nonce);
        hasher.update(&result.to_le_bytes());
        hasher.update(&computation_time_us.to_le_bytes());
        Ok(hasher.finalize().into())
    }

    /// Get mining statistics
    pub fn get_stats(&self) -> &MiningStats {
        &self.stats
    }

    /// Print statistics
    pub fn print_stats(&self) {
        println!("📊 Mining Statistics:");
        println!("   Proofs Submitted: {}", self.stats.proofs_submitted);
        println!("   Proofs Accepted: {}", self.stats.proofs_accepted);
        println!("   Proofs Rejected: {}", self.stats.proofs_rejected);
        println!("   Total Rewards: {:.8} RTC", self.stats.total_rewards as f64 / 100_000_000.0);
        println!("   Average Multiplier: {:.2}x", self.stats.average_multiplier);
        println!("   Uptime: {}s", self.stats.uptime_secs);
    }
}

/// Miner error types
#[derive(Debug)]
pub enum MinerError {
    HardwareDetectionError(String),
    NetworkError(String),
    ProofSubmissionError(String),
    EntropyVerificationError(String),
}

impl std::fmt::Display for MinerError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            MinerError::HardwareDetectionError(e) => write!(f, "Hardware detection error: {}", e),
            MinerError::NetworkError(e) => write!(f, "Network error: {}", e),
            MinerError::ProofSubmissionError(e) => write!(f, "Proof submission error: {}", e),
            MinerError::EntropyVerificationError(e) => write!(f, "Entropy verification error: {}", e),
        }
    }
}

impl std::error::Error for MinerError {}

/// Helper to get current Unix timestamp
fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn main() {
    println!("⛏️  RustChain Miner v0.1.0");
    println!("   Proof of Antiquity Mining");
    println!();

    // Example: PowerPC G4 miner
    let config = MinerConfig {
        wallet: WalletAddress::new("RTC1MinerG4PowerMac00000000000"),
        node_url: "http://localhost:8085".to_string(),
        hardware_model: "PowerPC G4 1.25GHz".to_string(),
        hardware_generation: "G4".to_string(),
        hardware_age_years: Some(22),
        enable_deep_entropy: true,
        mining_interval_secs: 10,
    };

    let mut miner = RustChainMiner::new(config);

    // Handle Ctrl+C
    let ctrlc_result = ctrlc::set_handler(move || {
        println!("\n⚠️  Received shutdown signal");
    });

    if let Err(e) = ctrlc_result {
        eprintln!("Error setting Ctrl+C handler: {}", e);
    }

    match miner.start() {
        Ok(_) => {
            miner.print_stats();
            println!("Miner shutdown gracefully");
        }
        Err(e) => eprintln!("Miner error: {}", e),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_miner_creation() {
        let config = MinerConfig::default();
        let miner = RustChainMiner::new(config);
        
        assert!(!miner.shutdown);
        assert_eq!(miner.stats.proofs_submitted, 0);
    }

    #[test]
    fn test_hardware_age_estimation() {
        let config = MinerConfig {
            hardware_model: "486 DX2-66".to_string(),
            hardware_generation: "486".to_string(),
            ..MinerConfig::default()
        };
        
        let miner = RustChainMiner::new(config);
        let age = miner.estimate_hardware_age();
        
        assert!(age >= 30); // 486 from 1992, should be 30+ years old in 2025
    }

    #[test]
    fn test_mining_stats() {
        let config = MinerConfig::default();
        let mut miner = RustChainMiner::new(config);
        
        miner.stats.proofs_submitted = 10;
        miner.stats.proofs_accepted = 8;
        miner.stats.proofs_rejected = 2;
        
        assert_eq!(miner.stats.proofs_submitted, 10);
        assert_eq!(miner.stats.proofs_accepted, 8);
    }
}
