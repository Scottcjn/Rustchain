#!/usr/bin/env python3
"""
GPU SRAM PUF (Physical Unclonable Function) Test
=================================================

Based on: Aubel, Bernstein, Niederhagen — "Investigating SRAM PUFs in
Large CPUs and GPUs" (SPACE 2015).

NVIDIA GPU shared memory (SRAM) has preferred bit states from manufacturing
variance in transistor threshold voltage. Each SM's shared memory retains
a unique power-on initialization pattern. This script tests whether
modern GPUs (Ampere, Ada Lovelace, Blackwell) still expose this behavior
or whether the CUDA driver now zeroes shared memory before use.

Technique:
  1. Allocate GPU shared memory WITHOUT initializing it
  2. Read the raw values — they reflect SRAM cell preferred states
  3. Repeat to measure intra-chip stability (good PUF: >90%)
  4. Hash the stable pattern for a chip-unique fingerprint

Usage:
  python3 gpu_sram_puf.py                  # 10 runs, default shared sizes
  python3 gpu_sram_puf.py --runs 50        # 50 runs for better statistics
  python3 gpu_sram_puf.py --device 1       # Use GPU 1
  python3 gpu_sram_puf.py --sizes 1024 4096 16384 49152
"""

import argparse
import hashlib
import os
import sys
import time
from collections import Counter

import numpy as np

# ---------------------------------------------------------------------------
# CUDA kernel source — reads uninitialized shared memory
# ---------------------------------------------------------------------------

CUDA_SRC = r'''
#include <torch/extension.h>
#include <cuda_runtime.h>
#include <cstdint>

// ---------------------------------------------------------------------------
// Kernel: each block reads its SM's uninitialized shared memory.
// We deliberately do NOT write to smem before reading — the values
// reflect the SRAM cell's preferred power-on state.
// ---------------------------------------------------------------------------
__global__ void read_sram_puf_kernel(
    int32_t* __restrict__ output,
    int shared_size_ints
) {
    extern __shared__ int32_t smem[];

    const int tid = threadIdx.x;
    const int bid = blockIdx.x;

    // Read uninitialized shared memory
    if (tid < shared_size_ints) {
        output[bid * shared_size_ints + tid] = smem[tid];
    }
}

// ---------------------------------------------------------------------------
// Second kernel: tries to "dirty" shared memory with a known pattern,
// then a DIFFERENT kernel (read_sram_puf_kernel) reads it fresh.
// This helps distinguish "residual from previous kernel" vs "SRAM PUF".
// ---------------------------------------------------------------------------
__global__ void dirty_sram_kernel(int shared_size_ints) {
    extern __shared__ int32_t smem[];
    const int tid = threadIdx.x;
    if (tid < shared_size_ints) {
        smem[tid] = 0xDEADBEEF;
    }
    __syncthreads();
    // We write but never read — the point is to leave a known residue
    // so the next read_sram_puf_kernel can detect whether it sees
    // 0xDEADBEEF (residual) or something else (true SRAM state).
}

// ---------------------------------------------------------------------------
// Torch-callable wrappers
// ---------------------------------------------------------------------------

torch::Tensor read_sram_puf(int num_blocks, int shared_size_bytes, bool prefer_shared) {
    const int shared_size_ints = shared_size_bytes / 4;

    // Optionally prefer shared memory over L1 cache
    if (prefer_shared) {
        cudaDeviceSetCacheConfig(cudaFuncCachePreferShared);
    } else {
        cudaDeviceSetCacheConfig(cudaFuncCachePreferNone);
    }

    auto output = torch::zeros({num_blocks, shared_size_ints},
                               torch::dtype(torch::kInt32).device(torch::kCUDA));

    read_sram_puf_kernel<<<num_blocks, shared_size_ints, shared_size_bytes>>>(
        output.data_ptr<int32_t>(),
        shared_size_ints
    );

    cudaDeviceSynchronize();
    return output;
}

torch::Tensor read_sram_after_dirty(int num_blocks, int shared_size_bytes) {
    const int shared_size_ints = shared_size_bytes / 4;

    cudaDeviceSetCacheConfig(cudaFuncCachePreferShared);

    // Step 1: dirty every SM's shared memory with 0xDEADBEEF
    dirty_sram_kernel<<<num_blocks, shared_size_ints, shared_size_bytes>>>(
        shared_size_ints
    );
    cudaDeviceSynchronize();

    // Step 2: read shared memory in a DIFFERENT kernel launch
    auto output = torch::zeros({num_blocks, shared_size_ints},
                               torch::dtype(torch::kInt32).device(torch::kCUDA));

    read_sram_puf_kernel<<<num_blocks, shared_size_ints, shared_size_bytes>>>(
        output.data_ptr<int32_t>(),
        shared_size_ints
    );
    cudaDeviceSynchronize();
    return output;
}
'''

# Python wrapper declarations for torch binding
CUDA_DECL = r'''
torch::Tensor read_sram_puf(int num_blocks, int shared_size_bytes, bool prefer_shared);
torch::Tensor read_sram_after_dirty(int num_blocks, int shared_size_bytes);
'''


def compile_cuda_module():
    """Compile the CUDA kernel inline via torch.utils.cpp_extension."""
    from torch.utils.cpp_extension import load_inline

    print("[*] Compiling CUDA SRAM PUF kernel (first run may take ~30s)...")
    t0 = time.time()

    # Detect GPU arch for nvcc flags
    import torch
    major, minor = torch.cuda.get_device_capability()
    arch_flag = f"-gencode=arch=compute_{major}{minor},code=sm_{major}{minor}"

    cpp_decl = (
        "#include <torch/extension.h>\n"
        "torch::Tensor read_sram_puf(int num_blocks, int shared_size_bytes, bool prefer_shared);\n"
        "torch::Tensor read_sram_after_dirty(int num_blocks, int shared_size_bytes);\n"
    )

    module = load_inline(
        name="sram_puf",
        cpp_sources=[cpp_decl],
        cuda_sources=[CUDA_SRC],
        functions=["read_sram_puf", "read_sram_after_dirty"],
        extra_cuda_cflags=["-O0", arch_flag],  # -O0: avoid optimizer removing reads
        verbose=False,
    )
    elapsed = time.time() - t0
    print(f"[+] Kernel compiled in {elapsed:.1f}s (arch: sm_{major}{minor})")
    return module


def bits_from_array(arr: np.ndarray) -> np.ndarray:
    """Convert int32 array to bit array."""
    # View as uint8, then unpack bits
    raw = arr.view(np.uint8)
    return np.unpackbits(raw)


def hamming_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Fractional Hamming distance between two bit arrays."""
    if len(a) != len(b):
        n = min(len(a), len(b))
        a, b = a[:n], b[:n]
    diff = np.sum(a != b)
    return diff / len(a)


def analyze_bias(bits: np.ndarray) -> dict:
    """Analyze bit bias — a true PUF has non-uniform 0/1 distribution."""
    total = len(bits)
    ones = int(np.sum(bits))
    zeros = total - ones
    ratio_ones = ones / total if total else 0.0
    return {
        "total_bits": total,
        "ones": ones,
        "zeros": zeros,
        "bias_ones": ratio_ones,
        "bias_zeros": 1.0 - ratio_ones,
        "uniform": abs(ratio_ones - 0.5) < 0.01,  # within 1% of 50/50
    }


def run_puf_test(module, num_blocks, shared_bytes, num_runs, prefer_shared=True):
    """Run the SRAM PUF read multiple times and analyze."""
    import torch

    shared_ints = shared_bytes // 4
    all_readings = []

    for i in range(num_runs):
        # Clear GPU caches between runs by allocating/freeing memory
        torch.cuda.empty_cache()

        result = module.read_sram_puf(num_blocks, shared_bytes, prefer_shared)
        data = result.cpu().numpy()  # shape: [num_blocks, shared_ints]
        all_readings.append(data)

    return np.array(all_readings)  # shape: [num_runs, num_blocks, shared_ints]


def run_dirty_test(module, num_blocks, shared_bytes, num_runs):
    """Run dirty+read test to check for residual vs true SRAM state."""
    import torch

    all_readings = []
    for i in range(num_runs):
        torch.cuda.empty_cache()
        result = module.read_sram_after_dirty(num_blocks, shared_bytes)
        data = result.cpu().numpy()
        all_readings.append(data)

    return np.array(all_readings)


def analyze_readings(readings: np.ndarray, label: str):
    """Analyze a set of SRAM readings."""
    num_runs, num_blocks, shared_ints = readings.shape
    total_bytes = num_blocks * shared_ints * 4

    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"  {num_runs} runs, {num_blocks} blocks, "
          f"{shared_ints*4} bytes/block ({shared_ints*4*8} bits/block)")
    print(f"{'='*70}")

    # --- Check if all zeros (driver cleared SRAM) ---
    all_zero = np.all(readings == 0)
    nonzero_count = np.count_nonzero(readings)
    total_ints = readings.size

    if all_zero:
        print("\n  *** ALL VALUES ARE ZERO ***")
        print("  The CUDA driver is zeroing shared memory before use.")
        print("  SRAM PUF is NOT extractable on this GPU/driver combination.")
        print("  This is a significant finding for modern GPU security research.")
        return {"all_zero": True, "extractable": False}

    # Check for 0xDEADBEEF residual (from dirty test)
    deadbeef_val = np.int32(np.uint32(0xDEADBEEF))
    deadbeef_count = np.sum(readings == deadbeef_val)
    deadbeef_frac = deadbeef_count / total_ints

    print(f"\n  Non-zero values: {nonzero_count}/{total_ints} "
          f"({100*nonzero_count/total_ints:.2f}%)")

    if deadbeef_frac > 0.5:
        print(f"  *** 0xDEADBEEF residual: {100*deadbeef_frac:.1f}% ***")
        print("  Shared memory retains values from previous kernel launch.")
        print("  This is residual data, NOT a true SRAM PUF signal.")

    # --- Per-block analysis ---
    print(f"\n  Per-Block Analysis (first 8 blocks shown):")
    print(f"  {'Block':>6} | {'Hash (run 0)':>20} | {'Nonzero%':>9} | {'Unique vals':>11}")
    print(f"  {'-'*6}-+-{'-'*20}-+-{'-'*9}-+-{'-'*11}")

    block_hashes_run0 = []
    for b in range(min(num_blocks, 8)):
        block_data = readings[0, b, :]
        h = hashlib.sha256(block_data.tobytes()).hexdigest()[:16]
        block_hashes_run0.append(h)
        nz = np.count_nonzero(block_data)
        nz_pct = 100 * nz / shared_ints
        uniq = len(np.unique(block_data))
        print(f"  {b:>6} | {h:>20} | {nz_pct:>8.1f}% | {uniq:>11}")

    # --- Bit bias ---
    first_run_bits = bits_from_array(readings[0].flatten())
    bias = analyze_bias(first_run_bits)
    print(f"\n  Bit Bias (run 0):")
    print(f"    Total bits:  {bias['total_bits']:,}")
    print(f"    Ones:        {bias['ones']:,} ({100*bias['bias_ones']:.2f}%)")
    print(f"    Zeros:       {bias['zeros']:,} ({100*bias['bias_zeros']:.2f}%)")
    if bias['uniform']:
        print(f"    Distribution: UNIFORM (within 1% of 50/50)")
        print(f"    -> Weak PUF signal (random or driver-initialized)")
    else:
        deviation = abs(bias['bias_ones'] - 0.5) * 100
        print(f"    Distribution: BIASED ({deviation:.2f}% deviation from 50/50)")
        print(f"    -> Potential PUF signal (preferred bit states detected)")

    # --- Intra-chip stability (Hamming distance between runs) ---
    if num_runs >= 2:
        print(f"\n  Intra-Chip Stability (run-to-run consistency):")
        distances = []
        for i in range(1, num_runs):
            bits_0 = bits_from_array(readings[0].flatten())
            bits_i = bits_from_array(readings[i].flatten())
            hd = hamming_distance(bits_0, bits_i)
            distances.append(hd)

        avg_hd = np.mean(distances)
        min_hd = np.min(distances)
        max_hd = np.max(distances)
        stability = (1.0 - avg_hd) * 100

        print(f"    Avg Hamming distance:  {avg_hd:.6f} ({avg_hd*100:.4f}%)")
        print(f"    Min Hamming distance:  {min_hd:.6f}")
        print(f"    Max Hamming distance:  {max_hd:.6f}")
        print(f"    Stability:            {stability:.2f}%")

        if stability > 99.9:
            print(f"    -> PERFECT stability (likely driver-zeroed or constant)")
        elif stability > 90:
            print(f"    -> GOOD PUF ({stability:.1f}% stable — usable fingerprint)")
        elif stability > 70:
            print(f"    -> MODERATE PUF ({stability:.1f}% — needs error correction)")
        elif stability > 50:
            print(f"    -> WEAK PUF ({stability:.1f}% — high noise)")
        else:
            print(f"    -> NOT a PUF ({stability:.1f}% — essentially random)")
    else:
        stability = None

    # --- Cross-block uniqueness ---
    if num_blocks >= 2:
        print(f"\n  Cross-Block Uniqueness (inter-SM difference):")
        block_distances = []
        for i in range(min(num_blocks - 1, 16)):
            bits_a = bits_from_array(readings[0, i, :])
            bits_b = bits_from_array(readings[0, i + 1, :])
            hd = hamming_distance(bits_a, bits_b)
            block_distances.append(hd)

        avg_block_hd = np.mean(block_distances)
        print(f"    Avg inter-block Hamming distance: {avg_block_hd:.6f} "
              f"({avg_block_hd*100:.4f}%)")
        if avg_block_hd < 0.01:
            print(f"    -> All blocks identical (no per-SM uniqueness)")
        elif abs(avg_block_hd - 0.5) < 0.05:
            print(f"    -> ~50% difference (good inter-SM uniqueness)")
        else:
            print(f"    -> {avg_block_hd*100:.1f}% difference between SMs")

    # --- Overall fingerprint ---
    # Use the majority-vote bit across all runs for each position
    if num_runs >= 3:
        all_bits = np.array([bits_from_array(readings[r].flatten())
                             for r in range(num_runs)])
        majority = (np.sum(all_bits, axis=0) > (num_runs / 2)).astype(np.uint8)
        fingerprint = hashlib.sha256(majority.tobytes()).hexdigest()
    else:
        fingerprint = hashlib.sha256(readings[0].tobytes()).hexdigest()

    print(f"\n  Overall SRAM PUF Fingerprint: {fingerprint}")

    # --- Value distribution ---
    flat = readings[0].flatten()
    unique_vals = np.unique(flat)
    print(f"\n  Value Distribution (run 0):")
    print(f"    Unique int32 values: {len(unique_vals)}")
    if len(unique_vals) <= 10:
        for v in unique_vals:
            count = np.sum(flat == v)
            print(f"      0x{np.uint32(v):08X}: {count} occurrences "
                  f"({100*count/len(flat):.1f}%)")
    else:
        # Show top 5 most common
        vals, counts = np.unique(flat, return_counts=True)
        top_idx = np.argsort(-counts)[:5]
        print(f"    Top 5 values:")
        for idx in top_idx:
            v, c = vals[idx], counts[idx]
            print(f"      0x{np.uint32(v):08X}: {c} occurrences "
                  f"({100*c/len(flat):.1f}%)")

    # Determine if this is a true PUF signal vs residual/contamination
    # A true PUF: non-zero, not dominated by 0xDEADBEEF, has varied values
    is_residual = deadbeef_frac > 0.1  # >10% DEADBEEF = contamination
    is_puf = (not all_zero
              and not is_residual
              and (stability is None or stability > 70)
              and len(unique_vals) > 2)  # True PUF has many distinct values

    return {
        "all_zero": all_zero,
        "nonzero_frac": nonzero_count / total_ints,
        "bias_ones": bias['bias_ones'],
        "stability": stability,
        "fingerprint": fingerprint,
        "extractable": is_puf,
        "deadbeef_frac": deadbeef_frac,
        "is_residual": is_residual,
        "unique_values": len(unique_vals),
    }


def main():
    parser = argparse.ArgumentParser(
        description="GPU SRAM PUF (Physical Unclonable Function) Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--runs", type=int, default=10,
                        help="Number of repeated reads for stability measurement")
    parser.add_argument("--device", type=int, default=0,
                        help="CUDA device index")
    parser.add_argument("--blocks", type=int, default=64,
                        help="Number of thread blocks (ideally >= SM count)")
    parser.add_argument("--sizes", type=int, nargs="+",
                        default=[1024, 4096, 16384, 49152],
                        help="Shared memory sizes to test in bytes")
    args = parser.parse_args()

    import torch

    # Select device
    if not torch.cuda.is_available():
        print("[!] CUDA not available. Exiting.")
        sys.exit(1)

    torch.cuda.set_device(args.device)
    dev = torch.cuda.get_device_properties(args.device)
    major, minor = torch.cuda.get_device_capability(args.device)

    print("=" * 70)
    print("  GPU SRAM PUF Test")
    print("  Based on Aubel, Bernstein, Niederhagen (SPACE 2015)")
    print("=" * 70)
    print(f"  GPU:            {dev.name}")
    print(f"  Compute Cap:    sm_{major}{minor}")
    print(f"  SMs:            {dev.multi_processor_count}")
    shared_per_sm = getattr(dev, 'shared_memory_per_multiprocessor',
                           getattr(dev, 'max_shared_memory_size_per_multiprocessor', 0))
    shared_per_blk = getattr(dev, 'shared_memory_per_block',
                             getattr(dev, 'max_shared_memory_size_per_block', 0))
    print(f"  Shared/SM:      {shared_per_sm} bytes")
    if shared_per_blk:
        print(f"  Shared/Block:   {shared_per_blk} bytes")
    print(f"  CUDA Driver:    {torch.version.cuda}")
    print(f"  PyTorch:        {torch.__version__}")
    print(f"  Runs:           {args.runs}")
    print(f"  Blocks:         {args.blocks}")
    print(f"  Shared sizes:   {args.sizes}")

    # Compile
    module = compile_cuda_module()

    results = {}

    # Compute effective sizes for each requested size
    test_sizes = []
    for sz in args.sizes:
        if sz % 4 != 0:
            print(f"\n[!] Skipping {sz} bytes (not a multiple of 4)")
            continue
        ints_per_block = sz // 4
        if ints_per_block > 1024:
            print(f"\n[!] {sz} bytes = {ints_per_block} ints > 1024 threads/block.")
            print(f"    Capping to 1024 threads (reading first 4096 bytes of {sz}).")
            effective_bytes = 4096
        else:
            effective_bytes = sz
        test_sizes.append((sz, effective_bytes))

    # --- PHASE 1: All CLEAN reads first (before any dirty writes) ---
    print("\n" + "-" * 70)
    print("  PHASE 1: Clean reads (uncontaminated shared memory)")
    print("-" * 70)

    for sz, effective_bytes in test_sizes:
        label = f"Shared Memory = {sz} bytes (reading {effective_bytes} bytes)"
        print(f"\n[*] Running PUF read: {label}")
        readings = run_puf_test(module, args.blocks, effective_bytes,
                                args.runs, prefer_shared=True)
        r = analyze_readings(readings, f"[CLEAN READ] {label}")
        results[f"clean_{sz}"] = r

    # --- PHASE 2: Dirty+read tests (to measure residual behavior) ---
    print("\n" + "-" * 70)
    print("  PHASE 2: Dirty+read tests (residual behavior analysis)")
    print("-" * 70)

    for sz, effective_bytes in test_sizes:
        label = f"Shared Memory = {sz} bytes (reading {effective_bytes} bytes)"
        print(f"\n[*] Running dirty+read test: {label}")
        dirty_readings = run_dirty_test(module, args.blocks, effective_bytes,
                                         args.runs)
        r2 = analyze_readings(dirty_readings,
                              f"[DIRTY+READ] {label} (after 0xDEADBEEF write)")
        results[f"dirty_{sz}"] = r2

    # --- Summary ---
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)

    any_extractable = False
    for key, r in results.items():
        tag = "CLEAN" if key.startswith("clean") else "DIRTY"
        sz = key.split("_", 1)[1]

        if r.get("extractable"):
            status = "PUF EXTRACTABLE"
            any_extractable = True
        elif r.get("is_residual"):
            status = "RESIDUAL (not PUF)"
        elif r.get("all_zero"):
            status = "ZEROED BY DRIVER"
        else:
            status = "NOT EXTRACTABLE"

        print(f"  [{tag:5s}] {sz:>6s}B: "
              f"nonzero={100*r.get('nonzero_frac', 0):.1f}% "
              f"bias={r.get('bias_ones', 0):.4f} "
              f"stability={r.get('stability', 0):.1f}% "
              f"deadbeef={100*r.get('deadbeef_frac', 0):.1f}% "
              f"unique_vals={r.get('unique_values', 0)} "
              f"-> {status}")

    print()
    if any_extractable:
        fp = None
        for key, r in results.items():
            if r.get("extractable") and key.startswith("clean"):
                fp = r.get("fingerprint")
                break
        print(f"  SRAM PUF IS EXTRACTABLE on this GPU.")
        if fp:
            print(f"  Best fingerprint: {fp}")
        print(f"  This GPU's shared memory retains preferred bit states.")
    else:
        print(f"  SRAM PUF is NOT extractable on this GPU.")
        print(f"  The CUDA driver appears to zero or randomize shared memory.")
        print(f"  This is consistent with NVIDIA's security hardening since ~CUDA 11.")
        print()
        print(f"  Possible reasons:")
        print(f"    1. Driver zeros shared memory between kernel launches (most likely)")
        print(f"    2. Hardware scrubs SRAM on allocation (Ada Lovelace feature)")
        print(f"    3. Shared memory is allocated from L1 cache (volatile)")

    # Check for residual behavior (dirty reads show 0xDEADBEEF)
    any_residual = any(r.get("deadbeef_frac", 0) > 0.5
                       for k, r in results.items() if k.startswith("dirty"))
    if any_residual:
        print(f"\n  NOTE: Dirty+read tests show 0xDEADBEEF residual.")
        print(f"  Shared memory DOES retain values between kernel launches,")
        print(f"  but the initial state is zeroed (no PUF pattern).")
    elif not any_extractable:
        any_dirty_zero = all(r.get("all_zero", True)
                             for k, r in results.items() if k.startswith("dirty"))
        if any_dirty_zero:
            print(f"\n  NOTE: Even after writing 0xDEADBEEF, the next read is zeroed.")
            print(f"  The driver aggressively clears shared memory between launches.")

    print()


if __name__ == "__main__":
    main()
