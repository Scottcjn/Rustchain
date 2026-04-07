/// ppa_spoofer.rs — Proof-of-Antiquity channel spoofing implementation
///
/// Demonstrates that PPA fingerprint channels can be bypassed by generating
/// realistic fake hardware signatures that pass server-side validation.

use std::time::{Duration, Instant};
use sha2::{Digest, Sha256};
use rand::{Rng, thread_rng};
use std::collections::HashMap;

// ---------------------------------------------------------------------------
// Spoofer configuration
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct SpooferConfig {
    /// Spoof mode: bypass_vm, realistic_random, targeted_attack
    pub mode: SpoofMode,
    /// Target architecture to fake
    pub target_arch: String,
    /// Level of sophistication (1-10, 10=most realistic)
    pub realism: u8,
    /// Random seed for reproducible results
    pub seed: u64,
}

#[derive(Debug, Clone, PartialEq)]
pub enum SpoofMode {
    BypassVm,           // Focus on hiding VM indicators
    RealisticRandom,    // Generate realistic random data
    TargetedAttack,     // Target specific weaknesses
}

// ---------------------------------------------------------------------------
// Spoofed hardware fingerprint
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpoofedFingerprint {
    pub clock_drift_cv: f64,
    pub cache_timing: Vec<f64>,
    pub thermal_drift: f64,
    pub simd_identity: String,
    pub instruction_jitter: Vec<f64>,
    pub anti_emulation_score: f64,
    pub fleet_detection_hash: String,
}

// ---------------------------------------------------------------------------
// Channel spoofing implementations
// ---------------------------------------------------------------------------

/// Generate realistic clock drift that simulates old hardware
pub fn spoof_clock_drift(config: &SpooferConfig) -> f64 {
    match config.mode {
        SpoofMode::BypassVm => {
            // VM detection: too regular clock = bad, add subtle irregularity
            let base_cv = 0.02 + (config.realism as f64 * 0.005);
            let mut rng = thread_rng();
            let jitter: f64 = rng.gen_range(-0.01..0.01);
            (base_cv + jitter).max(0.001)
        }
        SpoofMode::RealisticRandom => {
            let mut rng = thread_rng();
            // Real old hardware: 0.05-0.30 CV range
            rng.gen_range(0.05..0.30)
        }
        SpoofMode::TargetedAttack => {
            // Target PPA sweet spot: high enough for antiquity, not too high
            0.15 + (config.realism as f64 * 0.01)
        }
    }
}

/// Generate cache timing that mimics real cache hierarchy
pub fn spoof_cache_timing(config: &SpooferConfig) -> Vec<f64> {
    match config.mode {
        SpoofMode::BypassVm => {
            // VMs often have unrealistic cache performance, add noise
            let base_times = vec![2.5, 8.5, 45.0, 120.0]; // L1, L2, L3, RAM
            let mut rng = thread_rng();
            base_times.iter().map(|&t| {
                let noise: f64 = rng.gen_range(-0.5..0.5);
                (t + noise).max(0.1)
            }).collect()
        }
        SpoofMode::RealisticRandom => {
            let mut rng = thread_rng();
            // Realistic cache timing for old hardware
            vec![
                rng.gen_range(1.0..5.0),   // L1: 1-5ns
                rng.gen_range(5.0..20.0),  // L2: 5-20ns  
                rng.gen_range(30.0..80.0), // L3: 30-80ns
                rng.gen_range(80.0..200.0), // RAM: 80-200ns
            ]
        }
        SpoofMode::TargetedAttack => {
            // Target specific CPU architecture patterns
            match config.target_arch.as_str() {
                "x86_64" => vec![2.1, 12.5, 55.3, 135.7],
                "aarch64" => vec![1.8, 10.2, 48.9, 128.4],
                "powerpc" => vec![3.2, 18.7, 67.2, 156.3],
                _ => vec![2.5, 15.0, 60.0, 150.0],
            }
        }
    }
}

/// Generate thermal drift that simulates temperature-dependent behavior
pub fn spoof_thermal_drift(config: &SpooferConfig) -> f64 {
    match config.mode {
        SpoofMode::BypassVm => {
            // VMs lack thermal effects, simulate subtle temperature cycling
            let base_drift = 0.01 + (config.realism as f64 * 0.002);
            let mut rng = thread_rng();
            base_drift + rng.gen_range(-0.005..0.005)
        }
        SpoofMode::RealisticRandom => {
            let mut rng = thread_rng();
            // Real thermal drift in old hardware
            rng.gen_range(0.005..0.025)
        }
        SpoofMode::TargetedAttack => {
            // Target PPA's thermal scoring sweet spot
            0.015 + (config.realism as f64 * 0.002)
        }
    }
}

/// Generate SIMD identity that matches target architecture
pub fn spoof_simd_identity(config: &SpooferConfig) -> String {
    let target_features = match config.target_arch.as_str() {
        "x86_64" => vec!["sse2", "sse4.2", "avx", "avx2"],
        "aarch64" => vec!["neon", "sve"],
        "powerpc" => vec!["altivec", "vsx"],
        _ => vec!["none"],
    };
    
    let features = if config.realism >= 7 {
        target_features.to_vec()
    } else {
        // Random subset to increase entropy
        let mut rng = thread_rng();
        target_features.into_iter()
            .filter(|_| rng.gen_bool(0.7))
            .collect()
    };
    
    // Build deterministic hash
    let joined = features.join(",");
    let hash = Sha256::digest(joined.as_bytes());
    format!("{:x}", &hash)[..16].to_string()
}

/// Generate instruction jitter that simulates pipeline behavior
pub fn spoof_instruction_jitter(config: &SpooferConfig) -> Vec<f64> {
    match config.mode {
        SpoofMode::BypassVm => {
            // VMs often have overly consistent instruction timing
            let base_jitter = vec![0.1, 0.15, 0.08, 0.12]; // 4 instruction types
            let mut rng = thread_rng();
            base_jitter.iter().map(|&j| {
                let noise: f64 = rng.gen_range(-0.02..0.02);
                (j + noise).max(0.01)
            }).collect()
        }
        SpoofMode::RealisticRandom => {
            let mut rng = thread_rng();
            (0..4).map(|_| rng.gen_range(0.05..0.25)).collect()
        }
        SpoofMode::TargetedAttack => {
            // Target specific instruction patterns for bypass
            vec![0.12, 0.18, 0.10, 0.14]
        }
    }
}

/// Generate anti-emulation score (lower = more likely to be VM)
pub fn spoof_anti_emulation_score(config: &SpooferConfig) -> f64 {
    match config.mode {
        SpoofMode::BypassVm => {
            // Actively hide VM indicators
            0.95 - (config.realism as f64 * 0.05) // High score = not VM-like
        }
        SpoofMode::RealisticRandom => {
            let mut rng = thread_rng();
            rng.gen_range(0.3..0.8) // Mixed VM/hardware characteristics
        }
        SpoofMode::TargetedAttack => {
            // Target PPA's anti-emulation thresholds
            0.85 + (config.realism as f64 * 0.01)
        }
    }
}

/// Generate fleet detection hash (unique ROMs per instance)
pub fn spoof_fleet_detection_hash(config: &SpooferConfig) -> String {
    let mut hasher = Sha256::new();
    
    // Combine multiple sources for uniqueness
    hasher.update(config.seed.to_string().as_bytes());
    hasher.update(config.target_arch.as_bytes());
    hasher.update(&[config.realism]);
    hasher.update(config.mode.to_string().as_bytes());
    
    // Add some entropy based on current time
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    hasher.update(timestamp.to_string().as_bytes());
    
    format!("{:x}", hasher.finalize())[..16].to_string()
}

// ---------------------------------------------------------------------------
// Main spoofer interface
// ---------------------------------------------------------------------------

/// Generate a complete spoofed fingerprint
pub fn generate_spoofed_fingerprint(config: &SpooferConfig) -> SpoofedFingerprint {
    SpoofedFingerprint {
        clock_drift_cv: spoof_clock_drift(config),
        cache_timing: spoof_cache_timing(config),
        thermal_drift: spoof_thermal_drift(config),
        simd_identity: spoof_simd_identity(config),
        instruction_jitter: spoof_instruction_jitter(config),
        anti_emulation_score: spoof_anti_emulation_score(config),
        fleet_detection_hash: spoof_fleet_detection_hash(config),
    }
}

/// Validate that spoofed fingerprint passes basic sanity checks
pub fn validate_spoofed_fingerprint(fp: &SpoofedFingerprint) -> Result<(), String> {
    // Check for obviously fake values
    if fp.clock_drift_cv < 0.001 || fp.clock_drift_cv > 1.0 {
        return Err("Invalid clock drift coefficient".to_string());
    }
    
    if fp.cache_timing.len() != 4 || fp.cache_timing.iter().any(|&t| t < 0.1 || t > 1000.0) {
        return Err("Invalid cache timing values".to_string());
    }
    
    if fp.thermal_drift < 0.0 || fp.thermal_drift > 0.1 {
        return Err("Invalid thermal drift value".to_string());
    }
    
    if fp.instruction_jitter.len() != 4 || fp.instruction_jitter.iter().any(|&j| j < 0.01 || j > 1.0) {
        return Err("Invalid instruction jitter values".to_string());
    }
    
    if fp.anti_emulation_score < 0.0 || fp.anti_emulation_score > 1.0 {
        return Err("Invalid anti-emulation score".to_string());
    }
    
    if fp.fleet_detection_hash.len() != 16 {
        return Err("Invalid fleet detection hash length".to_string());
    }
    
    Ok(())
}

// ---------------------------------------------------------------------------
// Configuration helpers
// ---------------------------------------------------------------------------

impl SpooferConfig {
    pub fn default_bypass_vm() -> Self {
        Self {
            mode: SpoofMode::BypassVm,
            target_arch: "x86_64".to_string(),
            realism: 8,
            seed: rand::random(),
        }
    }
    
    pub fn realistic_random() -> Self {
        Self {
            mode: SpoofMode::RealisticRandom,
            target_arch: "x86_64".to_string(),
            realism: 5,
            seed: rand::random(),
        }
    }
    
    pub fn targeted_attack() -> Self {
        Self {
            mode: SpoofMode::TargetedAttack,
            target_arch: "x86_64".to_string(),
            realism: 9,
            seed: rand::random(),
        }
    }
}

impl SpoofMode {
    pub fn to_string(&self) -> String {
        match self {
            SpoofMode::BypassVm => "bypass_vm".to_string(),
            SpoofMode::RealisticRandom => "realistic_random".to_string(),
            SpoofMode::TargetedAttack => "targeted_attack".to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_bypass_vm_mode() {
        let config = SpooferConfig::default_bypass_vm();
        let fp = generate_spoofed_fingerprint(&config);
        
        assert!(validate_spoofed_fingerprint(&fp).is_ok());
        // Should have high anti-emulation score (not VM-like)
        assert!(fp.anti_emulation_score > 0.8);
    }
    
    #[test]
    fn test_realistic_random_mode() {
        let config = SpooferConfig::realistic_random();
        let fp = generate_spoofed_fingerprint(&config);
        
        assert!(validate_spoofed_fingerprint(&fp).is_ok());
        // Values should be in realistic ranges
        assert!(fp.clock_drift_cv > 0.05 && fp.clock_drift_cv < 0.30);
    }
    
    #[test]
    fn test_targeted_attack_mode() {
        let config = SpooferConfig::targeted_attack();
        let fp = generate_spoofed_fingerprint(&config);
        
        assert!(validate_spoofed_fingerprint(&fp).is_ok());
        // Should target specific sweet spots
        assert!(fp.clock_drift_cv > 0.14 && fp.clock_drift_cv < 0.16);
    }
}