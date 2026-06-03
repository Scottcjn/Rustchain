# GPU Fingerprinting — PPA Channel 8

## Overview

GPU fingerprinting extends Proof of Physical AI (PPA) from CPU-only verification to full GPU silicon identity. This enables verification of AI inference hardware in decentralized compute marketplaces.

## Modules

| Module | Channels | Target Hardware |
|--------|----------|----------------|
| `gpu_fingerprint.py` | 5 (memory, compute, jitter, thermal, PCIe) | NVIDIA GPUs (CUDA) |
| `gpu_fingerprint_vulkan.py` | 4 (identity, queues, memory types, system) | Any GPU (Vulkan) |
| `igpu_attestation.py` | 5 (fabric, contention, clock, cache, die) | AMD APU / Intel iGPU |
| `tensor_core_fingerprint.py` | 1 (FP16 matmul LSB drift) | NVIDIA with tensor cores |
| `gpu_spoof_test.py` | Cross-reference against 9 GPU profiles | Spoof detection |

## Quick Start

```bash
cd miners/

# Run GPU fingerprint (requires NVIDIA GPU + PyTorch)
python3 gpu_fingerprint.py

# Run tensor core precision drift (novel technique)
python3 tensor_core_fingerprint.py --verbose

# Test if your GPU can fake being an H100
python3 gpu_spoof_test.py --claim H100_SXM

# iGPU attestation (AMD APU only)
python3 igpu_attestation.py

# Vulkan fingerprint (any GPU vendor)
python3 gpu_fingerprint_vulkan.py --list
python3 gpu_fingerprint_vulkan.py --device 0
```

## Channel Details

### 8a: Memory Hierarchy Latency
Probes GPU memory hierarchy by measuring matmul throughput at different working set sizes. Cache tier transitions (L1→L2→HBM) produce measurable latency inflection points unique to each GPU architecture.

### 8b: Compute Throughput Asymmetry
Measures FP32 vs FP16 vs BF16 matmul throughput ratios. Each GPU generation has a characteristic ratio determined by its tensor core design:
- **Maxwell (no TC)**: FP16:FP32 ≈ 0.91x
- **Ada (4th gen TC)**: FP16:FP32 ≈ 4.16x
- **Blackwell (5th gen TC)**: FP16:FP32 ≈ 2.92x

### 8c: Warp Scheduling Jitter
Measures kernel launch timing variance. Real GPUs have measurable scheduling jitter (CV 0.01-0.5). Perfect emulation produces too-uniform timing.

### 8d: Thermal Ramp Signature
Records GPU temperature during sustained load to capture the thermal ramp rate and cooldown curve — unique to each GPU's cooling system and die characteristics.

### 8e: PCIe/Bus Bandwidth
Measures host-to-device and device-to-host transfer speeds. Reveals PCIe generation, lane width, and adapter configurations. Laptop x8 ≠ desktop x16 ≠ server NVLink.

### 8f: Tensor Core Precision Drift (Novel)
Different GPU generations implement tensor core FMA with different accumulator widths:
- Volta: 25-bit alignment, FMA groups of 4
- Ampere: 26-bit, groups of 8
- Hopper: 27-bit, groups of 16

The **least significant bits** of identical FP16 matmuls differ between generations. This is deterministic and unforgeable — the ALU design determines the output.

### 8i: iGPU Silicon Coherence
For integrated GPUs (AMD APU, Intel iGPU), measures internal fabric latency, CPU↔iGPU memory contention, clock domain correlation, and shared cache topology to prove CPU and GPU are on the same die.

## Validated Hardware

| GPU | Architecture | Channels Passed | Key Signature |
|-----|-------------|----------------|---------------|
| RTX 4070 Laptop | Ada sm_8.9 | 5/5 + 8f | FP16:FP32=4.16x, PCIe=12.4GB/s |
| RTX 5070 | Blackwell sm_12.0 | 5/5 + 8f | FP16:FP32=2.92x, PCIe=26.7GB/s |
| Tesla M40 | Maxwell sm_5.2 | 5/5 + 8f | FP16:FP32=0.91x, PCIe=10.6GB/s |
| AMD Radeon 780M | RDNA3 iGPU | 4/4 (Vulkan) + 5/5 (iGPU) | ts=10.0ns, 11 mem types |

## Spoof Detection

The `gpu_spoof_test.py` module tests claims against 9 GPU profiles. Results on RTX 4070 claiming to be each:

| Claimed | Violations | Caught? |
|---------|-----------|---------|
| H100 SXM | 5 | Yes |
| A100 SXM | 5 | Yes |
| V100 SXM | 4 | Yes |
| RTX 4090 | 3 | Yes |
| RTX 5070 | 5 | Yes |
| MI300X | 4 | Yes |
| L40S | 3 | Yes |
| T4 | 4 | Yes |

Minimum 3 violations even for same-architecture spoofs.

## Reference

- [RIP-0308: Proof of Physical AI](../rips/docs/RIP-0308-proof-of-physical-ai.md)
- [DOI: 10.5281/zenodo.19442753](https://doi.org/10.5281/zenodo.19442753)
- Khattak & Mikaitis, "Accurate Models of NVIDIA Tensor Cores" (arXiv:2512.07004)
