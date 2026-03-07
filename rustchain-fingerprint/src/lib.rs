// RIP-PoA Hardware Fingerprint Suite
// ====================================
// High-tier continuation checks for bounty #734
// Implements 6 core fingerprint validations:
// 1. Clock Drift & Oscillator Skew
// 2. Cache Timing Fingerprint
// 3. SIMD Identity (architecture-specific)
// 4. Thermal Drift Entropy
// 5. Instruction Jitter
// 6. Anti-Emulation (VM/Cloud detection)

#![cfg_attr(not(test), warn(dead_code))]

pub mod clock_drift;
pub mod cache_timing;
pub mod simd_identity;
pub mod thermal_drift;
pub mod instruction_jitter;
pub mod anti_emulation;
pub mod device_oracle;

pub use clock_drift::ClockDriftCheck;
pub use cache_timing::CacheTimingCheck;
pub use simd_identity::SIMDIdentityCheck;
pub use thermal_drift::ThermalDriftCheck;
pub use instruction_jitter::InstructionJitterCheck;
pub use anti_emulation::AntiEmulationCheck;
pub use device_oracle::DeviceOracleCheck;

use serde::{Deserialize, Serialize};
use std::time::Duration;

/// Result of a single fingerprint check
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CheckResult {
    /// Name of the check
    pub name: String,
    /// Whether the check passed
    pub passed: bool,
    /// Detailed data from the check
    pub data: serde_json::Value,
    /// Failure reason if applicable
    pub fail_reason: Option<String>,
}

/// Complete fingerprint report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FingerprintReport {
    /// Overall pass/fail
    pub all_passed: bool,
    /// Number of checks passed
    pub checks_passed: usize,
    /// Total number of checks
    pub checks_total: usize,
    /// Individual check results
    pub results: Vec<CheckResult>,
    /// Timestamp of report generation
    pub timestamp: u64,
    /// Platform information
    pub platform: PlatformInfo,
}

/// Platform information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlatformInfo {
    /// Architecture (x86_64, aarch64, powerpc, etc.)
    pub architecture: String,
    /// Operating system
    pub os: String,
    /// CPU model string
    pub cpu_model: Option<String>,
    /// CPU family (if available)
    pub cpu_family: Option<u32>,
}

/// Run all fingerprint checks
pub fn run_all_checks() -> FingerprintReport {
    let platform = detect_platform();
    let mut results = Vec::new();
    let mut checks_passed = 0;

    // 1. Clock Drift
    let clock_result = ClockDriftCheck::run();
    if clock_result.passed {
        checks_passed += 1;
    }
    results.push(clock_result);

    // 2. Cache Timing
    let cache_result = CacheTimingCheck::run();
    if cache_result.passed {
        checks_passed += 1;
    }
    results.push(cache_result);

    // 3. SIMD Identity
    let simd_result = SIMDIdentityCheck::run();
    if simd_result.passed {
        checks_passed += 1;
    }
    results.push(simd_result);

    // 4. Thermal Drift
    let thermal_result = ThermalDriftCheck::run();
    if thermal_result.passed {
        checks_passed += 1;
    }
    results.push(thermal_result);

    // 5. Instruction Jitter
    let jitter_result = InstructionJitterCheck::run();
    if jitter_result.passed {
        checks_passed += 1;
    }
    results.push(jitter_result);

    // 6. Anti-Emulation
    let emulation_result = AntiEmulationCheck::run();
    if emulation_result.passed {
        checks_passed += 1;
    }
    results.push(emulation_result);

    // 7. Device Oracle (bonus check for age attestation)
    let oracle_result = DeviceOracleCheck::run();
    if oracle_result.passed {
        checks_passed += 1;
    }
    results.push(oracle_result);

    let checks_total = results.len();

    FingerprintReport {
        all_passed: checks_passed == checks_total,
        checks_passed,
        checks_total,
        results,
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or(Duration::ZERO)
            .as_secs(),
        platform,
    }
}

/// Detect platform information
fn detect_platform() -> PlatformInfo {
    let arch = std::env::consts::ARCH.to_string();
    let os = std::env::consts::OS.to_string();
    
    let (cpu_model, cpu_family) = device_oracle::detect_cpu_info();

    PlatformInfo {
        architecture: arch,
        os,
        cpu_model,
        cpu_family,
    }
}

/// Validate a fingerprint report against reference profiles
pub fn validate_against_profile(report: &FingerprintReport, profile: &str) -> bool {
    // Basic validation - all checks must pass
    if !report.all_passed {
        return false;
    }

    // Profile-specific validation
    match profile {
        "modern_x86" => {
            // Modern x86 should have SSE/AVX
            report.results.iter()
                .find(|r| r.name == "simd_identity")
                .map(|r| {
                    r.data.get("has_sse").and_then(|v| v.as_bool()).unwrap_or(false) ||
                    r.data.get("has_avx").and_then(|v| v.as_bool()).unwrap_or(false)
                })
                .unwrap_or(false)
        }
        "vintage_ppc" => {
            // Vintage PowerPC should have AltiVec
            report.results.iter()
                .find(|r| r.name == "simd_identity")
                .map(|r| {
                    r.data.get("has_altivec").and_then(|v| v.as_bool()).unwrap_or(false)
                })
                .unwrap_or(false)
        }
        "arm64" => {
            // ARM64 should have NEON
            report.results.iter()
                .find(|r| r.name == "simd_identity")
                .map(|r| {
                    r.data.get("has_neon").and_then(|v| v.as_bool()).unwrap_or(false)
                })
                .unwrap_or(false)
        }
        _ => true, // Unknown profile - just check all passed
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_run_all_checks() {
        let report = run_all_checks();
        assert!(report.checks_total >= 6);
        assert!(report.checks_passed <= report.checks_total);
    }

    #[test]
    fn test_platform_detection() {
        let platform = detect_platform();
        assert!(!platform.architecture.is_empty());
        assert!(!platform.os.is_empty());
    }
}
