// RIP-0003: RustChain Deep Entropy Verification
// ==============================================
// Multi-layer entropy verification that makes emulation economically irrational.
// Status: DRAFT
// Author: Flamekeeper Scott
// Created: 2025-11-28

//! # Deep Entropy Hardware Verification
//!
//! This module implements multi-layer entropy verification to ensure that
//! mining is performed on real vintage hardware, not emulators.
//!
//! ## Philosophy
//!
//! > "It should be cheaper to buy a $50 486 than to emulate one."
//!
//! ## Entropy Layers
//!
//! 1. **Instruction Timing Entropy** - CPU-specific timing patterns
//! 2. **Memory Access Pattern Entropy** - Cache/DRAM behavior
//! 3. **Bus Timing Entropy** - ISA/PCI/PCIe timing signatures
//! 4. **Thermal Entropy** - Clock stability, DVFS detection
//! 5. **Architectural Quirk Entropy** - Known hardware bugs/quirks

use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use std::collections::HashMap;
use std::time::Instant;
use rand::prelude::SliceRandom;

// Import from RIP-001
use crate::core_types::HardwareCharacteristics;

// =============================================================================
// Constants
// =============================================================================

/// Minimum entropy bits required
pub const MIN_ENTROPY_BITS: u32 = 64;

/// Emulation cost threshold in USD
pub const EMULATION_COST_THRESHOLD_USD: f64 = 100.0;

/// Number of samples required for timing measurements
pub const ENTROPY_SAMPLES_REQUIRED: usize = 1000;

/// Minimum total entropy score for valid proof
pub const MIN_TOTAL_ENTROPY_SCORE: f64 = 0.65;

// =============================================================================
// Hardware Profiles
// =============================================================================

/// Known hardware profile for validation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareProfile {
    /// Profile name (e.g., "486DX2", "G4")
    pub name: String,
    /// CPU family number
    pub cpu_family: u32,
    /// Year introduced
    pub year_introduced: u32,
    /// Expected bus type
    pub expected_bus_type: String,
    /// Known hardware quirks
    pub expected_quirks: Vec<String>,
    /// Emulation difficulty (0.0-1.0)
    pub emulation_difficulty: f64,
    /// Expected instruction timing ranges
    pub instruction_timings: HashMap<String, (f64, f64)>,
}

impl HardwareProfile {
    /// Create a new hardware profile
    pub fn new(
        name: String,
        cpu_family: u32,
        year_introduced: u32,
        expected_bus_type: String,
        expected_quirks: Vec<String>,
        emulation_difficulty: f64,
    ) -> Self {
        HardwareProfile {
            name,
            cpu_family,
            year_introduced,
            expected_bus_type,
            expected_quirks,
            emulation_difficulty,
            instruction_timings: HashMap::new(),
        }
    }

    /// Add instruction timing range
    pub fn with_timing(mut self, instruction: String, min: f64, max: f64) -> Self {
        self.instruction_timings.insert(instruction, (min, max));
        self
    }
}

/// Build known hardware profiles database
pub fn get_hardware_profiles() -> HashMap<String, HardwareProfile> {
    let mut profiles = HashMap::new();

    // Intel 486 DX2-66 (1992)
    profiles.insert("486DX2".to_string(), HardwareProfile::new(
        "Intel 486 DX2-66".to_string(),
        4,
        1992,
        "ISA".to_string(),
        vec!["no_rdtsc".to_string(), "a20_gate".to_string()],
        0.95,
    )
    .with_timing("mul".to_string(), 13.0, 42.0)
    .with_timing("div".to_string(), 40.0, 44.0)
    .with_timing("fadd".to_string(), 8.0, 20.0)
    .with_timing("fmul".to_string(), 16.0, 27.0));

    // Intel Pentium 100 (1994)
    profiles.insert("Pentium".to_string(), HardwareProfile::new(
        "Intel Pentium 100".to_string(),
        5,
        1994,
        "PCI".to_string(),
        vec!["fdiv_bug".to_string()],
        0.90,
    )
    .with_timing("mul".to_string(), 10.0, 11.0)
    .with_timing("div".to_string(), 17.0, 41.0)
    .with_timing("fadd".to_string(), 3.0, 3.0)
    .with_timing("fmul".to_string(), 3.0, 3.0));

    // Intel Pentium II (1997)
    profiles.insert("PentiumII".to_string(), HardwareProfile::new(
        "Intel Pentium II".to_string(),
        6,
        1997,
        "PCI".to_string(),
        vec!["f00f_bug".to_string()],
        0.85,
    )
    .with_timing("mul".to_string(), 4.0, 5.0)
    .with_timing("div".to_string(), 17.0, 41.0)
    .with_timing("fadd".to_string(), 3.0, 3.0)
    .with_timing("fmul".to_string(), 5.0, 5.0));

    // PowerPC G4 (1999)
    profiles.insert("G4".to_string(), HardwareProfile::new(
        "PowerPC G4".to_string(),
        74,
        1999,
        "PCI".to_string(),
        vec!["altivec".to_string(), "big_endian".to_string()],
        0.85,
    )
    .with_timing("mul".to_string(), 3.0, 4.0)
    .with_timing("div".to_string(), 20.0, 35.0)
    .with_timing("fadd".to_string(), 5.0, 5.0)
    .with_timing("fmul".to_string(), 5.0, 5.0));

    // PowerPC G5 (2003)
    profiles.insert("G5".to_string(), HardwareProfile::new(
        "PowerPC G5".to_string(),
        75,
        2003,
        "PCI-X".to_string(),
        vec!["altivec".to_string(), "big_endian".to_string(), "970fx".to_string()],
        0.80,
    )
    .with_timing("mul".to_string(), 2.0, 4.0)
    .with_timing("div".to_string(), 15.0, 33.0)
    .with_timing("fadd".to_string(), 4.0, 4.0)
    .with_timing("fmul".to_string(), 4.0, 4.0));

    // DEC Alpha 21264 (1998)
    profiles.insert("Alpha".to_string(), HardwareProfile::new(
        "DEC Alpha 21264".to_string(),
        21,
        1998,
        "PCI".to_string(),
        vec!["alpha_pal".to_string(), "64bit_native".to_string()],
        0.95,
    )
    .with_timing("mul".to_string(), 4.0, 7.0)
    .with_timing("div".to_string(), 12.0, 16.0)
    .with_timing("fadd".to_string(), 4.0, 4.0)
    .with_timing("fmul".to_string(), 4.0, 4.0));

    profiles
}

// =============================================================================
// Entropy Layers
// =============================================================================

/// Layer 1: Instruction timing measurements
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InstructionTimingLayer {
    /// Instruction -> {mean, std_dev, min, max}
    pub timings: HashMap<String, TimingStats>,
    /// Cache miss penalty in cycles
    pub cache_miss_penalty: f64,
    /// Branch misprediction cost in cycles
    pub branch_misprediction_cost: f64,
}

/// Timing statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimingStats {
    /// Mean timing
    pub mean: f64,
    /// Standard deviation
    pub std_dev: f64,
    /// Minimum observed
    pub min: f64,
    /// Maximum observed
    pub max: f64,
    /// Sample count
    pub samples: u32,
}

impl TimingStats {
    /// Create new timing stats
    pub fn new() -> Self {
        TimingStats {
            mean: 0.0,
            std_dev: 0.0,
            min: f64::MAX,
            max: f64::MIN,
            samples: 0,
        }
    }

    /// Add a sample
    pub fn add_sample(&mut self, value: f64) {
        self.samples += 1;
        let delta = value - self.mean;
        self.mean += delta / self.samples as f64;
        self.min = self.min.min(value);
        self.max = self.max.max(value);

        // Welford's online algorithm for variance
        if self.samples > 1 {
            let delta2 = value - self.mean;
            self.std_dev = ((self.std_dev.powi(2) * (self.samples - 1) as f64
                + delta * delta2) / self.samples as f64)
                .sqrt();
        }
    }
}

impl Default for TimingStats {
    fn default() -> Self {
        Self::new()
    }
}

/// Layer 2: Memory access patterns
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryPatternLayer {
    /// Sequential read rate (bytes/ns)
    pub sequential_read_rate: f64,
    /// Random read rate (bytes/ns)
    pub random_read_rate: f64,
    /// Stride patterns: stride size -> rate
    pub stride_patterns: HashMap<u32, f64>,
    /// Page crossing penalty in cycles
    pub page_crossing_penalty: f64,
    /// DRAM refresh interference detected
    pub refresh_interference_detected: bool,
}

/// Layer 3: Bus timing characteristics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BusTimingLayer {
    /// Bus type (ISA, PCI, PCIe, etc.)
    pub bus_type: String,
    /// I/O read latency in nanoseconds
    pub io_read_ns: f64,
    /// I/O write latency in nanoseconds
    pub io_write_ns: f64,
    /// Timing variance
    pub timing_variance: f64,
    /// Interrupt latency in microseconds
    pub interrupt_latency_us: f64,
}

/// Layer 4: Thermal/clock characteristics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalEntropyLayer {
    /// Clock frequency in MHz
    pub clock_frequency_mhz: f64,
    /// Clock variance
    pub clock_variance: f64,
    /// Frequency changed during measurement
    pub frequency_changed: bool,
    /// C-states detected (power saving states)
    pub c_states_detected: Vec<String>,
    /// P-states detected (performance states)
    pub p_states_detected: Vec<String>,
}

/// Layer 5: Architectural quirks
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuirkEntropyLayer {
    /// Detected quirks
    pub detected_quirks: Vec<String>,
    /// Quirk test results
    pub quirk_test_results: HashMap<String, QuirkTestResult>,
}

/// Quirk test result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuirkTestResult {
    /// Whether quirk was detected
    pub detected: bool,
    /// Confidence level (0.0-1.0)
    pub confidence: f64,
    /// Additional data
    pub data: HashMap<String, String>,
}

// =============================================================================
// Entropy Proof and Verification
// =============================================================================

/// Complete entropy proof from hardware
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntropyProof {
    /// Instruction timing layer
    pub instruction_layer: InstructionTimingLayer,
    /// Memory pattern layer
    pub memory_layer: MemoryPatternLayer,
    /// Bus timing layer
    pub bus_layer: BusTimingLayer,
    /// Thermal entropy layer
    pub thermal_layer: ThermalEntropyLayer,
    /// Quirk entropy layer
    pub quirk_layer: QuirkEntropyLayer,
    /// Challenge response bytes
    pub challenge_response: Vec<u8>,
    /// Computation time in microseconds
    pub computation_time_us: u64,
    /// Timestamp
    pub timestamp: u64,
    /// Signature hash
    pub signature_hash: String,
}

/// Entropy scores from verification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntropyScores {
    /// Instruction timing score (0.0-1.0)
    pub instruction: f64,
    /// Memory pattern score (0.0-1.0)
    pub memory: f64,
    /// Bus timing score (0.0-1.0)
    pub bus: f64,
    /// Thermal entropy score (0.0-1.0)
    pub thermal: f64,
    /// Quirk entropy score (0.0-1.0)
    pub quirks: f64,
    /// Total weighted score
    pub total: f64,
}

impl Default for EntropyScores {
    fn default() -> Self {
        EntropyScores {
            instruction: 0.0,
            memory: 0.0,
            bus: 0.0,
            thermal: 0.0,
            quirks: 0.0,
            total: 0.0,
        }
    }
}

/// Result of entropy verification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationResult {
    /// Whether proof is valid
    pub valid: bool,
    /// Total entropy score
    pub total_score: f64,
    /// Individual layer scores
    pub scores: EntropyScores,
    /// Issues found
    pub issues: Vec<String>,
    /// Estimated emulation probability (0.0-1.0)
    pub emulation_probability: f64,
}

/// Challenge for hardware to solve
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Challenge {
    /// Challenge nonce
    pub nonce: String,
    /// Operations to perform
    pub operations: Vec<ChallengeOperation>,
    /// Expected time range in microseconds
    pub expected_time_range_us: (u64, u64),
    /// Challenge timestamp
    pub timestamp: u64,
    /// Challenge expiry
    pub expires_at: u64,
}

/// Challenge operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChallengeOperation {
    /// Operation type
    pub op: String,
    /// Operation value
    pub value: f64,
}

// =============================================================================
// Deep Entropy Verifier
// =============================================================================

/// Multi-layer entropy verification system
pub struct DeepEntropyVerifier {
    /// Hardware profiles database
    profiles: HashMap<String, HardwareProfile>,
    /// Verification thresholds
    thresholds: VerificationThresholds,
}

/// Verification thresholds
#[derive(Debug, Clone)]
pub struct VerificationThresholds {
    pub min_instruction_entropy: f64,
    pub min_memory_entropy: f64,
    pub min_bus_entropy: f64,
    pub min_thermal_entropy: f64,
    pub min_quirk_entropy: f64,
    pub total_min_entropy: f64,
}

impl Default for VerificationThresholds {
    fn default() -> Self {
        VerificationThresholds {
            min_instruction_entropy: 0.15,
            min_memory_entropy: 0.10,
            min_bus_entropy: 0.15,
            min_thermal_entropy: 0.05,
            min_quirk_entropy: 0.20,
            total_min_entropy: MIN_TOTAL_ENTROPY_SCORE,
        }
    }
}

impl DeepEntropyVerifier {
    /// Create a new deep entropy verifier
    pub fn new() -> Self {
        DeepEntropyVerifier {
            profiles: get_hardware_profiles(),
            thresholds: VerificationThresholds::default(),
        }
    }

    /// Generate a challenge for hardware to solve
    pub fn generate_challenge(&self) -> Challenge {
        use rand::Rng;
        let mut rng = rand::thread_rng();

        let nonce_bytes: [u8; 32] = rng.gen();
        let nonce = hex::encode(nonce_bytes);

        let operations = vec![
            ChallengeOperation {
                op: "mul".to_string(),
                value: rng.gen_range(1..=1_000_000) as f64,
            },
            ChallengeOperation {
                op: "div".to_string(),
                value: rng.gen_range(1..=1000) as f64,
            },
            ChallengeOperation {
                op: "fadd".to_string(),
                value: rng.gen_range(0.0..=1000.0),
            },
            ChallengeOperation {
                op: "memory".to_string(),
                value: *[1, 4, 16, 64, 256].choose(&mut rng).unwrap() as f64,
            },
        ];

        let now = current_timestamp();
        Challenge {
            nonce,
            operations,
            expected_time_range_us: (1000, 100000), // 1ms to 100ms
            timestamp: now,
            expires_at: now + 300, // 5 minute expiry
        }
    }

    /// Verify an entropy proof against claimed hardware
    pub fn verify(&self, proof: &EntropyProof, claimed_hardware: &str) -> VerificationResult {
        let mut scores = EntropyScores::default();
        let mut issues = Vec::new();

        // Get expected profile
        let profile = match self.profiles.get(claimed_hardware) {
            Some(p) => p,
            None => {
                return VerificationResult {
                    valid: false,
                    total_score: 0.0,
                    scores,
                    issues: vec![format!("Unknown hardware profile: {}", claimed_hardware)],
                    emulation_probability: 1.0,
                };
            }
        };

        // Layer 1: Verify instruction timing
        scores.instruction = self.verify_instruction_layer(&proof.instruction_layer, profile);
        if scores.instruction < self.thresholds.min_instruction_entropy {
            issues.push(format!(
                "Instruction timing entropy too low: {:.2}",
                scores.instruction
            ));
        }

        // Layer 2: Verify memory patterns
        scores.memory = self.verify_memory_layer(&proof.memory_layer, profile);
        if scores.memory < self.thresholds.min_memory_entropy {
            issues.push(format!(
                "Memory pattern entropy too low: {:.2}",
                scores.memory
            ));
        }

        // Layer 3: Verify bus timing
        scores.bus = self.verify_bus_layer(&proof.bus_layer, profile);
        if scores.bus < self.thresholds.min_bus_entropy {
            issues.push(format!("Bus timing entropy too low: {:.2}", scores.bus));
        }

        // Layer 4: Verify thermal characteristics
        scores.thermal = self.verify_thermal_layer(&proof.thermal_layer, profile);
        if scores.thermal < self.thresholds.min_thermal_entropy {
            issues.push(format!("Thermal entropy suspicious: {:.2}", scores.thermal));
        }

        // Layer 5: Verify architectural quirks
        scores.quirks = self.verify_quirk_layer(&proof.quirk_layer, profile);
        if scores.quirks < self.thresholds.min_quirk_entropy {
            issues.push(format!("Expected quirks not detected: {:.2}", scores.quirks));
        }

        // Calculate total score (weighted)
        scores.total = scores.instruction * 0.25
            + scores.memory * 0.20
            + scores.bus * 0.20
            + scores.thermal * 0.15
            + scores.quirks * 0.20;

        // Calculate emulation probability
        let emulation_prob =
            (0.0_f64).max(1.0 - (scores.total * profile.emulation_difficulty));

        let valid = scores.total >= self.thresholds.total_min_entropy && issues.is_empty();

        VerificationResult {
            valid,
            total_score: scores.total,
            scores,
            issues,
            emulation_probability: emulation_prob,
        }
    }

    fn verify_instruction_layer(
        &self,
        layer: &InstructionTimingLayer,
        profile: &HardwareProfile,
    ) -> f64 {
        let mut score = 0.0;
        let mut checks = 0;

        for (instruction, (min_expected, max_expected)) in &profile.instruction_timings {
            if let Some(measured) = layer.timings.get(instruction) {
                checks += 1;

                // Check if mean is within expected range
                if *min_expected <= measured.mean && measured.mean <= *max_expected {
                    score += 0.5;
                }

                // Check if variance is reasonable (vintage has natural jitter)
                if measured.std_dev > 0.0 && measured.std_dev < measured.mean * 0.5 {
                    score += 0.5;
                }
            }
        }

        if checks > 0 {
            score / checks as f64
        } else {
            0.0
        }
    }

    fn verify_memory_layer(&self, layer: &MemoryPatternLayer, _profile: &HardwareProfile) -> f64 {
        let mut score = 0.0;

        // Vintage hardware should show significant stride-dependent timing
        if !layer.stride_patterns.is_empty() {
            let stride_1 = layer.stride_patterns.get(&1).unwrap_or(&1.0);
            let stride_64 = layer.stride_patterns.get(&64).unwrap_or(&1.0);
            if stride_64 / stride_1 > 1.5 {
                score += 0.3; // Good cache behavior signature
            }
        }

        // Page crossing penalty should be detectable
        if layer.page_crossing_penalty > 10.0 {
            score += 0.3;
        }

        // DRAM refresh interference is strong signal of real hardware
        if layer.refresh_interference_detected {
            score += 0.4;
        }

        score
    }

    fn verify_bus_layer(&self, layer: &BusTimingLayer, profile: &HardwareProfile) -> f64 {
        let mut score = 0.0;

        // Check bus type matches
        if layer.bus_type == profile.expected_bus_type {
            score += 0.5;
        }

        // Verify I/O timing is in expected range for bus type
        let expected_ranges: HashMap<&str, (f64, f64)> = [
            ("ISA", (1000.0, 2500.0)),
            ("EISA", (500.0, 1500.0)),
            ("VLB", (100.0, 500.0)),
            ("PCI", (50.0, 200.0)),
            ("PCI-X", (30.0, 150.0)),
            ("AGP", (30.0, 150.0)),
            ("PCIe", (5.0, 50.0)),
        ]
        .iter()
        .cloned()
        .collect();

        if let Some((min_io, max_io)) = expected_ranges.get(layer.bus_type.as_str()) {
            if *min_io <= layer.io_read_ns && layer.io_read_ns <= *max_io {
                score += 0.3;
            }
        }

        // Vintage hardware has slower interrupts
        if layer.interrupt_latency_us > 1.0 {
            score += 0.2;
        }

        score
    }

    fn verify_thermal_layer(&self, layer: &ThermalEntropyLayer, _profile: &HardwareProfile) -> f64 {
        let mut score = 0.0;

        // Vintage hardware shouldn't have DVFS
        if !layer.frequency_changed {
            score += 0.4;
        }

        // No C-states on vintage hardware
        if layer.c_states_detected.is_empty() {
            score += 0.3;
        }

        // No P-states on vintage hardware
        if layer.p_states_detected.is_empty() {
            score += 0.3;
        }

        score
    }

    fn verify_quirk_layer(&self, layer: &QuirkEntropyLayer, profile: &HardwareProfile) -> f64 {
        if profile.expected_quirks.is_empty() {
            return 1.0;
        }

        let mut detected = 0;
        for expected_quirk in &profile.expected_quirks {
            if layer.detected_quirks.iter().any(|q| q == expected_quirk) {
                detected += 1;
            } else if let Some(result) = layer.quirk_test_results.get(expected_quirk) {
                if result.detected && result.confidence > 0.8 {
                    detected += 1;
                }
            }
        }

        detected as f64 / profile.expected_quirks.len() as f64
    }

    /// Convert hardware characteristics to entropy proof
    pub fn characteristics_to_proof(
        &self,
        chars: &HardwareCharacteristics,
        challenge: &Challenge,
        computation_time_us: u64,
    ) -> EntropyProof {
        // Build instruction timing layer from characteristics
        let mut instruction_timings = HashMap::new();
        for (instr, timing) in &chars.instruction_timings {
            let mut stats = TimingStats::new();
            // Simulate multiple samples from single timing
            for _ in 0..ENTROPY_SAMPLES_REQUIRED {
                // Add some natural jitter (±5%)
                let jitter = *timing as f64 * (0.95 + rand::random::<f64>() * 0.1);
                stats.add_sample(jitter);
            }
            instruction_timings.insert(instr.clone(), stats);
        }

        // Build cache info from characteristics
        let cache_miss_penalty = if chars.cache_sizes.l2 > 0 {
            50.0 // Typical L2 miss penalty
        } else {
            100.0 // Higher penalty for no L2
        };

        let instruction_layer = InstructionTimingLayer {
            timings: instruction_timings,
            cache_miss_penalty,
            branch_misprediction_cost: 15.0, // Typical for vintage CPUs
        };

        // Memory pattern layer
        let mut stride_patterns = HashMap::new();
        stride_patterns.insert(1, 1.0);
        stride_patterns.insert(4, 0.95);
        stride_patterns.insert(16, 0.85);
        stride_patterns.insert(64, 0.60);
        stride_patterns.insert(256, 0.40);

        let memory_layer = MemoryPatternLayer {
            sequential_read_rate: 0.5, // MB/s typical for vintage
            random_read_rate: 0.1,
            stride_patterns,
            page_crossing_penalty: 50.0,
            refresh_interference_detected: true,
        };

        // Bus timing layer based on CPU family
        let (bus_type, io_read_ns, io_write_ns, interrupt_latency) =
            match chars.cpu_family {
                4 => ("ISA".to_string(), 1500.0, 2000.0, 10.0),
                5 => ("PCI".to_string(), 100.0, 150.0, 5.0),
                6 => ("PCI".to_string(), 80.0, 120.0, 4.0),
                74 | 75 => ("PCI".to_string(), 100.0, 150.0, 5.0),
                21 => ("PCI".to_string(), 90.0, 130.0, 3.0),
                _ => ("PCI".to_string(), 100.0, 150.0, 5.0),
            };

        let bus_layer = BusTimingLayer {
            bus_type,
            io_read_ns,
            io_write_ns,
            timing_variance: 0.1,
            interrupt_latency_us: interrupt_latency,
        };

        // Thermal layer - vintage hardware has stable clocks
        let thermal_layer = ThermalEntropyLayer {
            clock_frequency_mhz: 100.0, // Placeholder
            clock_variance: 0.001,
            frequency_changed: false,
            c_states_detected: Vec::new(),
            p_states_detected: Vec::new(),
        };

        // Quirk layer
        let mut detected_quirks = Vec::new();
        let mut quirk_results = HashMap::new();

        for flag in &chars.cpu_flags {
            if flag == "fdiv_bug" || flag == "altivec" || flag == "a20_gate" {
                detected_quirks.push(flag.clone());
                quirk_results.insert(
                    flag.clone(),
                    QuirkTestResult {
                        detected: true,
                        confidence: 0.95,
                        data: HashMap::new(),
                    },
                );
            }
        }

        let quirk_layer = QuirkEntropyLayer {
            detected_quirks,
            quirk_test_results: quirk_results,
        };

        // Generate challenge response hash
        let mut hasher = Sha256::new();
        hasher.update(&challenge.nonce);
        hasher.update(&chars.unique_id);
        hasher.update(&computation_time_us.to_le_bytes());
        let response = hasher.finalize().to_vec();
        let signature_hash = hex::encode(&response);

        EntropyProof {
            instruction_layer,
            memory_layer,
            bus_layer,
            thermal_layer,
            quirk_layer,
            challenge_response: response,
            computation_time_us,
            timestamp: current_timestamp(),
            signature_hash,
        }
    }
}

impl Default for DeepEntropyVerifier {
    fn default() -> Self {
        Self::new()
    }
}

// =============================================================================
// Economic Analysis
// =============================================================================

/// Analyze the economic cost of emulating vs. buying hardware
pub fn emulation_cost_analysis(hardware_type: &str) -> EmulationCostAnalysis {
    let profiles = get_hardware_profiles();
    let profile = match profiles.get(hardware_type) {
        Some(p) => p,
        None => {
            return EmulationCostAnalysis {
                hardware: hardware_type.to_string(),
                error: Some(format!("Unknown hardware: {}", hardware_type)),
                ..Default::default()
            };
        }
    };

    // Emulation costs
    let gpu_hours_to_emulate = 50.0 + (profile.emulation_difficulty * 100.0);
    let gpu_cost_per_hour = 0.50;
    let emulation_cost = gpu_hours_to_emulate * gpu_cost_per_hour;

    // Real hardware costs (approximate eBay prices)
    let hardware_prices: HashMap<&str, f64> = [
        ("486DX2", 50.0),
        ("Pentium", 40.0),
        ("PentiumII", 30.0),
        ("G4", 80.0),
        ("G5", 150.0),
        ("Alpha", 200.0),
    ]
    .iter()
    .cloned()
    .collect();

    let real_cost = hardware_prices.get(hardware_type).unwrap_or(&100.0);

    // Power costs (per year at $0.10/kWh)
    let power_watts: HashMap<&str, f64> = [
        ("486DX2", 15.0),
        ("Pentium", 25.0),
        ("G4", 50.0),
        ("G5", 100.0),
    ]
    .iter()
    .cloned()
    .collect();

    let watts = power_watts.get(hardware_type).unwrap_or(&50.0);
    let yearly_power_cost = watts * 24.0 * 365.0 * 0.10 / 1000.0;

    let breakeven_days = if yearly_power_cost > 0.0 {
        (emulation_cost - real_cost) / (yearly_power_cost / 365.0)
    } else {
        0.0
    };

    let recommendation = if emulation_cost > *real_cost {
        "BUY REAL HARDWARE"
    } else {
        "EMULATE"
    };

    EmulationCostAnalysis {
        hardware: profile.name.clone(),
        error: None,
        emulation_difficulty: profile.emulation_difficulty,
        estimated_gpu_hours: gpu_hours_to_emulate,
        emulation_cost_usd: emulation_cost,
        real_hardware_cost_usd: *real_cost,
        yearly_power_cost_usd: yearly_power_cost,
        breakeven_days,
        recommendation: recommendation.to_string(),
        economic_conclusion: format!(
            "Buying a real {} for ${:.2} is {} than emulating (${:.2})",
            profile.name,
            real_cost,
            if *real_cost < emulation_cost {
                "cheaper"
            } else {
                "more expensive"
            },
            emulation_cost
        ),
    }
}

/// Economic analysis results
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct EmulationCostAnalysis {
    /// Hardware name
    pub hardware: String,
    /// Error message if any
    pub error: Option<String>,
    /// Emulation difficulty (0.0-1.0)
    pub emulation_difficulty: f64,
    /// Estimated GPU hours to emulate
    pub estimated_gpu_hours: f64,
    /// Cost to emulate in USD
    pub emulation_cost_usd: f64,
    /// Cost to buy real hardware in USD
    pub real_hardware_cost_usd: f64,
    /// Yearly power cost in USD
    pub yearly_power_cost_usd: f64,
    /// Days to breakeven
    pub breakeven_days: f64,
    /// Recommendation
    pub recommendation: String,
    /// Economic conclusion
    pub economic_conclusion: String,
}

// =============================================================================
// Helper Functions
// =============================================================================

/// Get current Unix timestamp
fn current_timestamp() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Measure time for a function execution
pub fn measure_time_us<F: FnOnce() -> R, R>(f: F) -> (R, u64) {
    let start = Instant::now();
    let result = f();
    let elapsed = start.elapsed().as_micros() as u64;
    (result, elapsed)
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hardware_profiles_exist() {
        let profiles = get_hardware_profiles();
        assert!(profiles.contains_key("486DX2"));
        assert!(profiles.contains_key("G4"));
        assert!(profiles.contains_key("Alpha"));
    }

    #[test]
    fn test_verifier_creation() {
        let verifier = DeepEntropyVerifier::new();
        assert!(!verifier.profiles.is_empty());
    }

    #[test]
    fn test_challenge_generation() {
        let verifier = DeepEntropyVerifier::new();
        let challenge = verifier.generate_challenge();

        assert!(!challenge.nonce.is_empty());
        assert!(!challenge.operations.is_empty());
        assert!(challenge.expires_at > challenge.timestamp);
    }

    #[test]
    fn test_verify_unknown_hardware() {
        let verifier = DeepEntropyVerifier::new();
        let proof = create_test_proof();

        let result = verifier.verify(&proof, "UnknownCPU");

        assert!(!result.valid);
        assert_eq!(result.total_score, 0.0);
        assert!(result.issues.iter().any(|i| i.contains("Unknown hardware")));
    }

    #[test]
    fn test_emulation_cost_analysis() {
        let analysis = emulation_cost_analysis("486DX2");

        assert!(analysis.error.is_none());
        assert!(analysis.emulation_cost_usd > 0.0);
        assert!(analysis.real_hardware_cost_usd > 0.0);
        assert_eq!(analysis.recommendation, "BUY REAL HARDWARE");
        assert!(analysis.economic_conclusion.contains("cheaper"));
    }

    #[test]
    fn test_timing_stats() {
        let mut stats = TimingStats::new();

        // Add samples
        for i in 1..=100 {
            stats.add_sample(i as f64);
        }

        assert_eq!(stats.samples, 100);
        assert!((stats.mean - 50.5).abs() < 0.1);
        assert!(stats.std_dev > 0.0);
    }

    #[test]
    fn test_measure_time() {
        let (_, elapsed_us) = measure_time_us(|| {
            // Busy work
            let mut sum = 0;
            for i in 0..1000 {
                sum += i;
            }
            sum
        });

        assert!(elapsed_us > 0);
        assert!(elapsed_us < 1_000_000); // Should be under 1 second
    }

    fn create_test_proof() -> EntropyProof {
        EntropyProof {
            instruction_layer: InstructionTimingLayer {
                timings: HashMap::new(),
                cache_miss_penalty: 50.0,
                branch_misprediction_cost: 15.0,
            },
            memory_layer: MemoryPatternLayer {
                sequential_read_rate: 0.5,
                random_read_rate: 0.1,
                stride_patterns: HashMap::new(),
                page_crossing_penalty: 50.0,
                refresh_interference_detected: true,
            },
            bus_layer: BusTimingLayer {
                bus_type: "PCI".to_string(),
                io_read_ns: 100.0,
                io_write_ns: 150.0,
                timing_variance: 0.1,
                interrupt_latency_us: 5.0,
            },
            thermal_layer: ThermalEntropyLayer {
                clock_frequency_mhz: 100.0,
                clock_variance: 0.001,
                frequency_changed: false,
                c_states_detected: Vec::new(),
                p_states_detected: Vec::new(),
            },
            quirk_layer: QuirkEntropyLayer {
                detected_quirks: Vec::new(),
                quirk_test_results: HashMap::new(),
            },
            challenge_response: vec![0u8; 32],
            computation_time_us: 1000,
            timestamp: current_timestamp(),
            signature_hash: String::new(),
        }
    }
}
