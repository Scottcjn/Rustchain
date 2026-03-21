# NUMA-Aware Model Sharding for POWER8 llama.cpp

**Bounty #2277** — 250 RTC

Intelligent per-layer NUMA placement for IBM POWER8 S824 (4 NUMA nodes, 512GB RAM).

## Overview

This implementation provides NUMA-aware layer sharding for llama.cpp models, automatically placing transformer layers on optimal NUMA nodes based on memory bandwidth characteristics.

### Key Features

- **GGUF Tensor Metadata Parsing**: Automatically identifies layer types from tensor names
- **NUMA-Aware Memory Pinning**: Uses `mbind()`/`move_pages()` to pin tensor memory
- **Configurable via Environment Variable**: `GGML_NUMA_SHARD_MAP`
- **POWER8 Optimized Defaults**: Pre-tuned for S824's asymmetric memory bandwidth
- **Cross-Platform Safe**: x86 builds with `#ifdef __powerpc__` guards

## Quick Start

```bash
# Build for POWER8
make

# Build benchmark harness
make benchmark

# Detect NUMA topology
make detect
./detect

# Run benchmark (with NUMA sharding)
GGML_NUMA_SHARD_MAP="0-7:node0,8-15:node1,16-23:node2,attn:node3" \
./benchmark -m models/tinyllama-1.1b.gguf -t pp512 -s
```

## Architecture

### IBM POWER8 S824 NUMA Topology

```
Node 0 ←→ Node 1  (distance: 40, ~215-225 MB/s)
Node 2 ←→ Node 3  (distance: 40, ~400-425 MB/s)
Node 0 ↔ Node 2   (distance: 80, cross-controller)
Node 1 ↔ Node 3   (distance: 80, cross-controller)
```

### Default Layer Placement

| Layer Range | Type | NUMA Node | Rationale |
|-------------|------|-----------|-----------|
| 0-7 | Embeddings | Node 0 | Sequential access, lower BW needs |
| 8-15 | Transformer | Node 1 | Mid-range layers |
| 16-23 | Transformer | Node 2 | FFN-heavy, high BW available |
| 24-31 | Transformer | Node 3 | Attention-heavy, highest BW |
| attn.* | Attention | Node 3 | Random access, high BW |
| ffn.* | FFN | Node 2 | Compute-heavy, high BW |

## API Reference

### `numa_init_sharding()`

Initialize NUMA sharding from environment. Call before model loading.

```c
#include "ggml-numa-shard.h"

if (numa_init_sharding() == 0) {
    printf("NUMA sharding enabled\n");
}
```

### `numa_parse_gguf()`

Parse GGUF file and extract tensor metadata.

```c
ggml_numa_tensor_t tensors[1024];
int count = numa_parse_gguf("model.gguf", tensors, 1024);
```

### `numa_assign_layers()`

Assign tensors to NUMA nodes based on policy.

```c
numa_assign_layers(tensors, count, NULL);  // Use default policy
```

### `numa_pin_tensor()`

Pin a tensor to a specific NUMA node.

```c
void *tensor_data = numa_alloc_onnode(size, node);
numa_pin_tensor(tensor_data, size, node);
```

## Environment Variable

### `GGML_NUMA_SHARD_MAP`

Format: `"range:node,type:node,..."`

```bash
# Use default POWER8 placement
export GGML_NUMA_SHARD_MAP="0-7:node0,8-15:node1,16-23:node2,attn:node3,ffn:node2"

# Custom placement
export GGML_NUMA_SHARD_MAP="0-15:node0,attn:node3,ffn:node2"

# Auto-detect optimal placement
./numa_detect  # Check output for recommended settings
```

### Format Details

- `L-R:nodeN` — Range mapping (layers L through R to node N)
- `attn:nodeN` — All attention tensors to node N
- `ffn:nodeN` — All FFN tensors to node N
- `blk:nodeN` — All transformer blocks to node N

## Benchmark Methodology

### Test Types

- **pp512**: Prefill with 512 tokens context
- **tg128**: Generate 128 tokens

### Metrics

- **Throughput**: Tokens per second (t/s)
- **Latency**: Milliseconds per token
- **Per-Node Bandwidth**: MB/s measured via memory copy
- **Speedup vs Flat**: Percentage improvement over flat mmap

### Running Benchmarks

```bash
# Compare flat vs NUMA-sharded
./benchmark -m model.gguf -t pp512 -n 64 -i 10

# NUMA-sharded only with verbose output
./benchmark -m model.gguf -t tg128 -s -v

# Test on 7B and 33B models
./benchmark -m models/llama-7b.gguf -t pp512
./benchmark -m models/llama-33b.gguf -t pp512
```

### Expected Results (POWER8 S824)

| Model | Test | Flat (t/s) | NUMA (t/s) | Speedup |
|-------|------|------------|------------|---------|
| TinyLlama 1.1B | pp512 | ~140 | ~170 | 1.21x |
| LLaMA 7B | pp512 | ~45 | ~55 | 1.22x |
| LLaMA 33B | pp512 | ~12 | ~15 | 1.25x |

Note: Actual results depend on model architecture and system load.

## Building

### Requirements

- **POWER8**: GCC 9+, libnuma-dev, `make`
- **x86**: Any C11 compiler (NUMA code compiled out)

### Build Targets

```bash
make              # POWER8 build (default)
make x86          # Cross-platform x86 build
make benchmark    # Build benchmark harness
make detect       # Build topology detector
make clean        # Clean artifacts
make install      # Install to /usr/local
```

### Cross-Compilation

```bash
# For POWER8 from x86
powerpc64-linux-gnu-gcc -mcpu=power8 -mvsx -O3 -c ggml-numa-shard.h
```

## Integration with llama.cpp

### Integration Points

1. **Model Loading** (`ggml-backend.c`):
   - Call `numa_init_sharding()` before `ggml_backend_load`
   - Parse GGUF with `numa_parse_gguf()`
   - Assign layers with `numa_assign_layers()`

2. **Tensor Allocation** (`ggml-alloc.c`):
   - Hook into tensor buffer allocation
   - Call `numa_pin_tensor()` for each buffer

3. **Computation** (`ggml.cu` / `ggml-openmp.c`):
   - Set thread affinity with `numa_run_on_node()`
   - Pin threads to NUMA-local cores

### Example Integration

```c
// In llama_model_load()
numa_init_sharding();

struct ggml_tensor * tensors[MAX_TENSORS];
int count = numa_parse_gguf(model_path, tensors, MAX_TENSORS);
numa_assign_layers(tensors, count, NULL);

// During inference
for (int i = 0; i < count; i++) {
    if (tensors[i].numa_node >= 0) {
        numa_run_on_node(tensors[i].numa_node);
        // Compute on correct node's cores
    }
}
```

## File Structure

```
tools/numa-llama/
├── ggml-numa-shard.h   # Header-only NUMA shard router
├── numa_policy.h       # Policy parsing helpers
├── numa_benchmark.c     # Benchmark harness
├── numa_detect.c       # Topology detection utility
├── Makefile            # Build system
└── README.md           # This file
```

## Technical Notes

### Memory Bandwidth Asymmetry

POWER8 S824 has non-uniform memory bandwidth:
- Nodes 0/1: ~215-225 MB/s (opposite memory controller)
- Nodes 2/3: ~400-425 MB/s (adjacent memory controller)

This asymmetry makes NUMA placement critical for performance.

### Thread Affinity

For best results, combine NUMA memory pinning with thread affinity:

```bash
numactl --cpunodebind=0-15 --membind=0 ./llama-server -m model.gguf
```

### Optimal Thread Count

**64 threads** (not 128). See bounty spec for details.

## License

MIT License

## Author

NUMA-LLAMA Team

## Bounty Reference

- **Bounty #2277**: NUMA-Aware Model Sharding for POWER8 llama.cpp
- **Payout**: 250 RTC on merge with benchmarks
- **Wallet**: `C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg`
