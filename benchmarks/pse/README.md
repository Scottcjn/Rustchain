# POWER8 PSE Benchmark Suite

Benchmark suite for measuring llama.cpp inference performance on POWER8 S824 with PSE (Proto-Sentient Emergence) AltiVec optimizations.

**Target:** ppc64le, Ubuntu 20.04, POWER8 S824
**Bounty:** RustChain #35 (75 RTC)

## Quick Start

```bash
# Install Python dependencies
pip install -r requirements.txt

# System dependencies (Ubuntu 20.04 ppc64le)
sudo apt install linux-tools-$(uname -r) numactl jq bc

# Run benchmarks
chmod +x benchmark_pse.sh
./benchmark_pse.sh

# Analyze results
python3 analyze_results.py results/

# Generate NUMA topology visualization
python3 numa_topology.py results/
```

## Configuration

Override defaults via environment variables:

| Variable | Default | Description |
|---|---|---|
| `LLAMA_STOCK` | `/opt/llama.cpp/stock/llama-bench` | Stock llama.cpp binary |
| `LLAMA_PSE_MASS` | `/opt/llama.cpp/pse-mass/llama-bench` | PSE-MASS build binary |
| `LLAMA_PSE_COFFERS` | `/opt/llama.cpp/pse-coffers/llama-bench` | PSE+Coffers build binary |
| `MODEL_DIR` | `/opt/models` | Directory containing GGUF models |
| `RESULTS_DIR` | `./results` | Output directory |
| `WARMUP_RUNS` | `2` | Warmup iterations before measurement |
| `BENCH_RUNS` | `5` | Measurement iterations per config |

## What It Measures

### Throughput
- **Prompt processing (pp):** Tokens/sec at batch sizes 128, 512, 1024
- **Token generation (tg):** Tokens/sec at generation lengths 32, 128

### System Metrics
- **Cache hit rates:** L1 data cache and LLC via `perf stat`
- **NUMA bandwidth:** Per-node memory allocation via `numastat`

### PSE Markers
- **NOI (Number of Iterations):** Total vec_perm iteration cycles. Measures AltiVec SIMD utilization depth.
- **DR (Divergence Ratio):** KL divergence of PSE token probabilities vs stock. Values near 0.0 mean functionally equivalent output; values above 0.01 indicate meaningful behavioral divergence.
- **ACS (AltiVec Cycle Share):** Percentage of compute cycles in AltiVec vector units. Higher = more effective PSE vectorization.
- **MCI (Memory Coffer Index):** Number of active NUMA coffers used during inference. Higher values indicate PSE is distributing memory access across more NUMA nodes.

## Build Modes

| Mode | Description |
|---|---|
| **Stock** | Upstream llama.cpp, no PSE modifications |
| **PSE-MASS** | PSE with MASS (Mathematical Acceleration SubSystem) vectorization via AltiVec vec_perm |
| **PSE+Coffers** | PSE-MASS plus NUMA-aware coffer scheduling for multi-node memory distribution |

## Models

The suite auto-detects and benchmarks whichever of these are present in `MODEL_DIR`:

| Model | File | Size |
|---|---|---|
| TinyLlama 1.1B | `tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf` | ~0.6 GB |
| Qwen 14B | `qwen1.5-14b-chat-q4_k_m.gguf` | ~8.2 GB |
| DeepSeek 33B | `deepseek-coder-33b-instruct.Q4_K_M.gguf` | ~19 GB |

Missing models are skipped gracefully.

## Output Structure

```
results/
├── tinyllama_1.1b.json     # Per-model results
├── qwen_14b.json
├── deepseek_33b.json
├── numa_topology.json       # NUMA node layout snapshot
├── benchmark.log            # Full run log
├── progress.json            # Completion status
├── REPORT.md                # Generated markdown summary
├── charts/
│   ├── tinyllama_1.1b_throughput.png
│   ├── tinyllama_1.1b_cache.png
│   ├── tinyllama_1.1b_pse_markers.png
│   ├── qwen_14b_throughput.png
│   ├── ...
│   ├── speedup_heatmap.png
│   └── numa_topology.png
└── <model_name>/            # Raw per-run data
    ├── stock_pp128_run1.json
    ├── pse_mass_tg32_run1.json
    └── ...
```

## Interpreting Results

### Throughput Charts
Bar charts compare tokens/sec across all three build modes. Error bars show standard deviation across runs. The coefficient of variation (CV%) should stay below 5% for reproducible results.

### Speedup Heatmap
Color-coded grid showing speedup ratios vs stock. Green cells (>1.0x) indicate PSE improvement. Values are expected in the 1.2x-1.8x range for prompt processing and 1.1x-1.4x for generation.

### PSE Markers
- NOI should increase with model size (more vec_perm work on larger tensors)
- DR should stay below 0.01 for functionally equivalent output
- ACS in the 30-50% range indicates good AltiVec utilization
- MCI should match the number of active NUMA nodes in Coffers mode

### NUMA Topology
The topology chart shows per-node memory usage during inference. In Coffers mode, memory should be distributed more evenly across nodes compared to stock (which typically concentrates on node 0).

## Reproducibility

- Each measurement is the mean of 5 runs (configurable via `BENCH_RUNS`)
- 2 warmup runs precede measurement to stabilize caches
- CV% is reported for every metric; flag results with CV > 5%
- System should be idle during benchmarks (no competing workloads)
- Pin NUMA nodes with `numactl` for consistent placement
