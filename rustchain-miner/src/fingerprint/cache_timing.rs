// SPDX-License-Identifier: Apache-2.0
//! Check 2: Cache Timing Fingerprint
//!
//! Sweeps memory buffers of increasing size (spanning L1 → L2 → L3 cache boundaries)
//! and measures sequential access latency. Real CPUs show distinct latency steps at
//! cache boundary crossings; emulators tend to show flat latency.

use super::CheckResult;
use std::time::Instant;

/// Buffer sizes to sweep, from well-within-L1 to beyond-L3.
const BUFFER_SIZES: &[usize] = &[
    4 * 1024,       // 4 KB  — L1
    8 * 1024,       // 8 KB  — L1
    16 * 1024,      // 16 KB — L1
    32 * 1024,      // 32 KB — L1 boundary
    64 * 1024,      // 64 KB — L2
    128 * 1024,     // 128 KB — L2
    256 * 1024,     // 256 KB — L2 boundary
    512 * 1024,     // 512 KB — L2/L3
    1024 * 1024,    // 1 MB  — L3
    2 * 1024 * 1024,// 2 MB  — L3
    4 * 1024 * 1024,// 4 MB  — L3 boundary
    8 * 1024 * 1024,// 8 MB  — beyond L3
];

const CACHE_LINE_SIZE: usize = 64;
const ITERATIONS: usize = 4;

/// Measure the average nanoseconds per cache-line access for a buffer of `size` bytes.
fn measure_access_latency(size: usize) -> f64 {
    let mut buffer = vec![0u8; size];

    // Warm up: touch all cache lines
    for i in (0..size).step_by(CACHE_LINE_SIZE) {
        buffer[i] = 1;
    }

    let accesses = size / CACHE_LINE_SIZE;
    let mut total_ns = 0u128;

    for _ in 0..ITERATIONS {
        let start = Instant::now();
        let mut sum: u64 = 0;
        for i in (0..size).step_by(CACHE_LINE_SIZE) {
            // Use read_volatile to prevent the optimizer from eliding loads
            unsafe {
                sum = sum.wrapping_add(*std::ptr::addr_of!(buffer[i]) as u64);
            }
        }
        std::hint::black_box(sum);
        total_ns += start.elapsed().as_nanos();
    }

    let total_accesses = accesses * ITERATIONS;
    total_ns as f64 / total_accesses as f64
}

/// Run the cache timing fingerprint check.
pub fn run() -> CheckResult {
    let mut latencies: Vec<(usize, f64)> = Vec::new();

    for &size in BUFFER_SIZES {
        let ns_per_access = measure_access_latency(size);
        latencies.push((size, ns_per_access));
    }

    // Instead of comparing L1 vs L3 directly (fragile under system load),
    // measure the coefficient of variation (CV) across all buffer sizes.
    // Real hardware: latencies differ across cache tiers → CV > 0.05
    // Emulators: flat latency across all sizes → CV ≈ 0

    let all_lats: Vec<f64> = latencies.iter().map(|(_, lat)| *lat).collect();
    let mean = all_lats.iter().sum::<f64>() / all_lats.len() as f64;
    let variance = all_lats.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / all_lats.len() as f64;
    let std_dev = variance.sqrt();
    let cv = if mean > 0.0 { std_dev / mean } else { 0.0 };

    // Also compute the max/min spread ratio for reporting
    let min_lat = all_lats.iter().cloned().fold(f64::INFINITY, f64::min);
    let max_lat = all_lats.iter().cloned().fold(0.0f64, f64::max);
    let spread_ratio = if min_lat > 0.0 { max_lat / min_lat } else { 1.0 };

    // Real hardware with distinct cache tiers shows CV > 0.05
    // Emulators show CV < 0.02 (near-identical latency at all sizes)
    let passed = cv > 0.02 || spread_ratio > 1.1;

    log::debug!(
        "Cache timing: cv={:.4}, spread_ratio={:.2}, mean={:.2}ns",
        cv,
        spread_ratio,
        mean
    );

    // Build the data map with readable size labels
    let mut latency_map = serde_json::Map::new();
    for (size, lat) in &latencies {
        let label = if *size >= 1024 * 1024 {
            format!("{}MB", size / (1024 * 1024))
        } else {
            format!("{}KB", size / 1024)
        };
        latency_map.insert(label, serde_json::json!((lat * 100.0).round() / 100.0));
    }

    CheckResult {
        passed,
        data: serde_json::json!({
            "cv": (cv * 10000.0).round() / 10000.0,
            "spread_ratio": (spread_ratio * 100.0).round() / 100.0,
            "mean_ns": (mean * 100.0).round() / 100.0,
            "latencies": latency_map,
        }),
    }
}
