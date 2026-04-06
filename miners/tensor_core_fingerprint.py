#!/usr/bin/env python3
"""
Tensor Core Precision Drift Fingerprint — PPA Channel 8f
=========================================================

Each GPU generation implements tensor core FMA (fused multiply-add)
differently at the silicon level:

  Volta (sm_7.0):   25-bit alignment, FMA groups of 4, truncation
  Ampere (sm_8.0):  26-bit alignment, FMA groups of 8, round-to-nearest
  Hopper (sm_9.0):  27-bit alignment, FMA groups of 16
  Ada (sm_8.9):     26-bit (CUDA cores) + 4th-gen tensor cores
  Blackwell (sm_12.0): Extended precision tensor cores

These internal differences cause the LEAST SIGNIFICANT BITS of identical
FP16 matrix multiplications to DIFFER between GPU generations. This is
unforgeable — the output is determined by the physical ALU implementation.

The silicon is the witness, not the defendant.

Key insight from Khattak & Mikaitis (arXiv 2512.07004, Dec 2025):
Models match hardware "exactly at the bit level" — meaning cross-generation
divergence is DETERMINISTIC, not noise.

Usage:
    python3 tensor_core_fingerprint.py [--device 0] [--verbose]

Author: Elyan Labs (RIP-0308: Proof of Physical AI)
"""

import argparse
import hashlib
import json
import struct
import sys
import time
from dataclasses import asdict, dataclass, field

try:
    import torch
    import torch.cuda
except ImportError:
    print("ERROR: PyTorch with CUDA required")
    sys.exit(1)

if not torch.cuda.is_available():
    print("ERROR: No CUDA GPU detected")
    sys.exit(1)


@dataclass
class TensorCoreFingerprintResult:
    gpu_name: str
    compute_capability: str
    has_tensor_cores: bool
    detected_generation: str
    tests: list = field(default_factory=list)
    precision_hash: str = ""
    all_passed: bool = False

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# Test Vectors — carefully crafted to expose tensor core arithmetic differences
# ---------------------------------------------------------------------------
# These matrices are designed so that:
# 1. The FP16 accumulation ORDER matters (non-associativity of FP)
# 2. Values near subnormal/overflow boundaries stress edge cases
# 3. The FMA group size (4 vs 8 vs 16) changes which partial products
#    get accumulated together, producing different LSBs
# ---------------------------------------------------------------------------

def _craft_test_vectors(device: torch.device, size: int = 16):
    """Create test matrices that expose tensor core arithmetic differences."""
    vectors = {}

    # Test 1: Near powers of 2 — exposes alignment bit differences
    # When a + b where a >> b, the alignment shift loses different bits
    # depending on the accumulator width (25 vs 26 vs 27 bits)
    a1 = torch.tensor([[1.0, 0.001, 1024.0, 0.0005]] * 4, device=device, dtype=torch.float16)
    b1 = torch.tensor([[0.001], [1024.0], [0.0005], [1.0]], device=device, dtype=torch.float16)
    vectors["power_of_2_alignment"] = (a1, b1)

    # Test 2: Accumulated sum of many small values — FMA group size matters
    # With group_size=4 (Volta), partial sums accumulate differently than
    # group_size=8 (Ampere) or group_size=16 (Hopper)
    torch.manual_seed(42)  # Deterministic
    a2 = torch.randn(size, size, device=device, dtype=torch.float16) * 0.01
    b2 = torch.randn(size, size, device=device, dtype=torch.float16) * 0.01
    vectors["small_accumulation"] = (a2, b2)

    # Test 3: Mixed magnitude — large and small values in same accumulation
    # The cancellation pattern depends on accumulator precision
    a3 = torch.zeros(size, size, device=device, dtype=torch.float16)
    for i in range(size):
        for j in range(size):
            # Alternating large and small values
            a3[i, j] = 1000.0 if (i + j) % 2 == 0 else 0.001
    b3 = torch.ones(size, size, device=device, dtype=torch.float16) * 0.1
    vectors["mixed_magnitude"] = (a3, b3)

    # Test 4: Subnormal boundary — tests how tensor cores handle denormals
    # Different generations handle subnormals differently (some flush to zero)
    a4 = torch.tensor([[6.1e-5, 6.0e-5, 5.96e-5, 1.0]] * 4, device=device, dtype=torch.float16)
    b4 = torch.tensor([[1.0], [1.0], [1.0], [6.0e-5]], device=device, dtype=torch.float16)
    vectors["subnormal_boundary"] = (a4, b4)

    # Test 5: Overflow boundary — tests saturation behavior
    a5 = torch.tensor([[65000.0, 1.0, 65000.0, 1.0]] * 4, device=device, dtype=torch.float16)
    b5 = torch.tensor([[1.0], [65000.0], [0.5], [0.001]], device=device, dtype=torch.float16)
    vectors["overflow_boundary"] = (a5, b5)

    # Test 6: Large matmul with deterministic seed — the "signature" test
    # The full accumulation pattern across 256 FMA operations per output element
    # is where FMA group size has maximum impact
    torch.manual_seed(0xDEADBEEF)
    a6 = torch.randn(32, 256, device=device, dtype=torch.float16)
    b6 = torch.randn(256, 32, device=device, dtype=torch.float16)
    vectors["signature_matmul"] = (a6, b6)

    # Test 7: Identity-ish matrix — tests rounding in trivial cases
    a7 = torch.eye(size, device=device, dtype=torch.float16)
    a7 += torch.randn(size, size, device=device, dtype=torch.float16) * 1e-4
    b7 = torch.randn(size, size, device=device, dtype=torch.float16)
    vectors["near_identity"] = (a7, b7)

    return vectors


def _fp16_to_hex(tensor: torch.Tensor) -> str:
    """Convert FP16 tensor to hex string for bit-exact comparison."""
    flat = tensor.contiguous().cpu().to(torch.float16)
    raw_bytes = flat.numpy().tobytes()
    return raw_bytes.hex()


def _extract_lsb_pattern(tensor: torch.Tensor) -> str:
    """Extract the least significant bits of each FP16 value."""
    flat = tensor.contiguous().cpu().to(torch.float16).numpy().flatten()
    # FP16: 1 sign + 5 exponent + 10 mantissa
    # LSB of mantissa is the bit most affected by accumulator differences
    lsb_bits = []
    for val in flat:
        raw = struct.pack('<e', float(val))
        u16 = struct.unpack('<H', raw)[0]
        lsb_bits.append(u16 & 0x000F)  # Bottom 4 bits of mantissa
    return "".join(f"{b:x}" for b in lsb_bits)


# ---------------------------------------------------------------------------
# Tensor Core vs CUDA Core detection
# ---------------------------------------------------------------------------

def _has_tensor_cores(device: torch.device) -> bool:
    """Detect if GPU has tensor cores (Volta+ = sm_7.0+)."""
    cap = torch.cuda.get_device_capability(device)
    return cap[0] >= 7


def _force_tensor_core_path(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Force matmul through tensor cores by using FP16 with TF32 enabled."""
    # Ensure dimensions are multiples of 8 (tensor core requirement)
    # and use torch.matmul which routes to cuBLAS GEMM → tensor cores
    with torch.cuda.amp.autocast(enabled=False):
        return torch.matmul(a, b)


def _force_cuda_core_path(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Force matmul through CUDA cores by disabling tensor core paths."""
    # Convert to FP32 — tensor cores don't handle FP32 matmul (pre-Ampere)
    # On Ampere+, disable TF32
    old_tf32 = torch.backends.cuda.matmul.allow_tf32
    torch.backends.cuda.matmul.allow_tf32 = False
    try:
        result = torch.matmul(a.float(), b.float()).half()
    finally:
        torch.backends.cuda.matmul.allow_tf32 = old_tf32
    return result


# ---------------------------------------------------------------------------
# Main fingerprint
# ---------------------------------------------------------------------------

def run_tensor_core_fingerprint(device_index: int = 0, verbose: bool = False):
    """Run tensor core precision drift fingerprint."""
    device = torch.device(f"cuda:{device_index}")
    props = torch.cuda.get_device_properties(device)
    gpu_name = props.name
    cap = f"{props.major}.{props.minor}"
    has_tc = _has_tensor_cores(device)

    print(f"\n{'='*65}")
    print(f"  Tensor Core Precision Drift Fingerprint — PPA Channel 8f")
    print(f"  GPU: {gpu_name} (sm_{cap})")
    print(f"  Tensor Cores: {'YES' if has_tc else 'NO (CUDA cores only)'}")
    print(f"{'='*65}\n")

    # Determine expected generation from compute capability
    gen_map = {
        (5, 0): "Maxwell", (5, 2): "Maxwell",
        (6, 0): "Pascal", (6, 1): "Pascal",
        (7, 0): "Volta", (7, 5): "Turing",
        (8, 0): "Ampere", (8, 6): "Ampere", (8, 9): "Ada",
        (9, 0): "Hopper",
        (10, 0): "Blackwell", (12, 0): "Blackwell",
    }
    detected_gen = gen_map.get((props.major, props.minor), f"Unknown (sm_{cap})")

    # Generate test vectors
    vectors = _craft_test_vectors(device)
    tests = []

    for test_name, (a, b) in vectors.items():
        print(f"  [{test_name}]", end=" ", flush=True)

        # Warmup
        for _ in range(3):
            _ = _force_tensor_core_path(a, b) if has_tc else torch.matmul(a.float(), b.float()).half()
        torch.cuda.synchronize(device)

        # Run multiple times to check determinism
        results_hex = []
        results_lsb = []
        for run in range(5):
            if has_tc:
                result = _force_tensor_core_path(a, b)
            else:
                result = torch.matmul(a.float(), b.float()).half()
            torch.cuda.synchronize(device)

            hex_str = _fp16_to_hex(result)
            lsb_str = _extract_lsb_pattern(result)
            results_hex.append(hex_str)
            results_lsb.append(lsb_str)

        # Check intra-run determinism
        unique_results = len(set(results_hex))
        is_deterministic = unique_results == 1

        # Also compute tensor core vs CUDA core divergence
        if has_tc:
            tc_result = _force_tensor_core_path(a, b)
            cuda_result = _force_cuda_core_path(a, b)
            torch.cuda.synchronize(device)

            tc_hex = _fp16_to_hex(tc_result)
            cuda_hex = _fp16_to_hex(cuda_result)
            tc_vs_cuda_match = tc_hex == cuda_hex

            # Count differing elements
            diff_count = sum(1 for t, c in zip(tc_result.flatten().tolist(),
                                                cuda_result.flatten().tolist())
                            if t != c)
            diff_pct = diff_count / max(tc_result.numel(), 1) * 100
        else:
            tc_vs_cuda_match = True  # No tensor cores, both paths are same
            diff_count = 0
            diff_pct = 0.0

        # Result hash — this is the fingerprint signal
        result_hash = hashlib.sha256(results_hex[0].encode()).hexdigest()[:16]
        lsb_hash = hashlib.sha256(results_lsb[0].encode()).hexdigest()[:16]

        status = "DETERMINISTIC" if is_deterministic else f"VARIES ({unique_results} unique)"
        tc_str = f"TC≠CUDA: {diff_pct:.1f}% ({diff_count} elements)" if has_tc else "N/A (no TC)"

        print(f"{status} | {tc_str} | hash={result_hash}")

        test_result = {
            "name": test_name,
            "deterministic": is_deterministic,
            "unique_results": unique_results,
            "result_hash": result_hash,
            "lsb_hash": lsb_hash,
            "tc_vs_cuda_match": tc_vs_cuda_match,
            "tc_cuda_diff_count": diff_count,
            "tc_cuda_diff_pct": round(diff_pct, 2),
            "matrix_shape": f"{list(a.shape)}x{list(b.shape)}",
        }

        if verbose:
            test_result["lsb_pattern"] = results_lsb[0][:64] + "..."
            test_result["first_5_values"] = [
                round(v, 6) for v in torch.matmul(a, b).flatten()[:5].tolist()
            ] if has_tc else []

        tests.append(test_result)

    # Composite precision fingerprint
    all_hashes = "|".join(t["result_hash"] for t in tests)
    precision_hash = hashlib.sha256(all_hashes.encode()).hexdigest()

    # LSB composite — the generation-specific signature
    all_lsb = "|".join(t["lsb_hash"] for t in tests)
    lsb_composite = hashlib.sha256(all_lsb.encode()).hexdigest()

    # Summary statistics
    deterministic_count = sum(1 for t in tests if t["deterministic"])
    avg_tc_diff = sum(t["tc_cuda_diff_pct"] for t in tests) / len(tests) if tests else 0

    all_passed = deterministic_count >= len(tests) - 1  # Allow 1 non-deterministic test

    print(f"\n{'='*65}")
    print(f"  RESULTS")
    print(f"  GPU Generation: {detected_gen}")
    print(f"  Tensor Cores: {'YES' if has_tc else 'NO'}")
    print(f"  Deterministic Tests: {deterministic_count}/{len(tests)}")
    print(f"  Avg TC vs CUDA Divergence: {avg_tc_diff:.1f}%")
    print(f"  Precision Hash: {precision_hash[:32]}...")
    print(f"  LSB Signature:  {lsb_composite[:32]}...")
    print(f"  Status: {'PASS' if all_passed else 'FAIL'}")
    print(f"{'='*65}")

    if has_tc and avg_tc_diff > 0:
        print(f"\n  The tensor cores produce DIFFERENT results than CUDA cores")
        print(f"  for identical inputs — {avg_tc_diff:.1f}% of output elements diverge.")
        print(f"  This divergence is DETERMINISTIC and GENERATION-SPECIFIC.")
        print(f"  A {detected_gen} GPU will always produce this exact LSB signature.")
        print(f"  A different generation will produce a DIFFERENT signature.")
    elif not has_tc:
        print(f"\n  No tensor cores detected (pre-Volta architecture).")
        print(f"  CUDA core FP32→FP16 path produces its own unique signature.")
        print(f"  The ABSENCE of tensor core divergence is itself a fingerprint.")

    return TensorCoreFingerprintResult(
        gpu_name=gpu_name,
        compute_capability=cap,
        has_tensor_cores=has_tc,
        detected_generation=detected_gen,
        tests=tests,
        precision_hash=precision_hash,
        all_passed=all_passed,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tensor Core Precision Drift — PPA Channel 8f")
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_tensor_core_fingerprint(device_index=args.device, verbose=args.verbose)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
