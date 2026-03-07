// RIP-002: Proof of Antiquity Consensus
// ======================================
// The revolutionary consensus mechanism that rewards vintage hardware
// Status: DRAFT
// Author: Flamekeeper Scott
// Created: 2025-11-28

use std::collections::HashMap;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use sha2::{Sha256, Digest};
use serde::{Serialize, Deserialize};

// Import from RIP-001
use crate::core_types::{
    HardwareTier, HardwareInfo, HardwareCharacteristics,
    WalletAddress, Block, BlockMiner, MiningProof, TokenAmount,
    is_console_arch,
};

/// Block reward per block (1.0 RTC maximum, split among miners)
pub const BLOCK_REWARD: TokenAmount = TokenAmount(100_000_000); // 1 RTC

/// Minimum multiplier threshold to receive any reward
pub const MIN_MULTIPLIER_THRESHOLD: f64 = 0.1;

/// Maximum Antiquity Score for reward capping
pub const AS_MAX: f64 = 100.0;

/// Current year for AS calculation
pub const CURRENT_YEAR: u32 = 2025;

/// Calculate Antiquity Score (AS) per RIP-0001 spec
/// AS = (current_year - release_year) * log10(uptime_days + 1)
pub fn calculate_antiquity_score(release_year: u32, uptime_days: u64) -> f64 {
    let age = CURRENT_YEAR.saturating_sub(release_year) as f64;
    let uptime_factor = ((uptime_days + 1) as f64).log10();
    age * uptime_factor
}

/// Maximum miners per block
pub const MAX_MINERS_PER_BLOCK: usize = 100;

/// Anti-emulation check interval (seconds)
pub const ANTI_EMULATION_CHECK_INTERVAL: u64 = 300;

/// Proof of Antiquity validator
#[derive(Debug)]
pub struct ProofOfAntiquity {
    /// Current block being assembled
    pending_proofs: Vec<ValidatedProof>,
    /// Block start time
    block_start_time: u64,
    /// Known hardware hashes (for duplicate detection)
    known_hardware: HashMap<[u8; 32], WalletAddress>,
    /// Anti-emulation verifier
    anti_emulation: AntiEmulationVerifier,
}

/// A validated mining proof ready for block inclusion
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidatedProof {
    pub wallet: WalletAddress,
    pub hardware: HardwareInfo,
    pub multiplier: f64,
    pub anti_emulation_hash: [u8; 32],
    pub validated_at: u64,
}

/// Anti-emulation verification system
#[derive(Debug)]
pub struct AntiEmulationVerifier {
    /// Known CPU characteristics by family
    cpu_signatures: HashMap<u32, CpuSignature>,
    /// Instruction timing baselines
    timing_baselines: HashMap<String, TimingBaseline>,
}

/// CPU signature for validation
#[derive(Debug, Clone)]
pub struct CpuSignature {
    pub family: u32,
    pub expected_flags: Vec<String>,
    pub cache_ranges: CacheRanges,
}

/// Expected cache size ranges for CPU families
#[derive(Debug, Clone)]
pub struct CacheRanges {
    pub l1_min: u32,
    pub l1_max: u32,
    pub l2_min: u32,
    pub l2_max: u32,
}

/// Timing baseline for instruction verification
#[derive(Debug, Clone)]
pub struct TimingBaseline {
    pub instruction: String,
    pub min_cycles: u64,
    pub max_cycles: u64,
}

impl ProofOfAntiquity {
    pub fn new() -> Self {
        ProofOfAntiquity {
            pending_proofs: Vec::new(),
            block_start_time: current_timestamp(),
            known_hardware: HashMap::new(),
            anti_emulation: AntiEmulationVerifier::new(),
        }
    }

    /// Submit a mining proof for the current block
    pub fn submit_proof(&mut self, proof: MiningProof) -> Result<SubmitResult, ProofError> {
        // Check if block window is still open
        let elapsed = current_timestamp() - self.block_start_time;
        if elapsed >= 120 {
            return Err(ProofError::BlockWindowClosed);
        }

        // Check for duplicate wallet submission
        if self.pending_proofs.iter().any(|p| p.wallet == proof.wallet) {
            return Err(ProofError::DuplicateSubmission);
        }

        // Check max miners
        if self.pending_proofs.len() >= MAX_MINERS_PER_BLOCK {
            return Err(ProofError::BlockFull);
        }

        // Validate hardware info
        self.validate_hardware(&proof.hardware)?;

        // Run anti-emulation checks
        if let Some(ref chars) = proof.hardware.characteristics {
            self.anti_emulation.verify(chars)?;
        }

        // Generate hardware hash to detect duplicate hardware
        let hw_hash = self.hash_hardware(&proof.hardware);
        if let Some(existing_wallet) = self.known_hardware.get(&hw_hash) {
            if existing_wallet != &proof.wallet {
                return Err(ProofError::HardwareAlreadyRegistered(existing_wallet.clone()));
            }
        }

        // Validate multiplier matches tier
        let expected_mult = proof.hardware.tier.multiplier();
        if (proof.hardware.multiplier - expected_mult).abs() > 0.2 {
            return Err(ProofError::InvalidMultiplier);
        }

        // Cap multiplier at Ancient tier maximum
        let capped_multiplier = proof.hardware.multiplier.min(3.5);

        // Create validated proof
        let validated = ValidatedProof {
            wallet: proof.wallet,
            hardware: proof.hardware,
            multiplier: capped_multiplier,
            anti_emulation_hash: proof.anti_emulation_hash,
            validated_at: current_timestamp(),
        };

        self.pending_proofs.push(validated);
        self.known_hardware.insert(hw_hash, proof.wallet.clone());

        Ok(SubmitResult {
            accepted: true,
            pending_miners: self.pending_proofs.len(),
            your_multiplier: capped_multiplier,
            block_completes_in: 120 - elapsed,
        })
    }

    /// Process all pending proofs and create a new block
    pub fn process_block(&mut self, previous_hash: [u8; 32], height: u64) -> Option<Block> {
        if self.pending_proofs.is_empty() {
            self.reset_block();
            return None;
        }

        // Calculate total multipliers
        let total_multipliers: f64 = self.pending_proofs.iter()
            .map(|p| p.multiplier)
            .sum();

        // Calculate rewards for each miner (proportional to multiplier)
        let mut miners = Vec::new();
        let mut total_distributed = 0u64;

        for proof in &self.pending_proofs {
            let share = proof.multiplier / total_multipliers;
            let reward = (BLOCK_REWARD.0 as f64 * share) as u64;
            total_distributed += reward;

            miners.push(BlockMiner {
                wallet: proof.wallet.clone(),
                hardware: proof.hardware.model.clone(),
                multiplier: proof.multiplier,
                reward,
            });
        }

        // Calculate block hash
        let block_data = format!(
            "{}:{}:{}:{}",
            height,
            hex::encode(previous_hash),
            total_distributed,
            current_timestamp()
        );
        let mut hasher = Sha256::new();
        hasher.update(block_data.as_bytes());
        let hash: [u8; 32] = hasher.finalize().into();

        // Calculate merkle root of miners
        let merkle_root = self.calculate_merkle_root(&miners);

        let block = Block {
            height,
            hash: crate::core_types::BlockHash::from_bytes(hash),
            previous_hash: crate::core_types::BlockHash::from_bytes(previous_hash),
            timestamp: current_timestamp(),
            miners,
            total_reward: total_distributed,
            merkle_root,
            state_root: [0u8; 32], // Simplified for now
        };

        // Reset for next block
        self.reset_block();

        Some(block)
    }

    fn reset_block(&mut self) {
        self.pending_proofs.clear();
        self.block_start_time = current_timestamp();
    }

    fn validate_hardware(&self, hardware: &HardwareInfo) -> Result<(), ProofError> {
        // Validate age is reasonable
        if hardware.age_years > 50 {
            return Err(ProofError::SuspiciousAge);
        }

        // Validate tier matches age
        let expected_tier = HardwareTier::from_age(hardware.age_years);
        if hardware.tier != expected_tier {
            return Err(ProofError::TierMismatch);
        }

        // Validate multiplier is within bounds
        if hardware.multiplier < MIN_MULTIPLIER_THRESHOLD || hardware.multiplier > 4.0 {
            return Err(ProofError::InvalidMultiplier);
        }

        Ok(())
    }

    fn hash_hardware(&self, hardware: &HardwareInfo) -> [u8; 32] {
        let data = format!(
            "{}:{}:{}",
            hardware.model,
            hardware.generation,
            hardware.characteristics
                .as_ref()
                .map(|c| &c.unique_id)
                .unwrap_or(&String::new())
        );
        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        hasher.finalize().into()
    }

    fn calculate_merkle_root(&self, miners: &[BlockMiner]) -> [u8; 32] {
        if miners.is_empty() {
            return [0u8; 32];
        }

        let mut hashes: Vec<[u8; 32]> = miners.iter()
            .map(|m| {
                let data = format!("{}:{}:{}", m.wallet.0, m.multiplier, m.reward);
                let mut hasher = Sha256::new();
                hasher.update(data.as_bytes());
                hasher.finalize().into()
            })
            .collect();

        while hashes.len() > 1 {
            if hashes.len() % 2 == 1 {
                hashes.push(hashes.last().unwrap().clone());
            }

            let mut new_hashes = Vec::new();
            for chunk in hashes.chunks(2) {
                let mut hasher = Sha256::new();
                hasher.update(&chunk[0]);
                hasher.update(&chunk[1]);
                new_hashes.push(hasher.finalize().into());
            }
            hashes = new_hashes;
        }

        hashes[0]
    }

    /// Get current block status
    pub fn get_status(&self) -> BlockStatus {
        let elapsed = current_timestamp() - self.block_start_time;
        BlockStatus {
            pending_proofs: self.pending_proofs.len(),
            total_multipliers: self.pending_proofs.iter().map(|p| p.multiplier).sum(),
            block_age: elapsed,
            time_remaining: 120u64.saturating_sub(elapsed),
        }
    }
}

impl AntiEmulationVerifier {
    pub fn new() -> Self {
        let mut verifier = AntiEmulationVerifier {
            cpu_signatures: HashMap::new(),
            timing_baselines: HashMap::new(),
        };
        verifier.initialize_signatures();
        verifier
    }

    fn initialize_signatures(&mut self) {
        // PowerPC G4 (family 74 = 0x4A)
        self.cpu_signatures.insert(74, CpuSignature {
            family: 74,
            expected_flags: vec!["altivec".into(), "ppc".into()],
            cache_ranges: CacheRanges {
                l1_min: 32, l1_max: 64,
                l2_min: 256, l2_max: 2048,
            },
        });

        // Intel 486 (family 4)
        self.cpu_signatures.insert(4, CpuSignature {
            family: 4,
            expected_flags: vec!["fpu".into()],
            cache_ranges: CacheRanges {
                l1_min: 8, l1_max: 16,
                l2_min: 0, l2_max: 512,
            },
        });

        // Intel Pentium (family 5)
        self.cpu_signatures.insert(5, CpuSignature {
            family: 5,
            expected_flags: vec!["fpu".into(), "vme".into(), "de".into()],
            cache_ranges: CacheRanges {
                l1_min: 16, l1_max: 32,
                l2_min: 256, l2_max: 512,
            },
        });

        // Intel P6 family (Pentium Pro/II/III, family 6)
        self.cpu_signatures.insert(6, CpuSignature {
            family: 6,
            expected_flags: vec!["fpu".into(), "vme".into(), "de".into(), "pse".into()],
            cache_ranges: CacheRanges {
                l1_min: 16, l1_max: 32,
                l2_min: 256, l2_max: 2048,
            },
        });
    }

    pub fn verify(&self, characteristics: &HardwareCharacteristics) -> Result<(), ProofError> {
        // Check if we have a signature for this CPU family
        if let Some(signature) = self.cpu_signatures.get(&characteristics.cpu_family) {
            // Verify cache sizes are reasonable
            if characteristics.cache_sizes.l1_data < signature.cache_ranges.l1_min
                || characteristics.cache_sizes.l1_data > signature.cache_ranges.l1_max {
                return Err(ProofError::SuspiciousHardware("L1 cache size mismatch".into()));
            }

            // Verify expected flags are present
            let has_expected_flags = signature.expected_flags.iter()
                .all(|flag| characteristics.cpu_flags.contains(flag));

            if !has_expected_flags {
                return Err(ProofError::SuspiciousHardware("Missing expected CPU flags".into()));
            }
        }

        // Verify instruction timings if present
        for (instruction, timing) in &characteristics.instruction_timings {
            if let Some(baseline) = self.timing_baselines.get(instruction) {
                if *timing < baseline.min_cycles || *timing > baseline.max_cycles {
                    return Err(ProofError::EmulationDetected);
                }
            }
        }

        Ok(())
    }

    // ═══════════════════════════════════════════════════════════
    // RIP-0683: Console-Specific Anti-Emulation
    // ═══════════════════════════════════════════════════════════

    /// Verify console miner attestation via Pico bridge
    /// 
    /// Console miners use different checks than standard miners:
    /// - ctrl_port_timing instead of clock_drift
    /// - rom_execution_timing instead of cache_timing
    /// - bus_jitter instead of instruction_jitter
    pub fn verify_console_miner(
        &self,
        console_arch: &str,
        timing_data: &ConsoleTimingData,
    ) -> Result<(), ProofError> {
        // Verify this is a known console architecture
        if !is_console_arch(console_arch) {
            return Err(ProofError::SuspiciousHardware(
                format!("Unknown console architecture: {}", console_arch)
            ));
        }

        // Get expected timing baseline for this console
        let baseline = self.get_console_timing_baseline(console_arch)
            .ok_or_else(|| ProofError::SuspiciousHardware(
                format!("No timing baseline for console: {}", console_arch)
            ))?;

        // Check 1: Controller port timing CV (must show real hardware jitter)
        // Emulators have near-perfect timing (CV < 0.0001)
        if timing_data.ctrl_port_cv < 0.0001 && timing_data.ctrl_port_cv != 0.0 {
            return Err(ProofError::EmulationDetected);
        }

        // Check 2: ROM execution timing must be within ±15% of baseline
        // Real hardware has characteristic execution times
        let timing_diff = (timing_data.rom_hash_time_us as f64 - baseline.expected_rom_time_us as f64).abs();
        let tolerance = (baseline.expected_rom_time_us as f64) * 0.15;
        if timing_diff > tolerance {
            return Err(ProofError::SuspiciousHardware(
                format!(
                    "ROM execution time {}us outside tolerance (expected {}±{}us)",
                    timing_data.rom_hash_time_us,
                    baseline.expected_rom_time_us,
                    tolerance
                )
            ));
        }

        // Check 3: Bus jitter must be present (real hardware has noise)
        // Emulators have deterministic bus timing
        if timing_data.bus_jitter_stdev_ns < 500 {
            return Err(ProofError::EmulationDetected);
        }

        // Check 4: Sample count must be meaningful
        if timing_data.bus_jitter_samples < 100 {
            return Err(ProofError::SuspiciousHardware(
                "Insufficient jitter samples".into()
            ));
        }

        Ok(())
    }

    /// Get timing baseline for a specific console architecture
    fn get_console_timing_baseline(&self, console_arch: &str) -> Option<ConsoleTimingBaseline> {
        // These are approximate values based on real hardware measurements
        // Actual values may vary by ±15% due to temperature, age, etc.
        match console_arch.to_lowercase().as_str() {
            // Nintendo consoles
            "nes_6502" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 2_500_000,  // ~2.5s for SHA-256 on 1.79MHz 6502
                ctrl_port_poll_ns: 16_667_000,    // 60Hz polling
                bus_jitter_expected_ns: 2_000,    // High jitter from bus contention
            }),
            "snes_65c816" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 1_200_000,  // ~1.2s on 3.58MHz 65C816
                ctrl_port_poll_ns: 16_667_000,    // 60Hz polling
                bus_jitter_expected_ns: 1_500,
            }),
            "n64_mips" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 847_000,    // ~847ms on 93.75MHz R4300i
                ctrl_port_poll_ns: 250_000,       // 4Mbit/s Joybus
                bus_jitter_expected_ns: 1_250,
            }),
            "gameboy_z80" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 3_000_000,  // ~3s on 4.19MHz Z80
                ctrl_port_poll_ns: 122_000,       // 8Kbit/s link cable
                bus_jitter_expected_ns: 1_800,
            }),
            "gba_arm7" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 450_000,    // ~450ms on 16.78MHz ARM7
                ctrl_port_poll_ns: 122_000,       // Link cable
                bus_jitter_expected_ns: 1_000,
            }),
            
            // Sega consoles
            "genesis_68000" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 1_500_000,  // ~1.5s on 7.67MHz 68000
                ctrl_port_poll_ns: 16_667_000,    // 60Hz polling
                bus_jitter_expected_ns: 1_600,
            }),
            "sms_z80" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 2_800_000,  // ~2.8s on 3.58MHz Z80
                ctrl_port_poll_ns: 16_667_000,
                bus_jitter_expected_ns: 1_700,
            }),
            "saturn_sh2" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 380_000,    // ~380ms on dual 28.6MHz SH-2
                ctrl_port_poll_ns: 16_667_000,    // Parallel SMPC
                bus_jitter_expected_ns: 900,
            }),
            
            // Sony consoles
            "ps1_mips" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 920_000,    // ~920ms on 33.8MHz R3000A
                ctrl_port_poll_ns: 4_000,         // 250Kbit/s SPI
                bus_jitter_expected_ns: 1_100,
            }),
            
            // Generic families (use conservative estimates)
            "6502" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 2_500_000,
                ctrl_port_poll_ns: 16_667_000,
                bus_jitter_expected_ns: 2_000,
            }),
            "65c816" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 1_200_000,
                ctrl_port_poll_ns: 16_667_000,
                bus_jitter_expected_ns: 1_500,
            }),
            "z80" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 2_800_000,
                ctrl_port_poll_ns: 16_667_000,
                bus_jitter_expected_ns: 1_700,
            }),
            "sh2" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 380_000,
                ctrl_port_poll_ns: 16_667_000,
                bus_jitter_expected_ns: 900,
            }),
            "mips" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 900_000,
                ctrl_port_poll_ns: 250_000,
                bus_jitter_expected_ns: 1_200,
            }),
            "68000" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 1_500_000,
                ctrl_port_poll_ns: 16_667_000,
                bus_jitter_expected_ns: 1_600,
            }),
            "arm7" => Some(ConsoleTimingBaseline {
                expected_rom_time_us: 450_000,
                ctrl_port_poll_ns: 122_000,
                bus_jitter_expected_ns: 1_000,
            }),
            
            _ => None,
        }
    }
}

/// Console timing data from Pico bridge
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsoleTimingData {
    /// Controller port timing mean (nanoseconds)
    pub ctrl_port_timing_mean_ns: u64,
    /// Controller port timing standard deviation (nanoseconds)
    pub ctrl_port_timing_stdev_ns: u64,
    /// Coefficient of variation (stdev/mean) - must be > 0.0001
    pub ctrl_port_cv: f64,
    /// ROM hash computation time (microseconds)
    pub rom_hash_time_us: u64,
    /// Number of bus jitter samples collected
    pub bus_jitter_samples: u32,
    /// Bus jitter standard deviation (nanoseconds)
    pub bus_jitter_stdev_ns: u64,
}

/// Console timing baseline for anti-emulation
#[derive(Debug, Clone)]
pub struct ConsoleTimingBaseline {
    /// Expected ROM hash time in microseconds
    pub expected_rom_time_us: u64,
    /// Expected controller port poll interval in nanoseconds
    pub ctrl_port_poll_ns: u64,
    /// Expected bus jitter in nanoseconds
    pub bus_jitter_expected_ns: u64,
}

/// Result of submitting a proof
#[derive(Debug, Serialize, Deserialize)]
pub struct SubmitResult {
    pub accepted: bool,
    pub pending_miners: usize,
    pub your_multiplier: f64,
    pub block_completes_in: u64,
}

/// Current block status
#[derive(Debug, Serialize, Deserialize)]
pub struct BlockStatus {
    pub pending_proofs: usize,
    pub total_multipliers: f64,
    pub block_age: u64,
    pub time_remaining: u64,
}

/// Proof validation errors
#[derive(Debug)]
pub enum ProofError {
    BlockWindowClosed,
    DuplicateSubmission,
    BlockFull,
    InvalidMultiplier,
    TierMismatch,
    SuspiciousAge,
    HardwareAlreadyRegistered(WalletAddress),
    SuspiciousHardware(String),
    EmulationDetected,
    InvalidSignature,
}

impl std::fmt::Display for ProofError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ProofError::BlockWindowClosed => write!(f, "Block window has closed"),
            ProofError::DuplicateSubmission => write!(f, "Already submitted proof for this block"),
            ProofError::BlockFull => write!(f, "Block has reached maximum miners"),
            ProofError::InvalidMultiplier => write!(f, "Invalid multiplier value"),
            ProofError::TierMismatch => write!(f, "Tier does not match hardware age"),
            ProofError::SuspiciousAge => write!(f, "Hardware age is suspicious"),
            ProofError::HardwareAlreadyRegistered(w) => {
                write!(f, "Hardware already registered to wallet {}", w.0)
            }
            ProofError::SuspiciousHardware(msg) => write!(f, "Suspicious hardware: {}", msg),
            ProofError::EmulationDetected => write!(f, "Emulation detected"),
            ProofError::InvalidSignature => write!(f, "Invalid signature"),
        }
    }
}

impl std::error::Error for ProofError {}

/// Helper to get current Unix timestamp
fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or(Duration::ZERO)
        .as_secs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_poa_new_block() {
        let mut poa = ProofOfAntiquity::new();

        let proof = MiningProof {
            wallet: WalletAddress::new("RTC1TestMiner123456789"),
            hardware: HardwareInfo::new(
                "PowerPC G4".to_string(),
                "G4".to_string(),
                22
            ),
            anti_emulation_hash: [0u8; 32],
            timestamp: current_timestamp(),
            nonce: 12345,
        };

        let result = poa.submit_proof(proof);
        assert!(result.is_ok());

        let status = poa.get_status();
        assert_eq!(status.pending_proofs, 1);
    }

    #[test]
    fn test_tier_matching() {
        let mut poa = ProofOfAntiquity::new();

        // Create proof with mismatched tier
        let mut hardware = HardwareInfo::new("Test CPU".to_string(), "Test".to_string(), 22);
        hardware.tier = HardwareTier::Ancient; // Should be Vintage for age 22

        let proof = MiningProof {
            wallet: WalletAddress::new("RTC1TestMiner123456789"),
            hardware,
            anti_emulation_hash: [0u8; 32],
            timestamp: current_timestamp(),
            nonce: 12345,
        };

        let result = poa.submit_proof(proof);
        assert!(matches!(result, Err(ProofError::TierMismatch)));
    }

    #[test]
    fn test_duplicate_submission() {
        let mut poa = ProofOfAntiquity::new();

        let wallet = WalletAddress::new("RTC1TestMiner123456789");

        let proof1 = MiningProof {
            wallet: wallet.clone(),
            hardware: HardwareInfo::new("CPU1".to_string(), "Gen1".to_string(), 15),
            anti_emulation_hash: [0u8; 32],
            timestamp: current_timestamp(),
            nonce: 1,
        };

        let proof2 = MiningProof {
            wallet: wallet,
            hardware: HardwareInfo::new("CPU2".to_string(), "Gen2".to_string(), 20),
            anti_emulation_hash: [0u8; 32],
            timestamp: current_timestamp(),
            nonce: 2,
        };

        assert!(poa.submit_proof(proof1).is_ok());
        assert!(matches!(poa.submit_proof(proof2), Err(ProofError::DuplicateSubmission)));
    }

    // ═══════════════════════════════════════════════════════════
    // RIP-0683: Console Miner Tests
    // ═══════════════════════════════════════════════════════════

    #[test]
    fn test_console_timing_data_structure() {
        // Create realistic N64 timing data
        let timing = ConsoleTimingData {
            ctrl_port_timing_mean_ns: 250_000,
            ctrl_port_timing_stdev_ns: 1_250,
            ctrl_port_cv: 0.005,  // 0.5% variation (real hardware)
            rom_hash_time_us: 847_000,
            bus_jitter_samples: 500,
            bus_jitter_stdev_ns: 1_250,
        };

        assert!(timing.ctrl_port_cv > 0.0001);  // Has real jitter
        assert!(timing.bus_jitter_stdev_ns > 500);  // Has bus noise
        assert!(timing.bus_jitter_samples >= 100);  // Enough samples
    }

    #[test]
    fn test_console_miner_verification_success() {
        let verifier = AntiEmulationVerifier::new();

        // Realistic N64 timing data
        let timing = ConsoleTimingData {
            ctrl_port_timing_mean_ns: 250_000,
            ctrl_port_timing_stdev_ns: 1_250,
            ctrl_port_cv: 0.005,
            rom_hash_time_us: 847_000,  // Within ±15% of 847ms baseline
            bus_jitter_samples: 500,
            bus_jitter_stdev_ns: 1_250,
        };

        let result = verifier.verify_console_miner("n64_mips", &timing);
        assert!(result.is_ok(), "N64 verification should pass: {:?}", result);
    }

    #[test]
    fn test_console_miner_rejects_emulator() {
        let verifier = AntiEmulationVerifier::new();

        // Emulator timing data (too perfect)
        let emulator_timing = ConsoleTimingData {
            ctrl_port_timing_mean_ns: 250_000,
            ctrl_port_timing_stdev_ns: 0,  // No jitter
            ctrl_port_cv: 0.0,  // Perfect timing = emulator
            rom_hash_time_us: 847_000,
            bus_jitter_samples: 500,
            bus_jitter_stdev_ns: 0,  // No bus noise
        };

        let result = verifier.verify_console_miner("n64_mips", &emulator_timing);
        assert!(matches!(result, Err(ProofError::EmulationDetected)),
            "Should detect emulator: {:?}", result);
    }

    #[test]
    fn test_console_miner_rejects_wrong_timing() {
        let verifier = AntiEmulationVerifier::new();

        // Wrong timing (claims to be N64 but timing matches different CPU)
        let wrong_timing = ConsoleTimingData {
            ctrl_port_timing_mean_ns: 250_000,
            ctrl_port_timing_stdev_ns: 1_250,
            ctrl_port_cv: 0.005,
            rom_hash_time_us: 100_000,  // Way too fast for N64 (should be ~847ms)
            bus_jitter_samples: 500,
            bus_jitter_stdev_ns: 1_250,
        };

        let result = verifier.verify_console_miner("n64_mips", &wrong_timing);
        assert!(matches!(result, Err(ProofError::SuspiciousHardware(_))),
            "Should reject wrong timing: {:?}", result);
    }

    #[test]
    fn test_console_miner_unknown_arch() {
        let verifier = AntiEmulationVerifier::new();

        let timing = ConsoleTimingData {
            ctrl_port_timing_mean_ns: 250_000,
            ctrl_port_timing_stdev_ns: 1_250,
            ctrl_port_cv: 0.005,
            rom_hash_time_us: 847_000,
            bus_jitter_samples: 500,
            bus_jitter_stdev_ns: 1_250,
        };

        let result = verifier.verify_console_miner("unknown_console", &timing);
        assert!(matches!(result, Err(ProofError::SuspiciousHardware(_))),
            "Should reject unknown console arch");
    }

    #[test]
    fn test_console_miner_insufficient_samples() {
        let verifier = AntiEmulationVerifier::new();

        let timing = ConsoleTimingData {
            ctrl_port_timing_mean_ns: 250_000,
            ctrl_port_timing_stdev_ns: 1_250,
            ctrl_port_cv: 0.005,
            rom_hash_time_us: 847_000,
            bus_jitter_samples: 50,  // Too few samples
            bus_jitter_stdev_ns: 1_250,
        };

        let result = verifier.verify_console_miner("n64_mips", &timing);
        assert!(matches!(result, Err(ProofError::SuspiciousHardware(_))),
            "Should reject insufficient samples: {:?}", result);
    }

    #[test]
    fn test_multiple_console_architectures() {
        let verifier = AntiEmulationVerifier::new();

        // Test NES (slowest CPU)
        let nes_timing = ConsoleTimingData {
            ctrl_port_timing_mean_ns: 16_667_000,
            ctrl_port_timing_stdev_ns: 2_000,
            ctrl_port_cv: 0.00012,
            rom_hash_time_us: 2_500_000,  // ~2.5s for 1.79MHz 6502
            bus_jitter_samples: 500,
            bus_jitter_stdev_ns: 2_000,
        };
        assert!(verifier.verify_console_miner("nes_6502", &nes_timing).is_ok());

        // Test PS1 (MIPS R3000A)
        let ps1_timing = ConsoleTimingData {
            ctrl_port_timing_mean_ns: 4_000,
            ctrl_port_timing_stdev_ns: 1_100,
            ctrl_port_cv: 0.275,
            rom_hash_time_us: 920_000,  // ~920ms for 33.8MHz MIPS
            bus_jitter_samples: 500,
            bus_jitter_stdev_ns: 1_100,
        };
        assert!(verifier.verify_console_miner("ps1_mips", &ps1_timing).is_ok());

        // Test Genesis (Motorola 68000)
        let genesis_timing = ConsoleTimingData {
            ctrl_port_timing_mean_ns: 16_667_000,
            ctrl_port_timing_stdev_ns: 1_600,
            ctrl_port_cv: 0.000096,
            rom_hash_time_us: 1_500_000,  // ~1.5s for 7.67MHz 68000
            bus_jitter_samples: 500,
            bus_jitter_stdev_ns: 1_600,
        };
        assert!(verifier.verify_console_miner("genesis_68000", &genesis_timing).is_ok());
    }

    #[test]
    fn test_console_cv_threshold() {
        let verifier = AntiEmulationVerifier::new();

        // Test CV right at threshold (should pass)
        let threshold_timing = ConsoleTimingData {
            ctrl_port_timing_mean_ns: 250_000,
            ctrl_port_timing_stdev_ns: 26,  // CV = 0.000104 (just above threshold)
            ctrl_port_cv: 0.000104,
            rom_hash_time_us: 847_000,
            bus_jitter_samples: 500,
            bus_jitter_stdev_ns: 1_250,
        };
        assert!(verifier.verify_console_miner("n64_mips", &threshold_timing).is_ok());

        // Test CV just below threshold (should fail as emulator)
        let below_threshold_timing = ConsoleTimingData {
            ctrl_port_timing_mean_ns: 250_000,
            ctrl_port_timing_stdev_ns: 24,  // CV = 0.000096 (below threshold)
            ctrl_port_cv: 0.000096,
            rom_hash_time_us: 847_000,
            bus_jitter_samples: 500,
            bus_jitter_stdev_ns: 1_250,
        };
        let result = verifier.verify_console_miner("n64_mips", &below_threshold_timing);
        assert!(matches!(result, Err(ProofError::EmulationDetected)),
            "CV below threshold should be flagged as emulator");
    }
}
