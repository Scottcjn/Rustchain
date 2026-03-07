//! RustChain Deep Entropy Benchmarks
//!
//! Benchmarks for the deep entropy verification system

use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use rustchain::deep_entropy::{DeepEntropyVerifier, HardwareProfile, TimingStats};

fn criterion_benchmark(c: &mut Criterion) {
    let verifier = DeepEntropyVerifier::new();
    
    // Benchmark challenge generation
    c.bench_function("entropy_challenge_generation", |b| {
        b.iter(|| verifier.generate_challenge())
    });

    // Benchmark timing stats collection
    c.bench_function("timing_stats_collection", |b| {
        b.iter(|| {
            let mut stats = TimingStats::new();
            for i in 0..1000 {
                stats.add_sample(black_box(i as f64 * 0.1));
            }
            stats
        })
    });

    // Benchmark hardware profile lookup
    c.bench_function("hardware_profile_lookup", |b| {
        b.iter(|| {
            let profiles = rustchain::deep_entropy::get_hardware_profiles();
            profiles.get(black_box("486DX2"))
        })
    });

    // Benchmark emulation cost analysis
    c.bench_function("emulation_cost_analysis", |b| {
        b.iter(|| {
            rustchain::deep_entropy::emulation_cost_analysis(black_box("486DX2"))
        })
    });

    // Benchmark with different hardware types
    let mut group = c.benchmark_group("hardware_profiles");
    for hw_type in ["486DX2", "Pentium", "G4", "Alpha"] {
        group.bench_with_input(
            BenchmarkId::new("cost_analysis", hw_type),
            &hw_type,
            |b, &hw_type| {
                b.iter(|| rustchain::deep_entropy::emulation_cost_analysis(hw_type))
            },
        );
    }
    group.finish();
}

criterion_group!(benches, criterion_benchmark);
criterion_main!(benches);
