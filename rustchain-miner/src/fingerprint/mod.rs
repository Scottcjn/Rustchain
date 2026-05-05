// SPDX-License-Identifier: Apache-2.0
pub mod clock_drift;
pub mod cache_timing;
pub mod simd_identity;
pub mod thermal_drift;
pub mod instruction_jitter;
pub mod anti_emulation;

use serde::Serialize;
use std::collections::HashMap;

/// Result of a single fingerprint check.
#[derive(Debug, Clone, Serialize)]
pub struct CheckResult {
    pub passed: bool,
    pub data: serde_json::Value,
}

/// Aggregate result of all 6 fingerprint checks.
#[derive(Debug, Clone, Serialize)]
pub struct FingerprintResult {
    pub all_passed: bool,
    pub checks: HashMap<String, CheckResult>,
}

/// Run all 6 RIP-PoA fingerprint checks and return the aggregate result.
pub fn run_all_checks() -> FingerprintResult {
    let mut checks = HashMap::new();

    log::info!("Running fingerprint check 1/6: Clock-Skew & Oscillator Drift");
    checks.insert("clock_drift".to_string(), clock_drift::run());

    log::info!("Running fingerprint check 2/6: Cache Timing Fingerprint");
    checks.insert("cache_timing".to_string(), cache_timing::run());

    log::info!("Running fingerprint check 3/6: SIMD Unit Identity");
    checks.insert("simd_identity".to_string(), simd_identity::run());

    log::info!("Running fingerprint check 4/6: Thermal Drift Entropy");
    checks.insert("thermal_drift".to_string(), thermal_drift::run());

    log::info!("Running fingerprint check 5/6: Instruction Path Jitter");
    checks.insert("instruction_jitter".to_string(), instruction_jitter::run());

    log::info!("Running fingerprint check 6/6: Anti-Emulation / VM Detection");
    checks.insert("anti_emulation".to_string(), anti_emulation::run());

    let all_passed = checks.values().all(|c| c.passed);

    FingerprintResult { all_passed, checks }
}
