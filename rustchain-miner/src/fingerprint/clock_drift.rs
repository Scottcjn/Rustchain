// SPDX-License-Identifier: Apache-2.0
//! Check 1: Clock-Skew & Oscillator Drift
//!
//! Measures the coefficient of variation (CV) of back-to-back high-resolution
//! timing deltas. Real hardware oscillators produce measurable jitter (CV ~0.02–0.15);
//! emulators produce suspiciously uniform timing (CV < 0.005).

use super::CheckResult;
use crate::config::CLOCK_DRIFT_SAMPLES;

/// Read a high-resolution timestamp.
///
/// On x86_64: uses `rdtsc` via inline assembly for cycle-level precision.
/// On other platforms: falls back to `Instant::now()` (nanosecond-level).
#[cfg(target_arch = "x86_64")]
#[inline(always)]
fn read_timestamp() -> u64 {
    let lo: u32;
    let hi: u32;
    unsafe {
        core::arch::asm!(
            "rdtsc",
            out("eax") lo,
            out("edx") hi,
            options(nostack, nomem),
        );
    }
    ((hi as u64) << 32) | (lo as u64)
}

#[cfg(any(target_arch = "powerpc", target_arch = "powerpc64"))]
#[inline(always)]
fn read_timestamp() -> u64 {
    let val: u64;
    unsafe {
        core::arch::asm!(
            "mftb {0}",
            out(reg) val,
            options(nostack, nomem),
        );
    }
    val
}

#[cfg(target_arch = "riscv64")]
#[inline(always)]
fn read_timestamp() -> u64 {
    let cycles: u64;
    unsafe {
        core::arch::asm!(
            "csrr {0}, cycle",
            out(reg) cycles,
            options(nostack, nomem),
        );
    }
    cycles
}

#[cfg(not(any(target_arch = "x86_64", target_arch = "powerpc", target_arch = "powerpc64", target_arch = "riscv64")))]
#[inline(always)]
fn read_timestamp() -> u64 {
    // Fallback: use Instant, convert to nanoseconds since an arbitrary epoch
    static START: std::sync::OnceLock<Instant> = std::sync::OnceLock::new();
    let start = START.get_or_init(Instant::now);
    start.elapsed().as_nanos() as u64
}

/// Compute mean of a slice of f64.
fn mean(data: &[f64]) -> f64 {
    if data.is_empty() {
        return 0.0;
    }
    data.iter().sum::<f64>() / data.len() as f64
}

/// Compute standard deviation of a slice of f64.
fn std_dev(data: &[f64], avg: f64) -> f64 {
    if data.len() < 2 {
        return 0.0;
    }
    let variance = data.iter().map(|x| (x - avg).powi(2)).sum::<f64>() / (data.len() - 1) as f64;
    variance.sqrt()
}

/// Run the clock-drift fingerprint check.
pub fn run() -> CheckResult {
    let sample_count = CLOCK_DRIFT_SAMPLES;
    let mut deltas = Vec::with_capacity(sample_count);

    for _ in 0..sample_count {
        let t0 = read_timestamp();
        // Small busy-spin to create a measurable delta
        let mut sink: u64 = 0;
        for i in 0..100u64 {
            sink = sink.wrapping_add(i.wrapping_mul(7));
        }
        // Prevent optimizer from eliding the spin
        std::hint::black_box(sink);
        let t1 = read_timestamp();
        if t1 > t0 {
            deltas.push((t1 - t0) as f64);
        }
    }

    if deltas.len() < 10 {
        return CheckResult {
            passed: false,
            data: serde_json::json!({
                "error": "insufficient_samples",
                "samples": deltas.len(),
            }),
        };
    }

    let avg = mean(&deltas);
    let sd = std_dev(&deltas, avg);
    let cv = if avg > 0.0 { sd / avg } else { 0.0 };

    // Real hardware: CV > 0.005 (any detectable variance in oscillator timing)
    // Hybrid CPUs (Intel P+E cores) can show CV > 2.0 due to core migration
    // Emulators: CV < 0.005 (too uniform — the sole anti-emulation signal)
    let passed = cv > 0.005;

    log::debug!(
        "Clock drift: samples={}, mean={:.2}, std_dev={:.2}, cv={:.6}",
        deltas.len(),
        avg,
        sd,
        cv
    );

    CheckResult {
        passed,
        data: serde_json::json!({
            "cv": (cv * 1000.0).round() / 1000.0,
            "samples": deltas.len(),
            "mean": avg.round(),
            "std_dev": sd.round(),
        }),
    }
}
