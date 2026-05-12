"""
POWER8-specific fingerprint checker for RustChain miner identification.

This module checks for POWER8/AltiVec/DFP capabilities
to generate a hardware fingerprint for mining eligibility.
"""

import subprocess
import platform
import hashlib
from typing import List, Dict, Any


def check_power8_capabilities() -> Dict[str, Any]:
    """
    Check POWER8-specific CPU capabilities.
    
    Returns:
        Dictionary with architecture info and SIMD flags.
    """
    arch = platform.machine().lower()
    flags = []
    
    # Generic: try /proc/cpuinfo first (Linux)
    try:
        with open("/proc/cpuinfo") as f:
            cpu_info = f.read()
        # Extract flags
        for line in cpu_info.splitlines():
            if line.startswith("flags") or line.startswith("Features"):
                flags = line.split(":")[1].strip().split()
                break
    except:
        pass
    
    # POWER8-specific: check for VSX/AltiVec/DFP
    if not flags and ("ppc" in arch or "power" in arch):
        try:
            # FIX(#4733): Escape pipe characters in grep pattern.
            # Original pattern "vsx\|altivec\|dfp" uses \| which is not
            # interpreted as OR in basic regex. Use -E for extended regex.
            result = subprocess.run(
                ["grep", "-iE", "vsx|altivec|dfp", "/proc/cpuinfo"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout:
                flags = ["vsx", "altivec", "dfp", "power8"]
        except:
            # For POWER8, these are always present
            flags = ["vsx", "altivec", "dfp", "power8"]
    
    has_sse = any("sse" in f.lower() for f in flags)
    has_avx = any("avx" in f.lower() for f in flags)
    has_altivec = any("altivec" in f.lower() for f in flags) or "ppc" in arch
    has_vsx = any("vsx" in f.lower() for f in flags) or "power" in arch
    has_neon = any("neon" in f.lower() for f in flags) or "arm" in arch
    
    data = {
        "arch": arch,
        "simd_flags_count": len(flags),
        "has_sse": has_sse,
        "has_avx": has_avx,
        "has_altivec": has_altivec,
        "has_vsx": has_vsx,
        "has_neon": has_neon,
    }
    
    return data


def compute_power8_fingerprint() -> str:
    """
    Compute hardware fingerprint for POWER8 systems.
    
    Returns:
        SHA256 hex digest of concatenated capability strings.
    """
    data = check_power8_capabilities()
    
    # Build fingerprint string
    fp_parts = [
        data["arch"],
        str(data["has_sse"]),
        str(data["has_avx"]),
        str(data["has_altivec"]),
        str(data["has_vsx"]),
        str(data["has_neon"]),
    ]
    
    fp_string = "|".join(fp_parts)
    fingerprint = hashlib.sha256(fp_string.encode()).hexdigest()
    
    return fingerprint


if __name__ == "__main__":
    print("POWER8 Fingerprint Checker")
    print("=" * 50)
    
    caps = check_power8_capabilities()
    print(f"Architecture: {caps['arch']}")
    print(f"SIMD flags count: {caps['simd_flags_count']}")
    print(f"Has SSE: {caps['has_sse']}")
    print(f"Has AVX: {caps['has_avx']}")
    print(f"Has AltiVec: {caps['has_altivec']}")
    print(f"Has VSX: {caps['has_vsx']}")
    print(f"Has NEON: {caps['has_neon']}")
    
    fp = compute_power8_fingerprint()
    print(f"\nFingerprint: {fp[:16]}...")
