# POWER8 vec_perm Benchmark Suite

Microbenchmark suite for comparing scalar permutation versus POWER8 Altivec `vec_perm` path.

## Run

```bash
cd benchmarks/power8_vecperm
./run_bench.sh
```

Optional:

```bash
ITERS=5000000 OUT_DIR=./results-5m ./run_bench.sh
```

## Output

JSON line files in `results/`:
- `scalar_or_host.json`
- `power8_vecperm.json` (on PowerPC64 with Altivec toolchain)

Fields:
- `iters`
- `scalar_ns`
- `vecperm_ns`
- `speedup`
- `altivec`

## Notes

- On non-PowerPC hosts, scalar benchmark still runs for CI/dev sanity.
- On POWER8 hosts, compile with `-maltivec -mvsx` to enable vec_perm path.
