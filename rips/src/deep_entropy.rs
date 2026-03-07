// RIP-003: Deep Entropy Verification
// ===================================
// Anti-emulation system using hardware entropy sources
// Status: DRAFT
// Author: Flamekeeper Scott
// Created: 2025-11-28

use std::collections::HashMap;
use std::time::{Duration, Instant};
use serde::{Serialize, Deserialize};
use sha2::{Sha256, Digest};

/// Entropy verification challenge
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Challenge {
    /// Random seed for challenge
    pub seed: [u8; 32],
    /// Challenge type
    pub challenge_type: ChallengeType,
    /// Difficulty level
    pub difficulty: u32,
    /// Timestamp
    pub issued_at: u64,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum ChallengeType {
    /// Cache timing challenge
    CacheTiming,
    /// Instruction timing challenge
    InstructionTiming,
    /// Thermal entropy challenge
    ThermalEntropy,
    /// Clock skew challenge
    ClockSkew,
}

/// Entropy proof response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntropyProof {
    /// Challenge being answered
    pub challenge_seed: [u8; 32],
    /// Measured latencies
    pub measurements: Vec<f64>,
    /// Statistical properties
    pub stats: EntropyStats,
    /// Hardware signature
    pub hw_signature: [u8; 32],
    /// Timestamp
    pub responded_at: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntropyStats {
    pub mean: f64,
    pub std_dev: f64,
    pub min: f64,
    pub max: f64,
    pub entropy_bits: f64,
}

/// Verification result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationResult {
    pub passed: bool,
    pub confidence: f64,
    pub entropy_score: f64,
    pub emulation_probability: f64,
    pub details: HashMap<String, String>,
}

/// Deep entropy verifier
pub struct DeepEntropyVerifier {
    /// Baseline measurements for known hardware
    baselines: HashMap<String, HardwareBaseline>,
    /// Challenge history
    challenges: Vec<Challenge>,
}

#[derive(Debug, Clone)]
struct HardwareBaseline {
    cache_timing_mean: f64,
    cache_timing_std: f64,
    instruction_timing_mean: f64,
    instruction_timing_std: f64,
    thermal_entropy: f64,
}

impl DeepEntropyVerifier {
    pub fn new() -> Self {
        let mut verifier = DeepEntropyVerifier {
            baselines: HashMap::new(),
            challenges: Vec::new(),
        };
        verifier.initialize_baselines();
        verifier
    }

    fn initialize_baselines(&mut self) {
        // PowerPC G4 baseline
        self.baselines.insert("G4".to_string(), HardwareBaseline {
            cache_timing_mean: 2.5,
            cache_timing_std: 0.3,
            instruction_timing_mean: 1.2,
            instruction_timing_std: 0.15,
            thermal_entropy: 4.2,
        });

        // Intel 486 baseline
        self.baselines.insert("486".to_string(), HardwareBaseline {
            cache_timing_mean: 8.0,
            cache_timing_std: 1.2,
            instruction_timing_mean: 4.5,
            instruction_timing_std: 0.8,
            thermal_entropy: 3.8,
        });

        // Modern CPU baseline
        self.baselines.insert("Modern".to_string(), HardwareBaseline {
            cache_timing_mean: 0.5,
            cache_timing_std: 0.05,
            instruction_timing_mean: 0.3,
            instruction_timing_std: 0.02,
            thermal_entropy: 5.5,
        });
    }

    /// Generate a new entropy challenge
    pub fn generate_challenge(&mut self, challenge_type: ChallengeType) -> Challenge {
        use rand::Rng;
        let mut rng = rand::thread_rng();

        let mut seed = [0u8; 32];
        rng.fill(&mut seed[..]);

        let challenge = Challenge {
            seed,
            challenge_type,
            difficulty: 1000,
            issued_at: current_timestamp(),
        };

        self.challenges.push(challenge.clone());
        challenge
    }

    /// Verify an entropy proof
    pub fn verify(&self, proof: &EntropyProof, expected_hw: &str) -> VerificationResult {
        let mut details = HashMap::new();

        // Check if challenge is recent
        let age = current_timestamp() - proof.responded_at;
        if age > 300 {
            return VerificationResult {
                passed: false,
                confidence: 0.0,
                entropy_score: 0.0,
                emulation_probability: 1.0,
                details: {
                    details.insert("error".to_string(), "Challenge too old".to_string());
                    details
                },
            };
        }

        // Get baseline for expected hardware
        let baseline = match self.baselines.get(expected_hw) {
            Some(b) => b,
            None => {
                details.insert("error".to_string(), "Unknown hardware type".to_string());
                return VerificationResult {
                    passed: false,
                    confidence: 0.0,
                    entropy_score: 0.0,
                    emulation_probability: 1.0,
                    details,
                };
            }
        };

        // Verify statistical properties match baseline
        let timing_match = (proof.stats.mean - baseline.cache_timing_mean).abs() 
            < 3.0 * baseline.cache_timing_std;
        
        let variance_match = (proof.stats.std_dev - baseline.cache_timing_std).abs()
            < 2.0 * baseline.cache_timing_std;

        // Check entropy level (real hardware has high entropy)
        let entropy_valid = proof.stats.entropy_bits > 3.0;

        // Calculate emulation probability
        let emulation_prob = if !timing_match {
            0.8 // Timing mismatch suggests emulation
        } else if !variance_match {
            0.6 // Variance mismatch
        } else if !entropy_valid {
            0.7 // Low entropy
        } else {
            0.1 // Likely real hardware
        };

        let confidence = 1.0 - emulation_prob;
        let passed = confidence > 0.5 && entropy_valid;

        details.insert("timing_match".to_string(), timing_match.to_string());
        details.insert("variance_match".to_string(), variance_match.to_string());
        details.insert("entropy_valid".to_string(), entropy_valid.to_string());

        VerificationResult {
            passed,
            confidence,
            entropy_score: proof.stats.entropy_bits,
            emulation_probability: emulation_prob,
            details,
        }
    }

    /// Measure cache timing entropy (to be called by miner)
    pub fn measure_cache_timing(iterations: usize) -> EntropyProof {
        use rand::Rng;
        let mut rng = rand::thread_rng();
        
        let mut measurements = Vec::with_capacity(iterations);
        let mut data = vec![0u8; 1024];
        
        for _ in 0..iterations {
            // Fill with random data
            rng.fill(&mut data[..]);
            
            // Measure access time
            let start = Instant::now();
            let mut sum: u64 = 0;
            for &byte in &data {
                sum += byte as u64;
            }
            let elapsed = start.elapsed();
            
            measurements.push(elapsed.as_nanos() as f64);
        }

        let stats = calculate_stats(&measurements);
        
        // Generate hardware signature from timing pattern
        let hw_signature = generate_hw_signature(&measurements);

        let mut seed = [0u8; 32];
        rng.fill(&mut seed[..]);

        EntropyProof {
            challenge_seed: seed,
            measurements,
            stats,
            hw_signature,
            responded_at: current_timestamp(),
        }
    }
}

/// Calculate statistical properties
fn calculate_stats(measurements: &[f64]) -> EntropyStats {
    if measurements.is_empty() {
        return EntropyStats {
            mean: 0.0,
            std_dev: 0.0,
            min: 0.0,
            max: 0.0,
            entropy_bits: 0.0,
        };
    }

    let mean = measurements.iter().sum::<f64>() / measurements.len() as f64;
    
    let variance = measurements.iter()
        .map(|x| (x - mean).powi(2))
        .sum::<f64>() / measurements.len() as f64;
    
    let std_dev = variance.sqrt();
    
    let min = measurements.iter().cloned().fold(f64::INFINITY, f64::min);
    let max = measurements.iter().cloned().fold(f64::NEG_INFINITY, f64::max);

    // Calculate Shannon entropy of timing distribution
    let entropy_bits = calculate_shannon_entropy(measurements);

    EntropyStats {
        mean,
        std_dev,
        min,
        max,
        entropy_bits,
    }
}

/// Calculate Shannon entropy of measurement distribution
fn calculate_shannon_entropy(measurements: &[f64]) -> f64 {
    use std::collections::BTreeMap;
    
    if measurements.is_empty() {
        return 0.0;
    }

    // Bin the measurements - use explicit comparison for f64
    let mut bins = BTreeMap::new();
    let min_val = measurements.iter().cloned().fold(f64::INFINITY, f64::min);
    let max_val = measurements.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let bin_size = ((max_val - min_val) / 10.0).max(0.001);
    
    for &m in measurements {
        let bin = ((m - min_val) / bin_size) as i64;
        *bins.entry(bin).or_insert(0) += 1;
    }

    // Calculate entropy
    let total = measurements.len() as f64;
    let mut entropy = 0.0;
    
    for &count in bins.values() {
        let p = count as f64 / total;
        if p > 0.0 {
            entropy -= p * p.log2();
        }
    }

    entropy
}

/// Generate hardware signature from timing pattern
fn generate_hw_signature(measurements: &[f64]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    
    for &m in measurements {
        hasher.update(&m.to_le_bytes());
    }
    
    hasher.finalize().into()
}

/// Helper to get current timestamp
fn current_timestamp() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or(Duration::ZERO)
        .as_secs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_entropy_measurement() {
        let proof = DeepEntropyVerifier::measure_cache_timing(100);
        
        assert!(!proof.measurements.is_empty());
        assert!(proof.stats.mean > 0.0);
        assert!(proof.stats.std_dev > 0.0);
        assert!(proof.stats.entropy_bits > 0.0);
    }

    #[test]
    fn test_challenge_generation() {
        let mut verifier = DeepEntropyVerifier::new();
        let challenge = verifier.generate_challenge(ChallengeType::CacheTiming);
        
        assert_ne!(challenge.seed, [0u8; 32]);
        assert_eq!(challenge.challenge_type, ChallengeType::CacheTiming);
    }

    #[test]
    fn test_verification() {
        let verifier = DeepEntropyVerifier::new();
        let proof = DeepEntropyVerifier::measure_cache_timing(100);
        
        let result = verifier.verify(&proof, "Modern");
        
        // Should pass for modern hardware with valid measurements
        assert!(result.passed || result.confidence > 0.3);
    }

    #[test]
    fn test_stats_calculation() {
        let measurements = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let stats = calculate_stats(&measurements);
        
        assert!((stats.mean - 3.0).abs() < 0.001);
        assert!(stats.std_dev > 0.0);
        assert!((stats.min - 1.0).abs() < 0.001);
        assert!((stats.max - 5.0).abs() < 0.001);
    }
}
