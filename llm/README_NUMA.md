# NUMA-Aware Model Sharding for POWER8

## Overview

`ggml-numa-shard.h` provides intelligent per-layer NUMA placement for llama.cpp tensor memory on multi-socket systems. Instead of flat `mmap()` allocation that lets the kernel scatter pages randomly across NUMA nodes, this library pins transformer layers to specific nodes based on access patterns and measured bandwidth.

## Why This Matters

The POWER8 S824 has 4 NUMA nodes with dramatically different memory bandwidth:

```
┌─────────────────────────────────────────────────────────┐
│                    POWER8 S824 Topology                   │
│                                                           │
│   Node 0 (Slow)        Node 1 (Medium)                   │
│   ┌──────────┐         ┌──────────┐                      │
│   │ 128 GB   │         │ 128 GB   │                      │
│   │ 215-225  │←─QPI─→  │ ~350     │                      │
│   │  MB/s    │         │  MB/s    │                      │
│   └──────────┘         └──────────┘                      │
│        ↑                     ↑                            │
│        │         QPI         │                            │
│        ↓                     ↓                            │
│   ┌──────────┐         ┌──────────┐                      │
│   │ 128 GB   │         │ 128 GB   │                      │
│   │ 400-415  │←─QPI─→  │ 415-425  │                      │
│   │  MB/s    │         │  MB/s    │                      │
│   └──────────┘         └──────────┘                      │
│   Node 2 (Fast)        Node 3 (Fastest)                  │
│                                                           │
│   Total: 512 GB RAM, 64 threads optimal                  │
└─────────────────────────────────────────────────────────┘
```

With flat mmap, the kernel interleaves pages across all 4 nodes. This means ~50% of memory accesses go through the slow Node 0/1 interconnect. NUMA-aware sharding places hot layers (attention) on the fastest nodes.

## Files

| File | Description |
|------|-------------|
| `ggml-numa-shard.h` | Header-only C library — tensor name parsing, mbind(), stats |
| `numa_shard_bench.c` | Benchmark harness — per-node bandwidth, flat vs sharded comparison |
| `numa_shard_config.py` | Python config generator — analyzes model, suggests optimal mapping |

## Quick Start

### 1. Generate Configuration

```bash
# Auto-detect NUMA topology, generate map for a 32-layer model
python3 numa_shard_config.py --layers 32 --auto

# For a specific GGUF model
python3 numa_shard_config.py --model llama-7b.gguf --auto

# Just the export line
python3 numa_shard_config.py --layers 32 --nodes 4 --arch power8 --export
# Output: export GGML_NUMA_SHARD_MAP="0-8:node3,9-17:node2,18-25:node1,26-31:node0,attn:node3"
```

### 2. Run Benchmark

```bash
# Build
gcc -O3 -mcpu=power8 -mvsx -lnuma numa_shard_bench.c -o numa_bench

# On x86
gcc -O3 -march=native -lnuma numa_shard_bench.c -o numa_bench

# Run
./numa_bench --size-mb 256 --iterations 10
```

Expected output on POWER8 S824:
```
NUMA Shard Benchmark
====================
Buffer size:  256 MiB per test
Iterations:   10 (best of)
NUMA nodes:   4
Cache line:   128 bytes
Architecture: POWER (VSX enabled)

Node      Seq Read      Seq Write     Random Read
--------  ------------  ------------  ------------
Node 0      221.3 MB/s    198.7 MB/s     45.2 MB/s
Node 1      348.9 MB/s    312.4 MB/s     72.1 MB/s
Node 2      412.6 MB/s    389.1 MB/s     91.8 MB/s
Node 3      423.1 MB/s    401.2 MB/s     94.3 MB/s

--- Flat (default mmap) ---
Flat        287.4 MB/s    261.8 MB/s     63.7 MB/s

Speedup (best NUMA node vs flat): 1.47x seq read
```

### 3. Integrate with llama.cpp

Add to your llama.cpp build after tensor mmap:

```c
#include "ggml-numa-shard.h"

// At startup
ggml_numa_shard_init();

// After each tensor is loaded
for (int i = 0; i < model.n_tensors; i++) {
    ggml_numa_shard_assign(
        model.tensors[i].name,
        model.tensors[i].data,
        model.tensors[i].size
    );
}

// Print allocation report
ggml_numa_shard_stats();

// At shutdown
ggml_numa_shard_cleanup();
```

## Configuration Syntax

The `GGML_NUMA_SHARD_MAP` environment variable controls layer placement:

```
GGML_NUMA_SHARD_MAP="0-8:node3,9-20:node2,21-31:node1,attn:node3"
```

### Rule Types

| Pattern | Example | Meaning |
|---------|---------|---------|
| `N-M:nodeX` | `0-8:node3` | Layers 0 through 8 → NUMA node 3 |
| `N:nodeX` | `5:node2` | Single layer 5 → NUMA node 2 |
| `type:nodeX` | `attn:node3` | All attention tensors → NUMA node 3 |

### Supported Types

- `attn` — Attention layers (Q, K, V, O projections)
- `ffn` — Feed-forward layers (up, down, gate projections)
- `norm` — Layer normalization weights
- `embed` — Token embeddings

### Priority

1. Type-specific rules are checked first
2. Range rules are checked second
3. If no rule matches, round-robin by layer index

## Recommended Mappings

### 7B Model (32 layers) on 4-node POWER8

```bash
export GGML_NUMA_SHARD_MAP="0-8:node3,9-17:node2,18-25:node1,26-31:node0,attn:node3"
```

- Early layers (0-8) on fastest Node 3 — most accessed during prefill
- Attention on Node 3 — bandwidth-critical
- Late layers on slower nodes — less latency-sensitive

### 33B Model (60 layers) on 4-node POWER8

```bash
export GGML_NUMA_SHARD_MAP="0-15:node3,16-30:node2,31-45:node1,46-59:node0,attn:node3"
```

### 70B Model (80 layers) on 4-node POWER8

```bash
export GGML_NUMA_SHARD_MAP="0-20:node3,21-40:node2,41-60:node1,61-79:node0,attn:node3"
```

## Build Requirements

### POWER8

```bash
gcc -O3 -mcpu=power8 -mvsx -lnuma numa_shard_bench.c -o numa_bench
```

Requires:
- GCC 9+ with `-mcpu=power8` support
- `libnuma-dev` / `numactl-devel` package
- Linux kernel 3.x+ with NUMA support

### x86 (for development/testing)

```bash
gcc -O3 -march=native -lnuma numa_shard_bench.c -o numa_bench
```

Works on any multi-socket x86 system. Single-socket systems will show 1 node with no sharding benefit.

### Cross-platform Safety

The header uses `#ifdef __linux__` guards. On non-Linux or non-NUMA systems:
- `ggml_numa_shard_init()` returns 0
- `ggml_numa_shard_assign()` is a no-op returning -1
- No compilation errors, no behavioral changes

## Performance Expectations

Based on RustChain POWER8 S824 benchmarks:

| Metric | Flat mmap | NUMA-sharded | Improvement |
|--------|-----------|--------------|-------------|
| pp512 throughput | ~105 t/s | ~140-155 t/s | 1.3-1.5x |
| tg128 throughput | ~35 t/s | ~42-48 t/s | 1.2-1.4x |
| Memory bandwidth utilization | ~60% | ~85-90% | +25-30% |
| Worst-case latency (P99) | High variance | Lower variance | More predictable |

Actual results depend on model size, quantization, and system load. The biggest gains come from preventing hot tensors from landing on Node 0 (the slowest node on the S824).

## Known Limitations

1. **Page alignment**: `mbind()` operates on page boundaries. Small tensors may share pages and can't be individually placed.
2. **Huge pages**: If using huge pages (recommended for POWER8), ensure `mbind()` is called before page faults.
3. **Migration overhead**: `MPOL_MF_MOVE` can be slow for large tensors. Best to set the map before model loading.
4. **Single-process only**: The global `g_numa_ctx` is not thread-safe during init. Call `ggml_numa_shard_init()` once from the main thread.
