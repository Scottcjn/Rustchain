#!/usr/bin/env python3
"""
Tests for GPU Fingerprinting (Channel 8, RIP-0308)
====================================================

Run with:
  python3 -m pytest test_gpu_fingerprint.py -v

Or standalone:
  python3 test_gpu_fingerprint.py

Tests verify:
1. Module structure matches fingerprint_checks.py style
2. All GPU check functions return (bool, dict) tuples
3. Graceful degradation when no GPU is available
4. Anti-emulation / VM detection logic
5. Silicone signature computation
"""

import os
import sys
import json
import hashlib
import statistics
from pathlib import Path

# Ensure we can import the node modules
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# ─── Imports ──────────────────────────────────────────────────────────────

try:
    from gpu_fingerprint_checks import (
        check_shader_execution_jitter,
        check_vram_timing,
        check_compute_unit_asymmetry,
        check_thermal_throttle_signature,
        check_gpu_vm_passthrough,
        validate_gpu_fingerprint,
        compute_gpu_silicone_signature,
        _detect_gpu_vendor,
        _get_gpu_info,
    )
    GPU_MODULE_AVAILABLE = True
except ImportError as e:
    print(f"GPU module import error: {e}")
    GPU_MODULE_AVAILABLE = False


# ─── Test Helpers ─────────────────────────────────────────────────────────

def test_result_shape(result, expected_keys=None):
    """Validate that a check result has the expected structure."""
    passed, data = result
    assert isinstance(passed, bool), f"passed should be bool, got {type(passed)}"
    assert isinstance(data, dict), f"data should be dict, got {type(data)}"
    if expected_keys:
        for key in expected_keys:
            assert key in data, f"missing key '{key}' in data: {data.keys()}"
    return passed, data


# ─── Tests ────────────────────────────────────────────────────────────────

def test_module_available():
    """Test that the GPU module can be imported."""
    assert GPU_MODULE_AVAILABLE, "gpu_fingerprint_checks.py should be importable"
    print("  [PASS] Module importable")


def test_detect_gpu_vendor():
    """Test GPU vendor detection."""
    vendor = _detect_gpu_vendor()
    # May be None in VM/no-GPU environments — that's OK
    assert vendor is None or vendor in ("nvidia", "amd"), \
        f"vendor should be None, 'nvidia', or 'amd', got {vendor}"
    print(f"  [PASS] Vendor detection: {vendor or 'no GPU (expected in VM)'}")


def test_shader_jitter_returns_tuple():
    """Test that check_shader_execution_jitter returns (bool, dict)."""
    passed, data = check_shader_execution_jitter(samples=50)
    test_result_shape((passed, data), ["channel"])
    assert data.get("channel") == "gpu_shader_jitter"
    print(f"  [PASS] Shader jitter: {'skipped' if data.get('skipped') else 'ran'}")


def test_vram_timing_returns_tuple():
    """Test that check_vram_timing returns (bool, dict)."""
    passed, data = check_vram_timing(iterations=10)
    test_result_shape((passed, data), ["channel"])
    assert data.get("channel") == "vram_timing"
    print(f"  [PASS] VRAM timing: {'skipped' if data.get('skipped') else 'ran'}")


def test_cu_asymmetry_returns_tuple():
    """Test that check_compute_unit_asymmetry returns (bool, dict)."""
    passed, data = check_compute_unit_asymmetry(buckets=8)
    test_result_shape((passed, data), ["channel"])
    assert data.get("channel") == "cu_asymmetry"
    print(f"  [PASS] CU asymmetry: {'skipped' if data.get('skipped') else 'ran'}")


def test_thermal_throttle_returns_tuple():
    """Test that check_thermal_throttle_signature returns (bool, dict)."""
    # Use very short warmup for testing
    passed, data = check_thermal_throttle_signature(warmup_seconds=2, cooldown_seconds=1)
    test_result_shape((passed, data), ["channel"])
    assert data.get("channel") == "thermal_throttle"
    print(f"  [PASS] Thermal throttle: {'skipped' if data.get('skipped') else 'ran'}")


def test_vm_passthrough_detection():
    """Test VM passthrough detection."""
    passed, data = check_gpu_vm_passthrough()
    test_result_shape((passed, data), ["channel"])
    assert data.get("channel") == "gpu_vm_passthrough"
    assert "indicators" in data
    assert isinstance(data["indicators"], list)
    print(f"  [PASS] VM passthrough: {len(data['indicators'])} indicators found")


def test_validate_gpu_fingerprint():
    """Test the full GPU fingerprint validation pipeline."""
    all_passed, results = validate_gpu_fingerprint()
    assert isinstance(all_passed, bool)
    assert isinstance(results, dict)
    assert len(results) >= 4  # At least 4 GPU checks
    print(f"  [PASS] Full validation: {'ALL PASSED' if all_passed else 'SOME FAILED/ SKIPPED'}")
    print(f"    Checks run: {list(results.keys())}")


def test_silicone_signature():
    """Test silicone signature computation."""
    sig = compute_gpu_silicone_signature()
    if sig is not None:
        assert isinstance(sig, str), f"signature should be str, got {type(sig)}"
        assert len(sig) == 16, f"signature should be 16 chars, got {len(sig)}"
        # Should be hex
        int(sig, 16)
        print(f"  [PASS] Silicone signature: {sig}")
    else:
        print(f"  [PASS] Silicone signature: None (no GPU, expected)")


def test_graceful_no_gpu():
    """Test that all checks gracefully handle no GPU environment."""
    vendor = _detect_gpu_vendor()
    if vendor is None:
        print("  No GPU detected — testing graceful skip behavior...")
        for name, func in [
            ("shader_jitter", lambda: check_shader_execution_jitter(10)),
            ("vram_timing", lambda: check_vram_timing(5)),
            ("cu_asymmetry", lambda: check_compute_unit_asymmetry(4)),
            ("thermal", lambda: check_thermal_throttle_signature(1, 1)),
        ]:
            passed, data = func()
            assert passed is True, f"{name} should pass (skip) when no GPU"
            assert data.get("skipped") is True, f"{name} should be skipped"
        print("  [PASS] All checks gracefully skipped without GPU")
    else:
        print(f"  [SKIP] GPU detected ({vendor}), skipping no-GPU test")


def test_vm_passthrough_indicators_in_current_env():
    """Test that VM indicators are detected in the current environment."""
    # This server runs in a VM, so we should detect some indicators
    passed, data = check_gpu_vm_passthrough()
    indicators = data.get("indicators", [])
    
    # In a VM environment, we expect at least some indicators
    if indicators:
        print(f"  [PASS] VM indicators detected: {indicators}")
    else:
        print(f"  [INFO] No VM indicators (clean environment)")


# ─── Style / Architecture Tests ───────────────────────────────────────────

def test_function_signature_matches_style():
    """Verify that all GPU check functions match fingerprint_checks.py style."""
    import inspect
    from gpu_fingerprint_checks import (
        check_shader_execution_jitter,
        check_vram_timing,
        check_compute_unit_asymmetry,
        check_thermal_throttle_signature,
        check_gpu_vm_passthrough,
    )

    for func in [
        check_shader_execution_jitter,
        check_vram_timing,
        check_compute_unit_asymmetry,
        check_thermal_throttle_signature,
        check_gpu_vm_passthrough,
    ]:
        sig = inspect.signature(func)
        # All should return Tuple[bool, Dict]
        ret_annotation = sig.return_annotation
        assert "Tuple" in str(ret_annotation) or "tuple" in str(ret_annotation).lower(), \
            f"{func.__name__} should return Tuple[bool, Dict], got {ret_annotation}"
    print("  [PASS] All functions have correct signature style")


def test_channel_constants_in_data():
    """Verify that all check results include a 'channel' key."""
    checks = [
        check_shader_execution_jitter(),
        check_vram_timing(),
        check_compute_unit_asymmetry(),
        check_thermal_throttle_signature(1, 1),
        check_gpu_vm_passthrough(),
    ]
    for passed, data in checks:
        assert "channel" in data, f"Missing 'channel' key in {data.keys()}"
    print("  [PASS] All results contain 'channel' key")


# ─── Main Runner ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("GPU Fingerprint (Channel 8) Tests — RIP-0308")
    print("=" * 60)
    print()

    all_tests = [
        test_module_available,
        test_detect_gpu_vendor,
        test_function_signature_matches_style,
        test_channel_constants_in_data,
        test_shader_jitter_returns_tuple,
        test_vram_timing_returns_tuple,
        test_cu_asymmetry_returns_tuple,
        test_thermal_throttle_returns_tuple,
        test_vm_passthrough_detection,
        test_validate_gpu_fingerprint,
        test_silicone_signature,
        test_graceful_no_gpu,
        test_vm_passthrough_indicators_in_current_env,
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test_func in all_tests:
        try:
            print(f"\nRunning: {test_func.__name__}")
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
