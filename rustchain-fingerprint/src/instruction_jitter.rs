// Check 5: Instruction Path Jitter
// ==================================
// Captures cycle-level jitter across different pipeline types (int, fp, branch, memory).
// Real hardware exhibits microarchitectural jitter; emulators tend to flatten this.

use crate::CheckResult;
use serde_json::json;
use std::time::Instant;

/// Number of samples per instruction type
const SAMPLES: usize = 100;
/// Operations per sample
const OPS: usize = 10000;

pub struct InstructionJitterCheck;

impl InstructionJitterCheck {
    pub fn run() -> CheckResult {
        // Measure integer pipeline jitter
        let int_times: Vec<u128> = (0..SAMPLES)
            .map(|_| measure_int_ops(OPS))
            .collect();

        // Measure floating-point pipeline jitter
        let fp_times: Vec<u128> = (0..SAMPLES)
            .map(|_| measure_fp_ops(OPS))
            .collect();

        // Measure branch prediction jitter
        let branch_times: Vec<u128> = (0..SAMPLES)
            .map(|_| measure_branch_ops(OPS))
            .collect();

        // Calculate statistics
        let int_avg = mean_u128(&int_times);
        let fp_avg = mean_u128(&fp_times);
        let branch_avg = mean_u128(&branch_times);

        let int_stdev = std_dev_u128(&int_times);
        let fp_stdev = std_dev_u128(&fp_times);
        let branch_stdev = std_dev_u128(&branch_times);

        let data = json!({
            "int_avg_ns": int_avg,
            "fp_avg_ns": fp_avg,
            "branch_avg_ns": branch_avg,
            "int_stdev": int_stdev,
            "fp_stdev": fp_stdev,
            "branch_stdev": branch_stdev,
        });

        // Validation: real hardware should have jitter variance
        let mut passed = true;
        let mut fail_reason = None;

        // At least one pipeline should show variance
        if int_stdev < 100 && fp_stdev < 100 && branch_stdev < 100 {
            passed = false;
            fail_reason = Some("no_jitter".to_string());
        }

        CheckResult {
            name: "instruction_jitter".to_string(),
            passed,
            data,
            fail_reason,
        }
    }
}

/// Measure integer operations timing
fn measure_int_ops(count: usize) -> u128 {
    let start = Instant::now();
    let mut x: u64 = 1;
    for _i in 0..count {
        x = x.wrapping_mul(7).wrapping_add(13) % 65537;
        // Prevent optimization
        std::hint::black_box(x);
    }
    start.elapsed().as_nanos()
}

/// Measure floating-point operations timing
fn measure_fp_ops(count: usize) -> u128 {
    let start = Instant::now();
    let mut x: f64 = 1.5;
    for _i in 0..count {
        x = (x * 1.414 + 0.5) % 1000.0;
        std::hint::black_box(x);
    }
    start.elapsed().as_nanos()
}

/// Measure branch prediction timing
fn measure_branch_ops(count: usize) -> u128 {
    let start = Instant::now();
    let mut x: i64 = 0;
    for i in 0..count {
        if i % 2 == 0 {
            x += 1;
        } else {
            x -= 1;
        }
        std::hint::black_box(x);
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
    fn test_instruction_jitter_check() {
        let result = InstructionJitterCheck::run();
        assert_eq!(result.name, "instruction_jitter");
        // Note: May fail in VM environments with deterministic scheduling
    }

    #[test]
    fn test_measure_int_ops() {
        let time = measure_int_ops(1000);
        assert!(time > 0);
    }

    #[test]
    fn test_measure_fp_ops() {
        let time = measure_fp_ops(1000);
        assert!(time > 0);
    }

    #[test]
    fn test_measure_branch_ops() {
        let time = measure_branch_ops(1000);
        assert!(time > 0);
    }
}
