// Fingerprint Benchmark Suite
// ==============================

use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use rustchain_fingerprint::{run_all_checks, ClockDriftCheck, CacheTimingCheck, 
    SIMDIdentityCheck, ThermalDriftCheck, InstructionJitterCheck, AntiEmulationCheck};

fn bench_clock_drift(c: &mut Criterion) {
    c.bench_function("clock_drift_check", |b| {
        b.iter(|| ClockDriftCheck::run());
    });
}

fn bench_cache_timing(c: &mut Criterion) {
    c.bench_function("cache_timing_check", |b| {
        b.iter(|| CacheTimingCheck::run());
    });
}

fn bench_simd_identity(c: &mut Criterion) {
    c.bench_function("simd_identity_check", |b| {
        b.iter(|| SIMDIdentityCheck::run());
    });
}

fn bench_thermal_drift(c: &mut Criterion) {
    c.bench_function("thermal_drift_check", |b| {
        b.iter(|| ThermalDriftCheck::run());
    });
}

fn bench_instruction_jitter(c: &mut Criterion) {
    c.bench_function("instruction_jitter_check", |b| {
        b.iter(|| InstructionJitterCheck::run());
    });
}

fn bench_anti_emulation(c: &mut Criterion) {
    c.bench_function("anti_emulation_check", |b| {
        b.iter(|| AntiEmulationCheck::run());
    });
}

fn bench_full_suite(c: &mut Criterion) {
    c.bench_function("full_fingerprint_suite", |b| {
        b.iter(|| run_all_checks());
    });
}

criterion_group!(
    benches,
    bench_clock_drift,
    bench_cache_timing,
    bench_simd_identity,
    bench_thermal_drift,
    bench_instruction_jitter,
    bench_anti_emulation,
    bench_full_suite,
);

criterion_main!(benches);
