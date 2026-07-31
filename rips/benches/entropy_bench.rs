use criterion::{criterion_group, criterion_main, Criterion};

fn bench_entropy(c: &mut Criterion) {
    c.bench_function("entropy", |b| {
        b.iter(|| 42u64.wrapping_mul(2654435761))
    });
}

criterion_group!(benches, bench_entropy);
criterion_main!(benches);
