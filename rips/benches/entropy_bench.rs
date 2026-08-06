use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn entropy_benchmark(c: &mut Criterion) {
    c.bench_function("entropy", |b| b.iter(|| {
        black_box(42u64)
    }));
}

criterion_group!(benches, entropy_benchmark);
criterion_main!(benches);