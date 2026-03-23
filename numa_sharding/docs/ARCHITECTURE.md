# NUMA-Aware Model Sharding for POWER8 llama.cpp
## Architecture Design Document

**Bounty:** #2277  
**Target Hardware:** IBM POWER8 S824 (4 NUMA nodes, 512GB RAM)  
**Version:** 1.0.0  
**Date:** 2026-03-23

---

## 1. Executive Summary

This document describes the architecture for NUMA-aware model sharding in llama.cpp, optimized for IBM POWER8 systems. The implementation addresses the critical performance bottleneck caused by cross-NUMA memory accesses when running large language models on multi-socket POWER8 servers.

### Problem Statement
- Current llama.cpp uses flat `mmap()` for model loading
- No NUMA awareness → tensors distributed arbitrarily across memory nodes
- Cross-NUMA accesses incur 2-3x latency penalty
- POWER8 S824 has 4 NUMA nodes with asymmetric bandwidth:
  - Node 2/3: 400-425 MB/s (fastest)
  - Node 0: 215-225 MB/s (slowest)

### Solution Overview
Implement intelligent per-layer NUMA placement using:
1. GGUF tensor metadata parsing
2. Configurable layer-to-node mapping
3. `mbind()`/`move_pages()` for memory pinning
4. Minimal code intrusion (header-only + optional C file)

---

## 2. System Architecture

### 2.1 Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      llama.cpp Application                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │  GGUF Loader    │───▶│  NUMA Shard     │───▶│  Tensor     │ │
│  │  (existing)     │    │  Router         │    │  Allocator  │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
│                              │                       │          │
│                              ▼                       ▼          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              ggml-numa-shard.h (Header-only)             │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ Layer Parser │  │ Node Mapper  │  │ Memory Binder│   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Linux NUMA APIs (numactl)                   │   │
│  │  mbind() | move_pages() | set_mempolicy() | get_mempolicy() │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    POWER8 Hardware (S824)                        │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │  Node 0 │  │  Node 1 │  │  Node 2 │  │  Node 3 │            │
│  │ 215MB/s │  │ 350MB/s │  │ 425MB/s │  │ 425MB/s │            │
│  │ 128GB   │  │ 128GB   │  │ 128GB   │  │ 128GB   │            │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

1. **Model Load Phase**
   - GGUF parser reads tensor metadata
   - NUMA router classifies tensors by layer type
   - Memory policy assigned per tensor group

2. **Memory Allocation Phase**
   - `mmap()` allocates virtual address space
   - `mbind()` binds pages to target NUMA node
   - Optional: `move_pages()` for runtime rebalancing

3. **Inference Phase**
   - Threads pinned to NUMA-local CPUs
   - Memory accessed from local node (minimal cross-NUMA)

---

## 3. NUMA Sharding Strategy

### 3.1 Layer Classification

Transformer layers classified into three categories:

| Layer Type | Layers | Recommended Node | Rationale |
|------------|--------|------------------|-----------|
| Early Embedding | 0-8 | Node 1 | Sequential access, moderate bandwidth |
| Attention | 9-20 | Node 3 | High bandwidth, KV cache residency |
| FFN/Output | 21-31 | Node 2 | Highest bandwidth for matrix ops |

### 3.2 Configuration Syntax

Environment variable format:
```bash
GGML_NUMA_SHARD_MAP="0-8:node1,9-20:node3,21-31:node2,attn:node3"
```

Parsed structure:
```c
struct numa_shard_rule {
    int layer_start;      // First layer index
    int layer_end;        // Last layer index (inclusive)
    int numa_node;        // Target NUMA node ID
    const char *pattern;  // Optional: "attn", "ffn", "embed"
};
```

### 3.3 Default Mapping (POWER8 S824)

```c
static const struct numa_shard_rule default_power8_rules[] = {
    { 0,  8,  1, "embed" },   // Early layers → Node 1
    { 9,  20, 3, "attn" },    // Attention → Node 3 (fastest)
    { 21, 31, 2, "ffn" },     // FFN → Node 2 (fastest)
    { -1, -1, 0, NULL }       // Sentinel
};
```

---

## 4. API Design

### 4.1 Public Functions

```c
// Initialize NUMA sharding subsystem
int ggml_numa_shard_init(const char *config_string);

// Parse GGUF tensor and assign NUMA node
int ggml_numa_shard_assign_tensor(struct ggml_tensor *tensor, 
                                   const char *tensor_name);

// Bind allocated memory to NUMA node
int ggml_numa_shard_bind(void *addr, size_t len, int numa_node);

// Query current NUMA configuration
int ggml_numa_shard_get_node(const char *layer_name);

// Cleanup
void ggml_numa_shard_cleanup(void);
```

### 4.2 Integration Points

| llama.cpp File | Integration Point | Modification |
|----------------|-------------------|--------------|
| `ggml.c` | `ggml_backend_alloc_ctx()` | Add NUMA binding after allocation |
| `llama.cpp` | `load_model_from_file()` | Initialize NUMA router before loading |
| `common.cpp` | `gpt_params` struct | Add `numa_shard_map` config option |

---

## 5. Memory Binding Implementation

### 5.1 Primary Method: mbind()

```c
#include <numa.h>
#include <numaif.h>

int ggml_numa_shard_bind(void *addr, size_t len, int numa_node) {
    unsigned long nodemask = (1UL << numa_node);
    
    // MPOL_BIND: Allocate from specified node
    // MPOL_MF_STRICT: Fail if pages already on wrong node
    // MPOL_MF_MOVE: Migrate existing pages
    return mbind(addr, len, MPOL_BIND, &nodemask, 
                 sizeof(nodemask) * 8, 
                 MPOL_MF_STRICT | MPOL_MF_MOVE);
}
```

### 5.2 Fallback: move_pages()

For runtime rebalancing:
```c
#include <numaif.h>

int ggml_numa_shard_migrate(void *addr, size_t len, 
                            int from_node, int to_node) {
    long page_size = sysconf(_SC_PAGESIZE);
    long num_pages = len / page_size;
    
    void **pages = malloc(num_pages * sizeof(void*));
    int *nodes = malloc(num_pages * sizeof(int));
    int *status = malloc(num_pages * sizeof(int));
    
    // Initialize page addresses
    for (long i = 0; i < num_pages; i++) {
        pages[i] = addr + (i * page_size);
        nodes[i] = to_node;
    }
    
    int ret = move_pages(0, num_pages, pages, nodes, status, MPOL_MF_MOVE);
    
    free(pages);
    free(nodes);
    free(status);
    return ret;
}
```

---

## 6. Platform Compatibility

### 6.1 POWER8 Build Requirements

```bash
# Compiler flags
CC=gcc
CFLAGS="-mcpu=power8 -mvsx -O3 -maltivec"
LDFLAGS="-lnuma"

# Minimum GCC version
GCC >= 9.0
```

### 6.2 x86 Compatibility

All POWER8-specific code guarded by:
```c
#if defined(__powerpc__) || defined(__powerpc64__)
    // POWER8 NUMA code
#elif defined(__x86_64__) || defined(_M_X64)
    // x86 NUMA code (optional)
#else
    // Fallback: no NUMA awareness
#endif
```

### 6.3 Runtime Detection

```c
int ggml_numa_available(void) {
#if defined(__GLIBC__) && defined(_GNU_SOURCE)
    return numa_available() != -1;
#else
    return 0;
#endif
}
```

---

## 7. Benchmark Methodology

### 7.1 Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| `pp512` | Prefill throughput (512 tokens) | +40% vs flat mmap |
| `tg128` | Text generation (128 tokens) | +50% vs flat mmap |
| Memory BW | Per-node bandwidth utilization | >85% local |
| Cross-NUMA % | Remote memory accesses | <10% |

### 7.2 Test Models

| Model | Parameters | Quantization | Layers |
|-------|------------|--------------|--------|
| TinyLlama | 1.1B | Q4_0 | 22 |
| Llama-2 | 7B | Q4_K_M | 32 |
| Llama-2 | 33B | Q4_K_M | 60 |

### 7.3 Benchmark Commands

```bash
# Baseline (flat mmap)
numactl --cpunodebind=0 --membind=0 \
    ./build/bin/llama-bench -m model.gguf -t 64 -b 512 -n 128

# NUMA-sharded
export GGML_NUMA_SHARD_MAP="0-8:node1,9-20:node3,21-31:node2"
./build/bin/llama-bench -m model.gguf -t 64 -b 512 -n 128 \
    --numa-shard
```

---

## 8. Expected Performance Gains

### 8.1 Theoretical Analysis

Based on POWER8 S824 memory topology:

| Scenario | Cross-NUMA % | Effective BW | Relative Perf |
|----------|--------------|--------------|---------------|
| Flat mmap (random) | 75% | 280 MB/s | 1.0x |
| NUMA-sharded (optimal) | 8% | 410 MB/s | 1.46x |

### 8.2 Projected Benchmarks

| Model | Baseline t/s | NUMA-sharded t/s | Gain |
|-------|--------------|------------------|------|
| TinyLlama 1.1B | 147.54 | 215.00 | +45.7% |
| Llama-2 7B | 42.3 | 61.8 | +46.1% |
| Llama-2 33B | 8.7 | 12.5 | +43.7% |

---

## 9. Risk Analysis

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| mbind() fails silently | Low | High | Add strict error checking |
| GGUF format changes | Medium | Medium | Version detection + fallback |
| Thread pinning conflicts | Medium | Low | Document numactl requirements |
| x86 regression | Low | High | Extensive CI guards |

---

## 10. File Structure

```
numa_sharding/
├── src/
│   ├── ggml-numa-shard.h      # Header-only API (main deliverable)
│   └── ggml-numa-shard.c      # Optional: extended implementation
├── benchmarks/
│   ├── benchmark_numa.sh      # Automated benchmark script
│   ├── compare_results.py     # Result analysis script
│   └── expected_results.json  # Expected baseline numbers
├── presets/
│   ├── power8_s824.json       # POWER8 S824 tuning preset
│   ├── power8_default.json    # Generic POWER8 preset
│   └── dual_socket_x86.json   # x86 dual-socket preset
├── reports/
│   ├── validation_report.md   # Validation results
│   └── performance_analysis.md # Detailed performance analysis
└── docs/
    ├── ARCHITECTURE.md        # This document
    ├── INTEGRATION.md         # Integration guide
    └── TROUBLESHOOTING.md     # Common issues
```

---

## 11. Acceptance Criteria

### 11.1 Functional Requirements

- [ ] Parses GGUF tensor metadata correctly
- [ ] Assigns layers to NUMA nodes per configuration
- [ ] Successfully binds memory using `mbind()`
- [ ] Compiles on POWER8 with GCC 9+
- [ ] Does not break x86 builds

### 11.2 Performance Requirements

- [ ] `pp512` throughput improved by ≥40%
- [ ] `tg128` throughput improved by ≥45%
- [ ] Cross-NUMA memory accesses <10%
- [ ] Memory bandwidth utilization >85% on target nodes

### 11.3 Deliverables

- [ ] `ggml-numa-shard.h` (header-only implementation)
- [ ] Benchmark harness with automated comparison
- [ ] Tuning presets for POWER8 S824
- [ ] Validation report with expected results
- [ ] Integration documentation

---

## 12. References

1. ARM Community: "Scaling llama.cpp on Neoverse N2: Solving Cross-NUMA" (2026)
2. llama.cpp GitHub: Issue #11333 "NUMA-aware MoE Expert Allocation"
3. IBM POWER8 Architecture Manual
4. Linux NUMA API Documentation (numactl)
5. Scottcjn/rustchain-bounties: Bounty #2277 specification

---

*Document Version: 1.0.0*  
*Last Updated: 2026-03-23*
