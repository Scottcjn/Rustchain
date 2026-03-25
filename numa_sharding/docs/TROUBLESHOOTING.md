# Troubleshooting Guide: NUMA Sharding

**Bounty:** Scottcjn/rustchain-bounties #2277  
**Version:** 1.0.0  
**Date:** 2026-03-23

---

## Quick Reference

| Symptom | Likely Cause | Quick Fix |
|---------|--------------|-----------|
| "NUMA not available" | libnuma not installed | `apt-get install libnuma-dev` |
| "mbind failed" | Invalid node ID | Check `numactl --hardware` |
| No improvement | Single NUMA node | Verify multi-NUMA topology |
| Performance regression | Too many threads | Use 64 threads, not 128 |
| Crash on startup | Missing NUMA guard | Check `#ifdef` guards |

---

## 1. Build Issues

### 1.1 "numa.h: No such file or directory"

**Cause:** libnuma development headers not installed.

**Solution:**

```bash
# Debian/Ubuntu
sudo apt-get install libnuma-dev

# RHEL/CentOS/Fedora
sudo yum install numactl-devel
# or
sudo dnf install numactl-devel

# SUSE
sudo zypper install libnuma-devel
```

### 1.2 "undefined reference to `mbind`"

**Cause:** Not linking with libnuma.

**Solution:**

```bash
# Add -lnuma to linker flags
gcc ... -lnuma

# Or in CMake
target_link_libraries(your_target numa)
```

### 1.3 "error: 'MPOL_BIND' undeclared"

**Cause:** Missing `_GNU_SOURCE` definition.

**Solution:**

```bash
# Add -D_GNU_SOURCE to compiler flags
gcc -D_GNU_SOURCE ...

# Or define before including headers
#define _GNU_SOURCE
#include <numaif.h>
```

### 1.4 POWER8-Specific Build Errors

**Cause:** Wrong compiler flags.

**Solution:**

```bash
# Use correct POWER8 flags
gcc -mcpu=power8 -mvsx -maltivec ...

# NOT these (wrong architecture):
# gcc -march=native ...  # May not select POWER8
# gcc -mcpu=power9 ...   # Different architecture
```

---

## 2. Runtime Issues

### 2.1 "NUMA not available on this system"

**Diagnostic:**

```bash
# Check if NUMA is available
numactl --hardware

# Check if libnuma is linked
ldd ./llama-cli | grep numa
```

**Possible Causes:**

1. **Single-socket system**: NUMA only exists on multi-socket systems
2. **NUMA disabled in BIOS**: Check BIOS settings
3. **Missing kernel support**: Rare on modern kernels

**Solutions:**

```bash
# Verify NUMA nodes
cat /sys/devices/system/node/online

# Check BIOS (may require reboot)
# Look for "NUMA", "Memory Interleaving", or "Node Interleaving"
# Disable "Node Interleaving" to enable NUMA
```

**Note:** The library gracefully falls back to non-NUMA operation.

### 2.2 "mbind failed for X bytes on node Y"

**Diagnostic:**

```bash
# Check available nodes
numactl --hardware

# Check current policy
numactl --show
```

**Possible Causes:**

1. **Invalid node ID**: Target node doesn't exist
2. **Insufficient memory**: Node is out of memory
3. **Permission issues**: Running in restricted environment

**Solutions:**

```bash
# If only 2 nodes (0-1), adjust config:
export GGML_NUMA_SHARD_MAP="0-8:0,9-20:1,21-31:1"

# Check memory per node
numactl --hardware | grep size

# Try running without explicit binding
unset GGML_NUMA_SHARD_MAP
./llama-cli -m model.gguf -n 10
```

### 2.3 "move_pages failed"

**Cause:** Runtime page migration failed.

**Solutions:**

1. This is a warning, not a fatal error
2. Initial binding (`mbind`) is preferred over migration
3. Ensure sufficient free memory on target node

---

## 3. Performance Issues

### 3.1 No Performance Improvement

**Diagnostic:**

```bash
# Verify multi-NUMA topology
numactl --hardware

# Expected: Multiple nodes with different bandwidths
# If single node: NUMA sharding won't help
```

**Possible Causes:**

1. **Single NUMA node**: No optimization possible
2. **Memory already local**: First-touch policy worked well
3. **Model too small**: Fits in cache, memory not bottleneck
4. **Wrong configuration**: Suboptimal layer mapping

**Solutions:**

```bash
# Check node count
NODES=$(numactl --hardware | grep "available:" | awk '{print $2}')
if [ "$NODES" -lt 2 ]; then
    echo "Single NUMA node - sharding won't help"
fi

# Try different configurations
export GGML_NUMA_SHARD_MAP="0-15:0,16-31:1"  # Simple split
export GGML_NUMA_SHARD_MAP="0-8:1,9-20:3,21-31:2"  # POWER8 optimal

# Run benchmark comparison
./benchmarks/benchmark_numa.sh -m model.gguf --compare
```

### 3.2 Performance Regression (Slower with NUMA)

**Diagnostic:**

```bash
# Check thread count
echo "Current threads: $OMP_NUM_THREADS"

# Check NUMA statistics
# Look for high bind failure count
```

**Possible Causes:**

1. **Too many threads**: Memory contention (common on POWER8)
2. **Wrong node binding**: All layers on slow node
3. **Thread/NUMA mismatch**: Threads on different node than memory
4. **System load**: Other processes competing for bandwidth

**Solutions:**

```bash
# POWER8: Use 64 threads, NOT 128
export OMP_NUM_THREADS=64
./llama-cli -m model.gguf -t 64 ...

# Verify thread affinity
numactl --cpunodebind=all ./llama-cli ...

# Run on idle system
# Stop other memory-intensive processes
```

### 3.3 Inconsistent Results

**Diagnostic:**

```bash
# Run multiple times
for i in {1..5}; do
    ./llama-bench -m model.gguf -t 64 -b 512 -n 128
done

# Check for high variance
```

**Possible Causes:**

1. **Thermal throttling**: CPU frequency changing
2. **System load**: Other processes interfering
3. **NUMA balancing**: Kernel moving pages
4. **Insufficient warmup**: First run slower

**Solutions:**

```bash
# Disable NUMA balancing (requires root)
echo 0 | sudo tee /proc/sys/kernel/numa_balancing

# Lock CPU frequency (if supported)
sudo cpufreq-set -g performance

# Warmup before measurement
./llama-cli -m model.gguf -n 10 > /dev/null  # Warmup
./llama-cli -m model.gguf -n 128             # Measure

# Run multiple iterations and average
./llama-bench -m model.gguf -t 64 -b 512 -n 128 -r 5
```

---

## 4. Configuration Issues

### 4.1 Configuration Not Applied

**Diagnostic:**

```bash
# Check environment variable
echo $GGML_NUMA_SHARD_MAP

# Check if it's exported
export | grep GGML
```

**Solutions:**

```bash
# Export before running
export GGML_NUMA_SHARD_MAP="0-8:1,9-20:3,21-31:2"
./llama-cli -m model.gguf -n 10

# Or set inline
GGML_NUMA_SHARD_MAP="0-8:1,9-20:3,21-31:2" ./llama-cli -m model.gguf -n 10
```

### 4.2 Invalid Configuration Syntax

**Common Mistakes:**

```bash
# Wrong: Spaces in config
export GGML_NUMA_SHARD_MAP="0-8: 1, 9-20: 3"  # Don't add spaces

# Wrong: Missing node
export GGML_NUMA_SHARD_MAP="0-8,9-20:3"  # Node required for all

# Correct:
export GGML_NUMA_SHARD_MAP="0-8:1,9-20:3,21-31:2"
```

**Validation:**

```bash
# Parse and validate config
python3 -c "
config = '$GGML_NUMA_SHARD_MAP'
rules = config.split(',')
for rule in rules:
    parts = rule.split(':')
    assert len(parts) == 2, f'Invalid rule: {rule}'
    range_part, node = parts
    if '-' in range_part:
        start, end = map(int, range_part.split('-'))
        assert start <= end, f'Invalid range: {range_part}'
    print(f'Valid rule: {rule}')
print('Configuration valid!')
"
```

---

## 5. Integration Issues

### 5.1 x86 Build Broken

**Cause:** Missing `#ifdef` guards.

**Solution:**

Ensure all NUMA code is guarded:

```c
#if defined(__powerpc__) || defined(__powerpc64__) || defined(GGML_NUMA_LINUX)
    // NUMA-specific code
#endif
```

Check that fallback exists:

```c
static inline int ggml_numa_shard_bind(void *addr, size_t len, int numa_node) {
#if defined(GGML_NUMA_LINUX)
    // Linux NUMA code
    return mbind(...);
#else
    // Fallback for other platforms
    (void)addr; (void)len; (void)numa_node;
    return -1;
#endif
}
```

### 5.2 llama.cpp Integration Conflicts

**Symptoms:**

- Compilation errors in ggml.c
- Symbol conflicts
- Linker errors

**Solutions:**

1. **Use header-only version**: Copy only `ggml-numa-shard.h`
2. **Check include paths**: Ensure header is in include path
3. **Verify initialization order**: NUMA init before model load

---

## 6. Debugging Tools

### 6.1 NUMA Debugging

```bash
# Show NUMA topology
numactl --hardware

# Show current policy
numactl --show

# Show memory status per node
numactl --meminfo

# Trace NUMA system calls
strace -e mbind,move_pages,set_mempolicy ./llama-cli ...

# Check page placement (after running)
numactl --meminfo | grep -A1 "node"
```

### 6.2 Performance Profiling

```bash
# CPU profiling
perf record -g ./llama-cli -m model.gguf -n 128
perf report

# Memory bandwidth (if perf available)
perf stat -e uncore_imc_0/event=0x04,umask=0x03/ ...

# Check CPU frequency
watch -n1 "cat /proc/cpuinfo | grep MHz"
```

### 6.3 Enable Debug Logging

```c
// Add before initialization
#define GGML_NUMA_DEBUG 1

// Or set environment variable (if implemented)
export GGML_NUMA_DEBUG=1
```

---

## 7. Known Limitations

### 7.1 Platform Limitations

| Platform | Limitation | Workaround |
|----------|------------|------------|
| macOS | No NUMA support | N/A - runs without NUMA |
| Windows | Limited NUMA API | Use WSL or native Linux |
| Single-socket | No NUMA domains | No benefit from sharding |
| Containers | May hide NUMA | Use host networking |

### 7.2 Model Limitations

| Model Type | Limitation | Workaround |
|------------|------------|------------|
| <1B params | Minimal benefit | Use default config |
| MoE models | Expert placement not optimized | Future enhancement |
| Multi-modal | Vision layers not classified | Manual config needed |

---

## 8. Getting Help

### 8.1 Information to Collect

When reporting issues:

```bash
# System info
uname -a
cat /proc/cpuinfo | head -20

# NUMA topology
numactl --hardware

# Memory info
free -h
numactl --meminfo

# Build info
gcc --version
ldd ./llama-cli | grep -E "numa|ggml"

# Runtime config
echo $GGML_NUMA_SHARD_MAP
echo $OMP_NUM_THREADS

# Error output
./llama-cli -m model.gguf -n 10 2>&1 | tail -50
```

### 8.2 Documentation References

- Architecture: `docs/ARCHITECTURE.md`
- Integration: `docs/INTEGRATION.md`
- Performance: `reports/performance_analysis.md`
- Validation: `reports/validation_report.md`

---

*Troubleshooting Guide Version: 1.0.0*  
*Last Updated: 2026-03-23*  
*Bounty: Scottcjn/rustchain-bounties #2277*
