"""Core verdict logic for SophiaCore Attestation Inspector.

Takes a hardware fingerprint dict and returns a structured verdict
with confidence score. No external LLM dependency — uses heuristics.
"""
import hashlib
import json
from typing import Dict, Any, Tuple
from enum import Enum


class Verdict(str, Enum):
    APPROVED = "APPROVED"
    CAUTIOUS = "CAUTIOUS"
    SUSPICIOUS = "SUSPICIOUS"
    REJECTED = "REJECTED"


def compute_fingerprint_hash(fingerprint: Dict[str, Any]) -> str:
    """Create a deterministic hash from fingerprint data for test_mode."""
    canonical = json.dumps(fingerprint, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def evaluate_fingerprint(fingerprint: Dict[str, Any], test_mode: bool = False) -> Tuple[Verdict, float, str]:
    """Evaluate a hardware fingerprint and return (verdict, confidence, reasoning).

    Args:
        fingerprint: Dict containing hardware metadata:
            - cpu_arch: str (e.g., "x86_64", "aarch64", "riscv64")
            - cpu_model: str (e.g., "Intel Xeon", "Apple M1")
            - cpu_cores: int
            - memory_gb: int
            - gpu_model: str or null
            - gpu_count: int
            - os: str (e.g., "Linux", "Darwin", "Windows")
            - has_tpm: bool
            - boot_mode: str (e.g., "UEFI", "BIOS", "secure")
            - rng_hardware: bool
            - enclave_support: bool
            -挖矿_duration_days: int
            - submitted_hash: str (previously submitted fingerprint hash)
        test_mode: If True, returns deterministic verdicts based on hash.

    Returns:
        Tuple of (Verdict, confidence_score 0.0-1.0, reasoning_string)
    """
    if test_mode:
        return _test_mode_verdict(fingerprint)

    # Real heuristic evaluation
    score = 0.0
    reasons = []

    # CPU architecture checks
    cpu_arch = fingerprint.get("cpu_arch", "")
    valid_arches = {"x86_64", "aarch64", "arm64", "riscv64"}
    if cpu_arch in valid_arches:
        score += 0.15
    else:
        reasons.append(f"Unknown CPU arch: {cpu_arch}")

    # CPU model sanity
    cpu_model = fingerprint.get("cpu_model", "").lower()
    if any(
        trusted in cpu_model
        for trusted in [
            "intel",
            "amd",
            "xeon",
            "core",
            "ryzen",
            "epyc",
            "apple",
            "m1",
            "m2",
            "m3",
            "m4",
            "cortex-a",
            "neoverse",
        ]
    ):
        score += 0.15
    else:
        reasons.append(f"Unrecognized CPU model: {cpu_model}")

    # Core count
    cores = fingerprint.get("cpu_cores", 0)
    if cores >= 8:
        score += 0.10
    elif cores >= 4:
        score += 0.05
    else:
        reasons.append(f"Low core count: {cores}")

    # Memory
    memory_gb = fingerprint.get("memory_gb", 0)
    if memory_gb >= 16:
        score += 0.10
    elif memory_gb >= 8:
        score += 0.05
    else:
        reasons.append(f"Low memory: {memory_gb}GB")

    # GPU
    gpu_count = fingerprint.get("gpu_count", 0)
    gpu_model = fingerprint.get("gpu_model", "").lower()
    if gpu_count > 0 and any(
        known in gpu_model
        for known in ["nvidia", "geforce", "rtx", "gtx", "amd", "radeon", "apple"]
    ):
        score += 0.10
    elif gpu_count > 0:
        score += 0.05
        reasons.append(f"Unknown GPU: {gpu_model}")

    # TPM and boot security
    if fingerprint.get("has_tpm"):
        score += 0.10
    else:
        reasons.append("No TPM detected")

    boot_mode = fingerprint.get("boot_mode", "").lower()
    if boot_mode in ("uefi", "secure", "secureboot"):
        score += 0.10
    elif boot_mode == "bios":
        reasons.append("Legacy BIOS boot mode")
        score -= 0.05
    else:
        reasons.append(f"Unknown boot mode: {boot_mode}")

    # Hardware RNG
    if fingerprint.get("rng_hardware"):
        score += 0.05
    else:
        reasons.append("No hardware RNG")

    # Enclave support
    if fingerprint.get("enclave_support"):
        score += 0.05

    # Mining duration (legitimate miners should have some history)
    duration = fingerprint.get("挖矿_duration_days", 0)
    if duration >= 30:
        score += 0.05
    elif duration == 0:
        reasons.append("New miner, no history")

    # Check for repeated fingerprint (potential clone detection)
    submitted_hash = fingerprint.get("submitted_hash", "")
    if submitted_hash:
        # If same hash submitted many times, could be duplicated hardware
        score += 0.00  # Placeholder for duplicate detection logic

    # Clamp score
    score = max(0.0, min(1.0, score))

    # Derive verdict from score
    if score >= 0.80:
        verdict = Verdict.APPROVED
    elif score >= 0.60:
        verdict = Verdict.CAUTIOUS
    elif score >= 0.40:
        verdict = Verdict.SUSPICIOUS
    else:
        verdict = Verdict.REJECTED

    # Build reasoning string
    if reasons:
        reasoning = f"Score={score:.2f}. " + "; ".join(reasons)
    else:
        reasoning = f"Score={score:.2f}. All checks passed."

    return verdict, score, reasoning


def _test_mode_verdict(fingerprint: Dict[str, Any]) -> Tuple[Verdict, float, str]:
    """Deterministic verdict for testing based on fingerprint hash.

    Hash suffix determines outcome:
        0x...APPROVED  -> APPROVED (0.95)
        0x...CAUTIOUS  -> CAUTIOUS (0.70)
        0x...SUSPICIOUS -> SUSPICIOUS (0.45)
        0x...REJECTED  -> REJECTED (0.10)
        default        -> APPROVED (0.85)
    """
    fp_hash = compute_fingerprint_hash(fingerprint)

    if fp_hash.endswith("APPROVED"):
        return Verdict.APPROVED, 0.95, f"test_mode=true — APPROVED (hash: ...{fp_hash[-8:]})"
    elif fp_hash.endswith("CAUTIOUS"):
        return Verdict.CAUTIOUS, 0.70, f"test_mode=true — CAUTIOUS (hash: ...{fp_hash[-8:]})"
    elif fp_hash.endswith("SUSPICIOUS"):
        return Verdict.SUSPICIOUS, 0.45, f"test_mode=true — SUSPICIOUS (hash: ...{fp_hash[-8:]})"
    elif fp_hash.endswith("REJECTED"):
        return Verdict.REJECTED, 0.10, f"test_mode=true — REJECTED (hash: ...{fp_hash[-8:]})"
    else:
        return Verdict.APPROVED, 0.85, f"test_mode=true — APPROVED (hash: ...{fp_hash[-8:]})"
