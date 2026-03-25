# Integration Guide: NUMA Sharding for llama.cpp

**Bounty:** Scottcjn/rustchain-bounties #2277  
**Version:** 1.0.0  
**Date:** 2026-03-23

---

## 1. Quick Start

### 1.1 Header-Only Integration (Recommended)

Copy the header file to your llama.cpp source:

```bash
cp numa_sharding/src/ggml-numa-shard.h /path/to/llama.cpp/ggml/include/
```

Add initialization to your main function:

```c
#include "ggml-numa-shard.h"

int main(int argc, char **argv) {
    // Initialize NUMA sharding before model loading
    if (ggml_numa_shard_init(NULL) < 0) {
        fprintf(stderr, "NUMA sharding initialization failed\n");
        // Continue without NUMA - graceful fallback
    }
    
    // ... rest of llama.cpp initialization
    
    // Cleanup on exit
    ggml_numa_shard_cleanup();
    return 0;
}
```

### 1.2 Runtime Configuration

Set environment variable before running:

```bash
export GGML_NUMA_SHARD_MAP="0-8:1,9-20:3,21-31:2"
./llama-cli -m model.gguf -n 128 -p "Hello"
```

---

## 2. Build Instructions

### 2.1 POWER8 Build

```bash
# Clone llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# Copy NUMA sharding header
cp /path/to/ggml-numa-shard.h ggml/include/

# Build with POWER8 optimizations
cmake -B build \
    -DCMAKE_C_COMPILER=gcc \
    -DCMAKE_C_FLAGS="-mcpu=power8 -mvsx -maltivec -O3 -lnuma" \
    -DCMAKE_BUILD_TYPE=Release

cmake --build build --config Release
```

### 2.2 x86 Build (Compatibility Test)

```bash
# Build with standard x86 flags
cmake -B build \
    -DCMAKE_C_FLAGS="-march=native -O3" \
    -DCMAKE_BUILD_TYPE=Release

cmake --build build --config Release
```

The NUMA sharding code will:
- Detect NUMA availability at runtime
- Gracefully fallback if NUMA unavailable
- Not affect x86 functionality

---

## 3. Code Integration Points

### 3.1 Model Loading (llama.cpp)

Modify `llama_model_load()` to initialize NUMA:

```cpp
// In llama.cpp, around model loading function
static struct ggml_context *llama_model_load(...) {
    // Initialize NUMA sharding before tensor allocation
    #if defined(GGML_NUMA_POWERPC) || defined(GGML_NUMA_LINUX)
    ggml_numa_shard_init(NULL);
    #endif
    
    // ... existing model loading code
    
    return ctx;
}
```

### 3.2 Tensor Allocation (ggml.c)

Modify tensor allocation to use NUMA binding:

```c
// In ggml.c, ggml_backend_alloc_ctx() or similar
struct ggml_tensor *ggml_new_tensor(...) {
    struct ggml_tensor *tensor = ggml_new_tensor_impl(...);
    
    #if defined(GGML_NUMA_LINUX)
    if (g_ggml_numa_ctx.initialized) {
        int node = ggml_numa_shard_assign_tensor(tensor->name, -1);
        if (node >= 0) {
            ggml_numa_shard_bind(tensor->data, ggml_nbytes(tensor), node);
        }
    }
    #endif
    
    return tensor;
}
```

### 3.3 Memory Mapping

For mmap-based loading, use the wrapper macro:

```c
// Replace direct mmap calls
void *ptr = mmap(addr, length, prot, flags, fd, offset);

// With NUMA-aware wrapper
int numa_node = ggml_numa_shard_assign_tensor(tensor_name, layer_idx);
void *ptr = GGML_NUMA_MMAP(addr, length, prot, flags, fd, offset, numa_node);
```

---

## 4. Configuration Options

### 4.1 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GGML_NUMA_SHARD_MAP` | Layer-to-node mapping | `"0-8:0,9-20:1,21-31:2"` |
| `GGML_NUMA_POLICY` | Binding policy | `"bind"` |

### 4.2 Configuration Syntax

```
GGML_NUMA_SHARD_MAP="range:node,range:node,pattern:node"
```

Examples:

```bash
# Range-based (layers 0-8 to node 1, etc.)
export GGML_NUMA_SHARD_MAP="0-8:1,9-20:3,21-31:2"

# Pattern-based (attention to node 3)
export GGML_NUMA_SHARD_MAP="attn:3,ffn:2,embed:1"

# Mixed
export GGML_NUMA_SHARD_MAP="0-5:1,attn:3,ffn:2"
```

### 4.3 Preset Files

Use provided presets for common configurations:

```bash
# POWER8 S824 optimal
export GGML_NUMA_SHARD_MAP=$(jq -r '.numa_shard_config.value' \
    presets/power8_s824.json)

# x86 dual-socket
export GGML_NUMA_SHARD_MAP=$(jq -r '.numa_shard_config.value' \
    presets/dual_socket_x86.json)
```

---

## 5. Thread Configuration

### 5.1 POWER8 Recommendations

```bash
# Optimal: 64 threads
export OMP_NUM_THREADS=64
./llama-cli -m model.gguf -t 64 ...

# NOT recommended: 128 threads (causes contention)
# ./llama-cli -m model.gguf -t 128 ...  # Avoid!
```

### 5.2 Thread Affinity

```bash
# Bind threads to all NUMA nodes
numactl --cpunodebind=0,1,2,3 ./llama-cli -m model.gguf -t 64 ...

# Or let NUMA sharding handle it (recommended)
./llama-cli -m model.gguf -t 64 ...
```

---

## 6. Verification

### 6.1 Check NUMA Availability

```bash
# Verify NUMA is available
numactl --hardware

# Expected output:
# available: 4 nodes (0-3)
# node 0 cpus: 0 1 2 3 4 5 6 7 ...
# node 0 size: 131072 MB
# ...
```

### 6.2 Verify Initialization

```bash
export GGML_NUMA_SHARD_MAP="0-8:1,9-20:3,21-31:2"
./llama-cli -m model.gguf -n 1

# Expected log output:
# [NUMA] Initialized with 3 rules across 4 nodes
# [NUMA] Config: 0-8:1,9-20:3,21-31:2
```

### 6.3 Check Statistics

```bash
# NUMA statistics printed on cleanup
./llama-cli -m model.gguf -n 10

# Expected output:
# ========== NUMA Sharding Statistics ==========
# Total bytes bound: 4096 MB
# Tensors assigned:  234
# Bind failures:     0
#
# Per-node distribution:
#   Node 1:  1024 MB ( 25.0%)
#   Node 2:  1536 MB ( 37.5%)
#   Node 3:  1536 MB ( 37.5%)
# =============================================
```

---

## 7. Troubleshooting

### 7.1 Common Issues

**Issue: "NUMA not available"**

```bash
# Check if libnuma is installed
ldd ./llama-cli | grep numa

# Install if missing
apt-get install libnuma-dev  # Debian/Ubuntu
yum install numactl-devel   # RHEL/CentOS
```

**Issue: "mbind failed"**

```bash
# Check NUMA topology
numactl --hardware

# Verify target nodes exist
# If only 2 nodes available, adjust config:
export GGML_NUMA_SHARD_MAP="0-8:0,9-20:1,21-31:1"
```

**Issue: No performance improvement**

```bash
# Verify multi-NUMA system
numactl --hardware

# Check if running on single node
numactl --show

# Try explicit thread binding
numactl --cpunodebind=all --membind=all ./llama-cli ...
```

### 7.2 Debug Mode

Enable verbose logging:

```c
// Add to your code before initialization
#define GGML_NUMA_DEBUG 1
ggml_numa_shard_init(NULL);
```

---

## 8. Performance Tuning

### 8.1 Benchmark Sweep

```bash
#!/bin/bash
# benchmark_sweep.sh

for threads in 32 48 64 80; do
    for config in \
        "0-8:0,9-20:1,21-31:2" \
        "0-8:1,9-20:2,21-31:3" \
        "0-8:1,9-20:3,21-31:2"; do
        
        export GGML_NUMA_SHARD_MAP="$config"
        echo "=== Threads: $threads, Config: $config ==="
        
        ./build/bin/llama-bench \
            -m model.gguf \
            -t $threads \
            -b 512 \
            -n 128 \
            -r 3
    done
done
```

### 8.2 Model-Specific Tuning

For models with non-standard layer counts:

```bash
# 22-layer model (TinyLlama)
export GGML_NUMA_SHARD_MAP="0-7:1,8-14:3,15-21:2"

# 40-layer model (Llama-2 13B)
export GGML_NUMA_SHARD_MAP="0-10:1,11-26:3,27-39:2"

# 60-layer model (Llama-2 33B)
export GGML_NUMA_SHARD_MAP="0-15:1,16-40:3,41-59:2"
```

---

## 9. API Reference

### 9.1 Core Functions

```c
// Initialize NUMA sharding
int ggml_numa_shard_init(const char *config_string);

// Assign tensor to NUMA node
int ggml_numa_shard_assign_tensor(const char *tensor_name, int layer_idx);

// Bind memory to node
int ggml_numa_shard_bind(void *addr, size_t len, int numa_node);

// Print statistics
void ggml_numa_shard_print_stats(void);

// Cleanup
void ggml_numa_shard_cleanup(void);
```

### 9.2 Utility Functions

```c
// Check NUMA availability
int ggml_numa_available(void);

// Get number of NUMA nodes
int ggml_numa_num_nodes(void);

// Get recommended thread count (POWER8: 64)
int ggml_numa_get_recommended_threads(void);
```

### 9.3 Helper Macros

```c
// NUMA-aware mmap
void *ptr = GGML_NUMA_MMAP(addr, length, prot, flags, fd, offset, node);

// NUMA-aware malloc
void *ptr = GGML_NUMA_MALLOC(size, node);

// Get node for tensor
int node = GGML_NUMA_NODE_FOR_TENSOR(name, layer);
```

---

## 10. Best Practices

### 10.1 Do's

- ✅ Initialize NUMA before model loading
- ✅ Use 64 threads on POWER8 S824
- ✅ Place attention layers on fastest nodes (2/3)
- ✅ Check NUMA availability before binding
- ✅ Print statistics for debugging

### 10.2 Don'ts

- ❌ Use 128 threads on POWER8 (causes contention)
- ❌ Bind to non-existent NUMA nodes
- ❌ Expect improvement on single-socket systems
- ❌ Forget to link with `-lnuma`

---

## 11. Example Integration

### 11.1 Complete Example

```c
// main.c
#include <stdio.h>
#include <stdlib.h>
#include "ggml-numa-shard.h"

int main(int argc, char **argv) {
    // Step 1: Check NUMA availability
    if (!ggml_numa_available()) {
        fprintf(stderr, "NUMA not available, running without sharding\n");
    } else {
        fprintf(stdout, "NUMA available with %d nodes\n", 
                ggml_numa_num_nodes());
    }
    
    // Step 2: Initialize NUMA sharding
    // Uses GGML_NUMA_SHARD_MAP env var if NULL
    if (ggml_numa_shard_init(NULL) < 0) {
        fprintf(stderr, "Warning: NUMA init failed, continuing without\n");
    }
    
    // Step 3: Load model (NUMA binding happens automatically)
    // ... llama.cpp model loading ...
    
    // Step 4: Run inference
    // ... llama.cpp inference ...
    
    // Step 5: Cleanup and print statistics
    ggml_numa_shard_cleanup();
    
    return 0;
}
```

### 11.2 Build Command

```bash
gcc -o llama-numa main.c \
    -I/path/to/llama.cpp/ggml/include \
    -L/path/to/llama.cpp/build/ggml/src -lggml \
    -lnuma \
    -mcpu=power8 -mvsx -O3
```

---

## 12. Support

For issues or questions:

1. Check `docs/ARCHITECTURE.md` for design details
2. Review `reports/validation_report.md` for expected behavior
3. Run `benchmark_numa.sh` for automated testing
4. Consult `reports/performance_analysis.md` for tuning guidance

---

*Integration Guide Version: 1.0.0*  
*Last Updated: 2026-03-23*  
*Bounty: Scottcjn/rustchain-bounties #2277*
