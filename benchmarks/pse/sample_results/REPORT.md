# POWER8 PSE Benchmark Results

Generated from 2 model(s).


## qwen_14b

**File:** `qwen1.5-14b-chat-q4_k_m.gguf`  
**Timestamp:** 2026-03-15T13:30:00Z


### Prompt Processing (tokens/sec)

| Build Mode | pp128 | pp512 | pp1024 |
|---|---|---|---|
| Stock llama.cpp | 82.4 (3.4% CV) | 65.1 (3.5% CV) | 48.7 (3.9% CV) |
| PSE-MASS | 115.6 (3.0% CV) | 94.2 (3.3% CV) | 72.8 (3.6% CV) |
| PSE+Coffers | 132.8 (3.0% CV) | 110.5 (3.1% CV) | 86.1 (3.6% CV) |

### Token Generation (tokens/sec)

| Build Mode | tg32 | tg128 |
|---|---|---|
| Stock llama.cpp | 12.4 (3.2% CV) | 11.8 (4.2% CV) |
| PSE-MASS | 15.1 (3.3% CV) | 14.3 (4.2% CV) |
| PSE+Coffers | 16.8 (2.4% CV) | 15.9 (3.8% CV) |

### Cache Hit Rates

| Build Mode | L1 Hit Rate | LLC Hit Rate |
|---|---|---|
| Stock llama.cpp | 92.00% | 80.00% |
| PSE-MASS | 94.00% | 85.00% |
| PSE+Coffers | 95.00% | 88.00% |

### PSE Markers

| Build Mode | NOI | DR | ACS (%) | MCI |
|---|---|---|---|---|
| Stock llama.cpp | 0 | 0.0000 | 0.0 | 0 |
| PSE-MASS | 128450 | 0.0031 | 38.9 | 2 |
| PSE+Coffers | 142800 | 0.0045 | 46.3 | 4 |

### Speedup vs Stock

| Metric | PSE-MASS | PSE+Coffers |
|---|---|---|
| pp128 | 1.40x | 1.61x |
| pp512 | 1.45x | 1.70x |
| pp1024 | 1.49x | 1.77x |
| tg32 | 1.22x | 1.35x |
| tg128 | 1.21x | 1.35x |

## tinyllama_1.1b

**File:** `tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf`  
**Timestamp:** 2026-03-15T12:00:00Z


### Prompt Processing (tokens/sec)

| Build Mode | pp128 | pp512 | pp1024 |
|---|---|---|---|
| Stock llama.cpp | 245.3 (3.3% CV) | 198.7 (3.1% CV) | 162.4 (3.6% CV) |
| PSE-MASS | 312.8 (3.0% CV) | 268.1 (2.8% CV) | 221.6 (3.7% CV) |
| PSE+Coffers | 341.5 (3.0% CV) | 295.3 (3.0% CV) | 248.9 (3.7% CV) |

### Token Generation (tokens/sec)

| Build Mode | tg32 | tg128 |
|---|---|---|
| Stock llama.cpp | 38.2 (2.9% CV) | 35.6 (3.9% CV) |
| PSE-MASS | 44.1 (3.0% CV) | 41.8 (3.8% CV) |
| PSE+Coffers | 46.8 (2.6% CV) | 44.2 (3.4% CV) |

### Cache Hit Rates

| Build Mode | L1 Hit Rate | LLC Hit Rate |
|---|---|---|
| Stock llama.cpp | 95.00% | 85.00% |
| PSE-MASS | 96.00% | 87.00% |
| PSE+Coffers | 96.50% | 89.00% |

### PSE Markers

| Build Mode | NOI | DR | ACS (%) | MCI |
|---|---|---|---|---|
| Stock llama.cpp | 0 | 0.0000 | 0.0 | 0 |
| PSE-MASS | 48720 | 0.0012 | 34.2 | 1 |
| PSE+Coffers | 52340 | 0.0018 | 41.7 | 3 |

### Speedup vs Stock

| Metric | PSE-MASS | PSE+Coffers |
|---|---|---|
| pp128 | 1.28x | 1.39x |
| pp512 | 1.35x | 1.49x |
| pp1024 | 1.36x | 1.53x |
| tg32 | 1.15x | 1.23x |
| tg128 | 1.17x | 1.24x |

---

## PSE Marker Reference

- **NOI (Number of Iterations)**
- **DR (Divergence Ratio)**
- **ACS (AltiVec Cycle Share %)**
- **MCI (Memory Coffer Index)**

- **NOI**: Total vec_perm iteration cycles executed during inference. Higher values indicate more AltiVec SIMD utilization.
- **DR**: KL divergence of token probability distribution vs stock build. Values near 0 mean PSE produces equivalent outputs.
- **ACS**: Percentage of total compute cycles spent in AltiVec vector units. Higher is better for PSE workloads.
- **MCI**: Number of active NUMA memory coffers used during inference. Higher values indicate better memory distribution across NUMA nodes.