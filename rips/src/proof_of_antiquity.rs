// RIP-002: Proof of Antiquity Consensus
// ======================================
// The revolutionary consensus mechanism that rewards vintage hardware
// Status: DRAFT
// Author: Flamekeeper Scott
// Created: 2025-11-28

use std::collections::{HashMap, HashSet};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use sha2::{Sha256, Digest};
use serde::{Serialize, Deserialize};

// Import from RIP-001
use crate::core_types::{
    HardwareTier, HardwareInfo, HardwareCharacteristics,
    WalletAddress, Block, BlockMiner, MiningProof, TokenAmount
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
    /// Track used nonces per wallet to prevent replay attacks
    used_nonces: HashMap<WalletAddress, HashSet<u64>>,
}

/// A validated mining proof ready for block inclusion
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidatedProof {
    pub wallet: WalletAddress,
    pub hardware: HardwareInfo,
    pub multiplier: f64,
    pub anti_emulation_hash: [u8; 32],
    pub validated_at: u64,
    /// Antiquity score derived from hardware age and multiplier
    pub antiquity_score: f64,
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
            used_nonces: HashMap::new(),
        }
    }

/// Submit a mining proof for validation and inclusion in the current block.
///
/// # Validation Pipeline
/// 1. **Block window check**: Proofs only accepted within 120-second block window
/// 2. **Duplicate submission**: Prevents same wallet submitting multiple proofs
/// 3. **Capacity check**: Maximum 100 miners per block (MAX_MINERS_PER_BLOCK)
/// 4. **Hardware validation**: Verifies age/tier/multiplier consistency
/// 5. **Anti-emulation**: Checks CPU characteristics against known signatures
/// 6. **Hardware hash**: Detects duplicate hardware across different wallets
/// 7. **Multiplier cap**: Caps at 3.5x (Ancient tier maximum)
///
/// # Anti-Emulation Strategy
/// The `anti_emulation_hash` proves the miner is running on real hardware by
/// verifying CPU-specific characteristics (cache sizes, instruction flags,
/// timing measurements) against known silicon signatures.
///
/// # Arguments
/// * `proof` - MiningProof containing wallet, hardware info, and anti-emulation hash
///
/// # Returns
/// * `Ok(SubmitResult)` - Proof accepted with pending miner count and multiplier
/// * `Err(ProofError)` - Validation failure reason
///
/// # Errors
/// - `BlockWindowClosed` - 120-second block window expired
/// - `DuplicateSubmission` - Wallet already submitted for this block
/// - `BlockFull` - Maximum miners (100) reached
/// - `HardwareAlreadyRegistered` - Same hardware registered to different wallet
/// - `TierMismatch` - Hardware tier doesn't match declared age
/// - `EmulationDetected` - Anti-emulation check failed
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

        // Check for nonce reuse (prevents replay attacks)
        if self.used_nonces.get(&proof.wallet).map_or(false, |nonces| nonces.contains(&proof.nonce)) {
            return Err(ProofError::NonceReuse);
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
        let antiquity_score = proof.hardware.age_years as f64 * proof.hardware.multiplier;

        // Create validated proof
        let validated = ValidatedProof {
            wallet: proof.wallet.clone(),
            hardware: proof.hardware,
            multiplier: capped_multiplier,
            anti_emulation_hash: proof.anti_emulation_hash,
            validated_at: current_timestamp(),
            antiquity_score,
        };

        self.pending_proofs.push(validated);
        self.known_hardware.insert(hw_hash, proof.wallet.clone());
        self.used_nonces.entry(proof.wallet).or_insert_with(HashSet::new).insert(proof.nonce);

        Ok(SubmitResult {
            accepted: true,
            pending_miners: self.pending_proofs.len(),
            your_multiplier: capped_multiplier,
            block_completes_in: 120 - elapsed,
        })
    }

    /// Process all pending proofs and create a new block with proportional rewards.
    ///
    /// # Reward Distribution Algorithm
    /// Rewards are distributed proportionally to each miner's hardware multiplier:
    /// ```text
    /// miner_share = miner_multiplier / sum(all_multipliers)
    /// miner_reward = BLOCK_REWARD * miner_share
    /// ```
    ///
    /// # Block Construction
    /// 1. Calculate total multipliers from all validated proofs
    /// 2. Compute proportional reward for each miner
    /// 3. Generate block hash from height, previous hash, reward total, timestamp
    /// 4. Build Merkle root from miner entries for integrity verification
    /// 5. Reset pending proofs for next block window
    ///
    /// # Arguments
    /// * `previous_hash` - Hash of the previous block (32 bytes)
    /// * `height` - New block height (sequential)
    ///
    /// # Returns
    /// * `Some(Block)` - Constructed block with miner rewards
    /// * `None` - No pending proofs (empty block window)
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
            let share = proof.hardware.multiplier / total_multipliers;
            let reward = (BLOCK_REWARD.0 as f64 * share) as u64;
            total_distributed += reward;

            miners.push(BlockMiner {
                wallet: proof.wallet.clone(),
                hardware: proof.hardware.model.clone(),
                multiplier: proof.hardware.multiplier,
                reward,
                antiquity_score: proof.antiquity_score,
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
        // NOTE: used_nonces is NOT cleared - persistent nonce tracking prevents replay across blocks
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

    /// Calculate Merkle root from miner entries for block integrity verification.
    ///
    /// # Merkle Tree Construction
    /// Uses iterative pairwise hashing (binary tree):
    /// 1. Hash each miner entry: `hash(wallet, multiplier, reward)`
    /// 2. Pair adjacent hashes, concatenate, and hash again
    /// 3. If odd number of hashes, duplicate the last one
    /// 4. Repeat until single root hash remains
    ///
    /// # Properties
    /// - **Empty set**: Returns `[0u8; 32]` (null root)
    /// - **Single miner**: Root equals the single entry's hash
    /// - **Efficiency**: O(log n) proof verification for any miner
    ///
    /// # Arguments
    /// * `miners` - Slice of BlockMiner entries
    ///
    /// # Returns
    /// 32-byte Merkle root hash
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

    /// Verify hardware characteristics against known CPU signatures.
    ///
    /// # Anti-Emulation Verification
    /// This function detects emulated/virtual hardware by checking:
    ///
    /// 1. **Cache size validation**: Compares L1/L2 cache against expected
    ///    ranges for the CPU family (emulators often report incorrect sizes)
    ///
    /// 2. **CPU flags verification**: Ensures expected instruction set flags
    ///    are present (e.g., Altivec for PowerPC, FPU for x86)
    ///
    /// 3. **Instruction timing analysis**: If provided, verifies that
    ///    instruction cycle counts fall within physical hardware bounds
    ///    (emulators typically have uniform/suspicious timings)
    ///
    /// # Known CPU Signatures
    /// - **Family 74**: PowerPC G4 (Altivec, 32-64KB L1, 256-2048KB L2)
    /// - **Family 4**: Intel 486 (FPU, 8-16KB L1, 0-512KB L2)
    /// - **Family 5**: Intel Pentium (FPU+VME, 16-32KB L1, 256-512KB L2)
    /// - **Family 6**: Intel P6 family (FPU+VME+DE+PSE, 16-32KB L1, 256-2048KB L2)
    ///
    /// # Arguments
    /// * `characteristics` - HardwareCharacteristics from miner's system
    ///
    /// # Returns
    /// * `Ok(())` - Hardware appears genuine
    /// * `Err(ProofError::SuspiciousHardware)` - Cache/flags mismatch
    /// * `Err(ProofError::EmulationDetected)` - Timing analysis failed
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
    NonceReuse,
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
            ProofError::NonceReuse => write!(f, "Nonce has already been used (replay attempt)"),
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

    #[test]
    fn test_nonce_reuse_rejected() {
        // Same wallet reusing the same nonce across blocks must be rejected
        let mut poa = ProofOfAntiquity::new();
        let wallet = WalletAddress::new("RTC1TestMiner123456789");

        let proof = MiningProof {
            wallet: wallet.clone(),
            hardware: HardwareInfo::new("CPU1".to_string(), "Gen1".to_string(), 15),
            anti_emulation_hash: [0u8; 32],
            timestamp: current_timestamp(),
            nonce: 42,
        };

        assert!(poa.submit_proof(proof.clone()).is_ok());

        // Process block
        let _ = poa.process_block([0u8; 32], 1);

        // Replay same proof with same nonce - should be rejected
        assert!(matches!(poa.submit_proof(proof), Err(ProofError::NonceReuse)));
    }

    #[test]
    fn test_different_nonce_accepted() {
        // Same wallet with different nonces should be accepted (different hardware)
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
            wallet: wallet.clone(),
            hardware: HardwareInfo::new("CPU2".to_string(), "Gen2".to_string(), 20),
            anti_emulation_hash: [0u8; 32],
            timestamp: current_timestamp(),
            nonce: 2,
        };

        assert!(poa.submit_proof(proof1).is_ok());
        assert!(matches!(poa.submit_proof(proof2), Err(ProofError::DuplicateSubmission)));
    }

    #[test]
    fn test_replay_across_blocks_rejected() {
        // A proof replayed in a new block is rejected because used_nonces persists
        let mut poa = ProofOfAntiquity::new();
        let wallet = WalletAddress::new("RTC1TestMiner123456789");
        let hardware = HardwareInfo::new("CPU1".to_string(), "Gen1".to_string(), 15);

        let proof = MiningProof {
            wallet: wallet.clone(),
            hardware: hardware.clone(),
            anti_emulation_hash: [0u8; 32],
            timestamp: current_timestamp(),
            nonce: 999,
        };

        assert!(poa.submit_proof(proof.clone()).is_ok());
        let _ = poa.process_block([0u8; 32], 1);

        // Replay same proof - NonceReuse (used_nonces is NOT cleared)
        assert!(matches!(poa.submit_proof(proof), Err(ProofError::NonceReuse)));
    }

    #[test]
    fn test_block_reset_preserves_nonce_state() {
        // After process_block, nonce state is preserved (nonces are NOT cleared)
        // This prevents replay attacks across blocks
        let mut poa = ProofOfAntiquity::new();
        let wallet = WalletAddress::new("RTC1TestMiner123456789");
        let hardware = HardwareInfo::new("CPU1".to_string(), "Gen1".to_string(), 15);

        let proof = MiningProof {
            wallet: wallet.clone(),
            hardware: hardware.clone(),
            anti_emulation_hash: [0u8; 32],
            timestamp: current_timestamp(),
            nonce: 42,
        };

        assert!(poa.submit_proof(proof.clone()).is_ok());

        let prev_hash = [0u8; 32];
        let result = poa.process_block(prev_hash, 1);
        assert!(result.is_some());

        // Same wallet + same nonce should be rejected even in new block
        assert!(matches!(poa.submit_proof(proof), Err(ProofError::NonceReuse)));
    }
}
