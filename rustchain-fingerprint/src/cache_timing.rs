// Check 2: Cache Timing Fingerprint
// ===================================
// Measures latency harmonics across L1, L2, L3 cache levels.
// Real hardware has distinct cache hierarchy; emulators often flatten this.

use crate::CheckResult;
use serde_json::json;
use std::time::Instant;

/// Cache sizes to test (in bytes)
const L1_SIZE: usize = 8 * 1024;      // 8KB
const L2_SIZE: usize = 128 * 1024;    // 128KB
const L3_SIZE: usize = 4 * 1024 * 1024; // 4MB
/// Iterations per measurement
const ITERATIONS: usize = 100;
/// Accesses per iteration
const ACCESSES: usize = 1000;

pub struct CacheTimingCheck;

impl CacheTimingCheck {
    pub fn run() -> CheckResult {
        // Measure access times for each cache level
        let l1_times: Vec<f64> = (0..ITERATIONS)
            .map(|_| measure_access_time(L1_SIZE, ACCESSES))
            .collect();
        let l2_times: Vec<f64> = (0..ITERATIONS)
            .map(|_| measure_access_time(L2_SIZE, ACCESSES))
            .collect();
        let l3_times: Vec<f64> = (0..ITERATIONS)
            .map(|_| measure_access_time(L3_SIZE, ACCESSES))
            .collect();

        let l1_avg = mean_f64(&l1_times);
        let l2_avg = mean_f64(&l2_times);
        let l3_avg = mean_f64(&l3_times);

        // Calculate ratios between cache levels
        let l2_l1_ratio = if l1_avg > 0.0 { l2_avg / l1_avg } else { 0.0 };
        let l3_l2_ratio = if l2_avg > 0.0 { l3_avg / l2_avg } else { 0.0 };

        let data = json!({
            "l1_ns": (l1_avg * 1_000_000.0).round() / 1_000_000.0,
            "l2_ns": (l2_avg * 1_000_000.0).round() / 1_000_000.0,
            "l3_ns": (l3_avg * 1_000_000.0).round() / 1_000_000.0,
            "l2_l1_ratio": (l2_l1_ratio * 1_000.0).round() / 1_000.0,
            "l3_l2_ratio": (l3_l2_ratio * 1_000.0).round() / 1_000.0,
        });

        // Validation: real hardware should show cache hierarchy
        let mut passed = true;
        let mut fail_reason = None;

        // Ratios should be > 1.0 (larger caches are slower)
        if l2_l1_ratio < 1.01 && l3_l2_ratio < 1.01 {
            passed = false;
            fail_reason = Some("no_cache_hierarchy".to_string());
        }

        // Latencies should not be zero
        if l1_avg == 0.0 || l2_avg == 0.0 || l3_avg == 0.0 {
            passed = false;
            fail_reason = Some("zero_latency".to_string());
        }

        CheckResult {
            name: "cache_timing".to_string(),
            passed,
            data,
            fail_reason,
        }
    }
}

/// Measure average access time for a buffer of given size
fn measure_access_time(buffer_size: usize, accesses: usize) -> f64 {
    // Allocate buffer
    let mut buf: Vec<u8> = vec![0u8; buffer_size];
    
    // Initialize buffer to ensure pages are allocated
    for i in (0..buffer_size).step_by(64) {
        buf[i] = (i % 256) as u8;
    }

    // Measure sequential access time
    let start = Instant::now();
    for i in 0..accesses {
        let idx = (i * 64) % buffer_size;
        let _ = buf[idx];
    }
    let elapsed = start.elapsed().as_secs_f64();

    elapsed / accesses as f64
}

/// Calculate mean of f64 values
fn mean_f64(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    values.iter().sum::<f64>() / values.len() as f64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cache_timing_check() {
        let result = CacheTimingCheck::run();
        assert_eq!(result.name, "cache_timing");
        // Note: May fail in some VM environments
    }

    #[test]
    fn test_measure_access_time() {
        let time = measure_access_time(1024, 100);
        assert!(time > 0.0);
    }
}
