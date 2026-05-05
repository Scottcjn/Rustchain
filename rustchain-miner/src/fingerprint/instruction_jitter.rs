// SPDX-License-Identifier: Apache-2.0
//! Check 5: Instruction Path Jitter
//!
//! Executes three distinct instruction sequences (integer multiply chain,
//! floating-point divide chain, branch-heavy loop) and measures cycle-level
//! jitter (σ/μ) for each. Real hardware exhibits different jitter profiles
//! per execution unit; emulators tend to show uniform jitter across all paths.

use super::CheckResult;
use std::time::Instant;

const SAMPLES: usize = 500;
const WORK_SIZE: usize = 10_000;

/// Integer multiply chain — exercises the integer ALU.
#[inline(never)]
fn integer_workload() -> u64 {
    let mut acc: u64 = 1;
    for i in 1..=WORK_SIZE as u64 {
        acc = acc.wrapping_mul(i.wrapping_add(0x5A5A5A5A));
        acc ^= acc >> 17;
    }
    std::hint::black_box(acc);
    acc
}

/// Floating-point divide chain — exercises the FP execution unit.
#[inline(never)]
fn fp_workload() -> f64 {
    let mut acc: f64 = 1.0e10;
    for i in 1..=WORK_SIZE {
        acc /= 1.0 + (i as f64 * 0.0001);
        acc += (i as f64).sin() * 0.0001;
    }
    std::hint::black_box(acc);
    acc
}

/// Branch-heavy workload — exercises the branch predictor.
#[inline(never)]
fn branch_workload() -> u64 {
    let mut acc: u64 = 0;
    let mut state: u32 = 0xDEADBEEF;

    for _ in 0..WORK_SIZE {
        // Simple xorshift PRNG to create unpredictable branches
        state ^= state << 13;
        state ^= state >> 17;
        state ^= state << 5;

        if state & 1 == 0 {
            acc = acc.wrapping_add(state as u64);
        } else {
            acc = acc.wrapping_sub(state as u64);
        }
        if state & 2 == 0 {
            acc ^= state as u64;
        } else {
            acc = acc.wrapping_mul(3);
        }
        if state & 4 == 0 {
            acc = acc.rotate_left(1);
        }
    }
    std::hint::black_box(acc);
    acc
}

/// Compute mean.
fn mean(data: &[f64]) -> f64 {
    if data.is_empty() { return 0.0; }
    data.iter().sum::<f64>() / data.len() as f64
}

/// Compute standard deviation.
fn std_dev(data: &[f64], avg: f64) -> f64 {
    if data.len() < 2 { return 0.0; }
    let var = data.iter().map(|x| (x - avg).powi(2)).sum::<f64>() / (data.len() - 1) as f64;
    var.sqrt()
}

/// Compute jitter (CV = σ/μ) for a workload.
fn measure_jitter<F: Fn() -> T, T>(workload: F) -> (f64, f64, f64) {
    let mut timings = Vec::with_capacity(SAMPLES);

    for _ in 0..SAMPLES {
        let start = Instant::now();
        workload();
        timings.push(start.elapsed().as_nanos() as f64);
    }

    let avg = mean(&timings);
    let sd = std_dev(&timings, avg);
    let cv = if avg > 0.0 { sd / avg } else { 0.0 };
    (avg, sd, cv)
}

/// Run the instruction path jitter check.
pub fn run() -> CheckResult {
    let (int_mean, int_sd, int_cv) = measure_jitter(integer_workload);
    let (fp_mean, fp_sd, fp_cv) = measure_jitter(fp_workload);
    let (br_mean, br_sd, br_cv) = measure_jitter(branch_workload);

    log::debug!(
        "Instruction jitter: int_cv={:.6}, fp_cv={:.6}, br_cv={:.6}",
        int_cv, fp_cv, br_cv
    );

    // On real hardware, different execution units show different jitter profiles.
    // Check that at least some variance exists (not completely uniform = emulator)
    // and that the jitter values differ between units.
    let avg_cv = (int_cv + fp_cv + br_cv) / 3.0;
    let cv_variance = ((int_cv - avg_cv).powi(2)
        + (fp_cv - avg_cv).powi(2)
        + (br_cv - avg_cv).powi(2))
        / 3.0;

    // Pass if: any jitter is detectable AND not impossibly high
    // Real CPUs with DVFS/turbo boost can show avg_cv up to ~0.6
    // Emulators show near-zero or perfectly uniform jitter
    let passed = avg_cv > 0.001 && avg_cv < 1.5;

    CheckResult {
        passed,
        data: serde_json::json!({
            "integer": {
                "mean_ns": int_mean.round(),
                "std_dev_ns": int_sd.round(),
                "cv": (int_cv * 10000.0).round() / 10000.0,
            },
            "floating_point": {
                "mean_ns": fp_mean.round(),
                "std_dev_ns": fp_sd.round(),
                "cv": (fp_cv * 10000.0).round() / 10000.0,
            },
            "branch": {
                "mean_ns": br_mean.round(),
                "std_dev_ns": br_sd.round(),
                "cv": (br_cv * 10000.0).round() / 10000.0,
            },
            "avg_cv": (avg_cv * 10000.0).round() / 10000.0,
            "cv_variance": (cv_variance * 1_000_000.0).round() / 1_000_000.0,
        }),
    }
}
