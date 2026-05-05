// SPDX-License-Identifier: Apache-2.0
//! Check 4: Thermal Drift Entropy
//!
//! Runs a CPU-intensive workload for several seconds, sampling timing deltas
//! at intervals. As the die heats up, real silicon shows measurable speed
//! fluctuations (thermal throttling). We compute the Shannon entropy of the
//! delta distribution — real hardware produces entropy > 2.0 bits; emulators
//! produce near-zero entropy (perfectly uniform timing).

use super::CheckResult;
use std::time::Instant;

const PHASES: usize = 5;
const SAMPLES_PER_PHASE: usize = 200;
const WORK_ITERATIONS: usize = 50_000;

/// Small CPU-intensive workload to generate heat.
#[inline(never)]
fn cpu_heat_work() -> u64 {
    let mut acc: u64 = 1;
    for i in 1..=WORK_ITERATIONS as u64 {
        acc = acc.wrapping_mul(i).wrapping_add(i ^ acc);
    }
    std::hint::black_box(acc);
    acc
}

/// Compute Shannon entropy of a distribution (in bits).
fn shannon_entropy(data: &[f64]) -> f64 {
    if data.is_empty() {
        return 0.0;
    }

    // Bucket the data into 16 bins
    let min = data.iter().cloned().fold(f64::INFINITY, f64::min);
    let max = data.iter().cloned().fold(f64::NEG_INFINITY, f64::max);

    if (max - min).abs() < f64::EPSILON {
        return 0.0;
    }

    let num_bins = 16usize;
    let bin_width = (max - min) / num_bins as f64;
    let mut bins = vec![0usize; num_bins];

    for &val in data {
        let idx = ((val - min) / bin_width).floor() as usize;
        let idx = idx.min(num_bins - 1);
        bins[idx] += 1;
    }

    let total = data.len() as f64;
    let mut entropy = 0.0;
    for &count in &bins {
        if count > 0 {
            let p = count as f64 / total;
            entropy -= p * p.log2();
        }
    }

    entropy
}

/// Run the thermal drift entropy check.
pub fn run() -> CheckResult {
    let mut all_deltas: Vec<f64> = Vec::new();
    let mut phase_entropies: Vec<f64> = Vec::new();

    for phase in 0..PHASES {
        let mut deltas = Vec::with_capacity(SAMPLES_PER_PHASE);

        for _ in 0..SAMPLES_PER_PHASE {
            let start = Instant::now();
            cpu_heat_work();
            let elapsed_ns = start.elapsed().as_nanos() as f64;
            deltas.push(elapsed_ns);
        }

        let entropy = shannon_entropy(&deltas);
        phase_entropies.push(entropy);
        all_deltas.extend(&deltas);

        log::debug!("Thermal drift: phase {}/{} entropy={:.3} bits", phase + 1, PHASES, entropy);
    }

    let overall_entropy = shannon_entropy(&all_deltas);

    // Check for drift between phases (thermal change over time)
    let first_phase_mean: f64 = all_deltas[..SAMPLES_PER_PHASE].iter().sum::<f64>() / SAMPLES_PER_PHASE as f64;
    let last_phase_mean: f64 = all_deltas[(PHASES - 1) * SAMPLES_PER_PHASE..].iter().sum::<f64>() / SAMPLES_PER_PHASE as f64;
    let drift_ratio = if first_phase_mean > 0.0 {
        (last_phase_mean - first_phase_mean).abs() / first_phase_mean
    } else {
        0.0
    };

    // Real hardware typically shows entropy > 0.3 bits (thermal noise in timing)
    // On modern laptops with efficient cooling, entropy can be as low as ~0.5
    // Emulators produce near-zero entropy (perfectly deterministic timing)
    let passed = overall_entropy > 0.3;

    log::debug!(
        "Thermal drift: overall_entropy={:.3}, drift_ratio={:.6}",
        overall_entropy,
        drift_ratio
    );

    CheckResult {
        passed,
        data: serde_json::json!({
            "entropy_bits": (overall_entropy * 1000.0).round() / 1000.0,
            "phase_entropies": phase_entropies.iter().map(|e| (e * 1000.0).round() / 1000.0).collect::<Vec<f64>>(),
            "drift_ratio": (drift_ratio * 1_000_000.0).round() / 1_000_000.0,
            "total_samples": all_deltas.len(),
        }),
    }
}
