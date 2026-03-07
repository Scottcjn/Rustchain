// Check 4: Thermal Drift Entropy
// ================================
// Measures performance changes as CPU heats up under load.
// Real silicon shows thermal drift; emulators often ignore this.

use crate::CheckResult;
use serde_json::json;
use sha2::{Sha256, Digest};
use std::time::Instant;

/// Number of samples per phase
const SAMPLES: usize = 50;
/// Warmup iterations
const WARMUP_ITERATIONS: usize = 100;
/// Work per iteration
const WORK_ITERATIONS: usize = 10000;

pub struct ThermalDriftCheck;

impl ThermalDriftCheck {
    pub fn run() -> CheckResult {
        // Phase 1: Cold measurements
        let cold_times: Vec<u128> = (0..SAMPLES)
            .map(|i| measure_work(&format!("cold_{}", i)))
            .collect();

        // Phase 2: Heat up the CPU
        for _ in 0..WARMUP_ITERATIONS {
            for _ in 0..WORK_ITERATIONS {
                let mut hasher = Sha256::new();
                hasher.update(b"warmup");
                let _ = hasher.finalize();
            }
        }

        // Phase 3: Hot measurements
        let hot_times: Vec<u128> = (0..SAMPLES)
            .map(|i| measure_work(&format!("hot_{}", i)))
            .collect();

        // Calculate statistics
        let cold_avg = mean_u128(&cold_times) as f64;
        let hot_avg = mean_u128(&hot_times) as f64;
        let cold_stdev = std_dev_u128(&cold_times) as f64;
        let hot_stdev = std_dev_u128(&hot_times) as f64;

        // Thermal drift ratio
        let drift_ratio = if cold_avg > 0.0 { hot_avg / cold_avg } else { 0.0 };

        let data = json!({
            "cold_avg_ns": cold_avg as u64,
            "hot_avg_ns": hot_avg as u64,
            "cold_stdev": cold_stdev as u64,
            "hot_stdev": hot_stdev as u64,
            "drift_ratio": (drift_ratio * 10_000.0).round() / 10_000.0,
        });

        // Validation: real hardware should show some thermal variance
        let mut passed = true;
        let mut fail_reason = None;

        // Both cold and hot should have some variance
        if cold_stdev < 100.0 && hot_stdev < 100.0 {
            passed = false;
            fail_reason = Some("no_thermal_variance".to_string());
        }

        // Drift ratio should be reasonable (not exactly 1.0)
        if (drift_ratio - 1.0).abs() < 0.0001 && cold_stdev < 1000.0 {
            passed = false;
            fail_reason = Some("synthetic_thermal".to_string());
        }

        CheckResult {
            name: "thermal_drift".to_string(),
            passed,
            data,
            fail_reason,
        }
    }
}

/// Measure time for hash work
fn measure_work(label: &str) -> u128 {
    let start = Instant::now();
    for i in 0..WORK_ITERATIONS {
        let data = format!("{}_{}", label, i);
        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        let _ = hasher.finalize();
    }
    start.elapsed().as_nanos()
}

/// Calculate mean of u128 values
fn mean_u128(values: &[u128]) -> u128 {
    if values.is_empty() {
        return 0;
    }
    values.iter().sum::<u128>() / values.len() as u128
}

/// Calculate standard deviation of u128 values
fn std_dev_u128(values: &[u128]) -> u128 {
    if values.len() < 2 {
        return 0;
    }
    let mean = mean_u128(values) as f64;
    let variance: f64 = values.iter()
        .map(|v| {
            let diff = *v as f64 - mean;
            diff * diff
        })
        .sum::<f64>() / (values.len() - 1) as f64;
    variance.sqrt() as u128
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_thermal_drift_check() {
        let result = ThermalDriftCheck::run();
        assert_eq!(result.name, "thermal_drift");
        // Note: May fail in VM environments with stable timing
    }

    #[test]
    fn test_measure_work() {
        let time = measure_work("test");
        assert!(time > 0);
    }
}
