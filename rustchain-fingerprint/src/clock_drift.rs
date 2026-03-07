// Check 1: Clock Drift & Oscillator Skew
// =======================================
// Measures microscopic timing imperfections in the CPU oscillator.
// Real hardware exhibits natural variance; emulators often have synthetic timing.

use crate::CheckResult;
use serde_json::json;
use sha2::{Sha256, Digest};
use std::time::Instant;

/// Number of samples to collect
const SAMPLES: usize = 200;
/// Reference operations per sample
const REFERENCE_OPS: usize = 5000;
/// Sleep interval in milliseconds
const SLEEP_INTERVAL_MS: u64 = 1;

pub struct ClockDriftCheck;

impl ClockDriftCheck {
    pub fn run() -> CheckResult {
        let mut intervals: Vec<u128> = Vec::with_capacity(SAMPLES);

        for i in 0..SAMPLES {
            let data = format!("drift_{}", i);
            let start = Instant::now();
            
            for _ in 0..REFERENCE_OPS {
                let mut hasher = Sha256::new();
                hasher.update(data.as_bytes());
                let _ = hasher.finalize();
            }
            
            let elapsed = start.elapsed().as_nanos();
            intervals.push(elapsed);

            // Small delay to capture oscillator drift
            if i % 50 == 0 {
                std::thread::sleep(std::time::Duration::from_millis(SLEEP_INTERVAL_MS));
            }
        }

        // Calculate statistics
        let mean_ns = mean(&intervals);
        let stdev_ns = standard_deviation(&intervals);
        let cv = if mean_ns > 0.0 { stdev_ns / mean_ns } else { 0.0 };

        // Calculate drift between consecutive samples
        let drift_pairs: Vec<f64> = intervals.windows(2)
            .map(|w| (w[1] as f64 - w[0] as f64).abs())
            .collect();
        let drift_stdev = standard_deviation_f64(&drift_pairs);

        let data = json!({
            "mean_ns": mean_ns as u64,
            "stdev_ns": stdev_ns as u64,
            "cv": (cv * 1_000_000.0).round() / 1_000_000.0, // 6 decimal places
            "drift_stdev": drift_stdev as u64,
        });

        // Validation: real hardware should have some variance
        let mut passed = true;
        let mut fail_reason = None;

        // CV threshold: synthetic timing often has CV < 0.0001
        if cv < 0.0001 {
            passed = false;
            fail_reason = Some("synthetic_timing".to_string());
        }

        // Drift should not be zero
        if drift_stdev < 100.0 {
            passed = false;
            fail_reason = Some("no_drift".to_string());
        }

        CheckResult {
            name: "clock_drift".to_string(),
            passed,
            data,
            fail_reason,
        }
    }
}

/// Calculate mean of u128 values
fn mean(values: &[u128]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let sum: u128 = values.iter().sum();
    sum as f64 / values.len() as f64
}

/// Calculate standard deviation of u128 values
fn standard_deviation(values: &[u128]) -> f64 {
    if values.len() < 2 {
        return 0.0;
    }
    let mean_val = mean(values);
    let variance: f64 = values.iter()
        .map(|v| {
            let diff = *v as f64 - mean_val;
            diff * diff
        })
        .sum::<f64>() / (values.len() - 1) as f64;
    variance.sqrt()
}

/// Calculate standard deviation of f64 values
fn standard_deviation_f64(values: &[f64]) -> f64 {
    if values.len() < 2 {
        return 0.0;
    }
    let mean_val: f64 = values.iter().sum::<f64>() / values.len() as f64;
    let variance: f64 = values.iter()
        .map(|v| {
            let diff = v - mean_val;
            diff * diff
        })
        .sum::<f64>() / (values.len() - 1) as f64;
    variance.sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clock_drift_check() {
        let result = ClockDriftCheck::run();
        assert_eq!(result.name, "clock_drift");
        // Note: This may fail in VM environments, which is expected behavior
    }

    #[test]
    fn test_statistics() {
        let values = vec![100u128, 200, 300, 400, 500];
        let m = mean(&values);
        assert!((m - 300.0).abs() < 0.001);
        
        let sd = standard_deviation(&values);
        assert!(sd > 0.0);
    }
}
