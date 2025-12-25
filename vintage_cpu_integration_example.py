#!/usr/bin/env python3
"""
Vintage CPU Integration Example for RustChain Miner
====================================================

Demonstrates how to integrate vintage CPU detection into the RustChain
universal miner client and server validation.

Usage:
    python3 vintage_cpu_integration_example.py
"""

import platform
import re
from typing import Optional, Dict, Any

# Import both modern and vintage detection
from cpu_architecture_detection import (
    detect_cpu_architecture,
    calculate_antiquity_multiplier,
    CPUInfo
)
from cpu_vintage_architectures import (
    detect_vintage_architecture,
    get_vintage_description
)


# =============================================================================
# UNIFIED DETECTION FUNCTION
# =============================================================================

def detect_all_cpu_architectures(brand_string: str) -> Dict[str, Any]:
    """
    Unified CPU detection - checks vintage first, then modern

    Returns a dictionary with:
        - vendor: CPU vendor (intel, amd, motorola, alpha, etc.)
        - architecture: Specific architecture (i386, k6, m68040, etc.)
        - year: Microarchitecture release year
        - base_multiplier: Antiquity multiplier
        - description: Human-readable description
        - is_vintage: True if vintage CPU, False if modern
    """
    # Try vintage detection first (most specific patterns)
    vintage_result = detect_vintage_architecture(brand_string)

    if vintage_result:
        vendor, architecture, year, base_multiplier = vintage_result
        description = get_vintage_description(architecture)
        return {
            "vendor": vendor,
            "architecture": architecture,
            "year": year,
            "base_multiplier": base_multiplier,
            "description": description,
            "is_vintage": True
        }

    # Fall back to modern detection
    cpu_info = calculate_antiquity_multiplier(brand_string)
    return {
        "vendor": cpu_info.vendor,
        "architecture": cpu_info.architecture,
        "year": cpu_info.microarch_year,
        "base_multiplier": cpu_info.antiquity_multiplier,
        "description": cpu_info.generation,
        "is_vintage": False,
        "is_server": cpu_info.is_server
    }


# =============================================================================
# MINER CLIENT INTEGRATION
# =============================================================================

def get_cpu_brand_string() -> str:
    """
    Get CPU brand string from system

    On Linux: Read /proc/cpuinfo
    On Windows: Read registry
    On Mac: Use sysctl
    """
    system = platform.system()

    if system == "Linux":
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
                    elif line.startswith("cpu"):
                        # For non-x86 systems (ARM, MIPS, SPARC, etc.)
                        cpu_line = line.split(":", 1)[1].strip()
                        if cpu_line and not cpu_line.isdigit():
                            return cpu_line
        except Exception as e:
            print(f"Error reading /proc/cpuinfo: {e}")

    elif system == "Darwin":
        # Mac OS X
        try:
            import subprocess
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            print(f"Error reading sysctl: {e}")

    elif system == "Windows":
        # Windows Registry
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            )
            value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
            return value.strip()
        except Exception as e:
            print(f"Error reading Windows registry: {e}")

    # Fallback to platform.processor()
    return platform.processor()


def detect_hardware_for_miner() -> Dict[str, Any]:
    """
    Detect hardware for RustChain miner client

    Returns device info suitable for attestation payload
    """
    brand_string = get_cpu_brand_string()
    cpu_info = detect_all_cpu_architectures(brand_string)

    return {
        "cpu_brand": brand_string,
        "device_family": cpu_info["vendor"],
        "device_arch": cpu_info["architecture"],
        "cpu_year": cpu_info["year"],
        "expected_multiplier": cpu_info["base_multiplier"],
        "is_vintage": cpu_info.get("is_vintage", False),
        "is_server": cpu_info.get("is_server", False),
        "description": cpu_info["description"]
    }


# =============================================================================
# SERVER-SIDE VALIDATION
# =============================================================================

def validate_cpu_claim(attestation: Dict[str, Any]) -> tuple:
    """
    Server-side validation of miner's CPU claim

    Parameters:
        attestation: Attestation payload from miner

    Returns:
        (is_valid, reason, detected_arch, detected_multiplier)
    """
    # Extract claimed device info
    device = attestation.get("device", {})
    claimed_brand = device.get("cpu_brand", "")
    claimed_arch = device.get("device_arch", "")
    claimed_multiplier = device.get("expected_multiplier", 1.0)

    if not claimed_brand:
        return (False, "missing_cpu_brand", None, 1.0)

    # Detect actual architecture from brand string
    cpu_info = detect_all_cpu_architectures(claimed_brand)
    detected_arch = cpu_info["architecture"]
    detected_multiplier = cpu_info["base_multiplier"]

    # Validate architecture matches
    if detected_arch != claimed_arch:
        return (
            False,
            f"arch_mismatch:claimed={claimed_arch},detected={detected_arch}",
            detected_arch,
            detected_multiplier
        )

    # Validate multiplier matches (allow 1% tolerance)
    multiplier_diff = abs(detected_multiplier - claimed_multiplier)
    if multiplier_diff > 0.01:
        return (
            False,
            f"multiplier_mismatch:claimed={claimed_multiplier},detected={detected_multiplier}",
            detected_arch,
            detected_multiplier
        )

    return (True, "valid", detected_arch, detected_multiplier)


# =============================================================================
# TIME DECAY APPLICATION
# =============================================================================

def apply_time_decay(
    base_multiplier: float,
    cpu_year: int,
    genesis_timestamp: int = 1764706927,  # RustChain genesis (Dec 2, 2025)
) -> float:
    """
    Apply time decay to vintage bonuses

    Vintage hardware (>5 years old): 15% decay per year of chain operation
    Modern hardware (<5 years old): Eligible for loyalty bonus (not in this function)

    Parameters:
        base_multiplier: Base antiquity multiplier from detection
        cpu_year: Year CPU microarchitecture was released
        genesis_timestamp: Unix timestamp of chain genesis

    Returns:
        Decayed multiplier (minimum 1.0)
    """
    import time
    from datetime import datetime

    # Current date
    current_year = datetime.now().year
    hardware_age = current_year - cpu_year

    # Only apply decay to vintage hardware (>5 years old)
    if hardware_age <= 5 or base_multiplier <= 1.0:
        return base_multiplier

    # Calculate years since chain genesis
    current_timestamp = int(time.time())
    chain_age_seconds = current_timestamp - genesis_timestamp
    chain_age_years = chain_age_seconds / (365.25 * 24 * 3600)

    # Apply 15% decay per year of chain operation
    # Formula: aged = 1.0 + (base - 1.0) * (1 - 0.15 * chain_age_years)
    # Full decay after ~6.67 years (vintage bonus → 0)
    decay_factor = max(0.0, 1.0 - (0.15 * chain_age_years))
    vintage_bonus = base_multiplier - 1.0
    final_multiplier = max(1.0, 1.0 + (vintage_bonus * decay_factor))

    return round(final_multiplier, 4)


# =============================================================================
# DIFFICULTY ADJUSTMENT FOR VINTAGE HARDWARE
# =============================================================================

def adjust_difficulty_for_vintage(
    base_difficulty: float,
    cpu_info: Dict[str, Any]
) -> float:
    """
    Adjust mining difficulty for vintage hardware

    Vintage CPUs are slow and may overheat/fail with modern difficulty.
    Apply difficulty reduction based on CPU age.

    Parameters:
        base_difficulty: Base mining difficulty
        cpu_info: CPU info from detect_all_cpu_architectures()

    Returns:
        Adjusted difficulty (lower for vintage hardware)
    """
    cpu_year = cpu_info.get("year", 2025)
    current_year = 2025  # Or use datetime.now().year
    age = current_year - cpu_year

    if age <= 10:
        return base_difficulty  # Modern hardware, no adjustment

    # Apply difficulty reduction
    # 11-15 years: 10x easier
    # 16-20 years: 100x easier
    # 21-25 years: 1000x easier
    # 26+ years: 10000x easier
    if age <= 15:
        return base_difficulty * 0.1
    elif age <= 20:
        return base_difficulty * 0.01
    elif age <= 25:
        return base_difficulty * 0.001
    else:
        return base_difficulty * 0.0001


# =============================================================================
# DEMO/TEST CODE
# =============================================================================

def demo():
    """Demo vintage CPU integration"""
    print("=" * 80)
    print("VINTAGE CPU INTEGRATION DEMO")
    print("=" * 80)
    print()

    # Test CPUs (mix of vintage and modern)
    test_cpus = [
        # Vintage
        "Intel 80386DX @ 33MHz",
        "MC68040 @ 33MHz",
        "Alpha 21064 @ 150MHz",
        "AMD K6-2 350MHz",
        "Intel(R) Pentium(R) III CPU 1000MHz",
        "Cyrix 6x86MX PR200",
        "VIA C3 Samuel 2 800MHz",
        "Transmeta Crusoe TM5800",

        # Modern
        "Intel(R) Core(TM) i7-2600K CPU @ 3.40GHz",
        "AMD Ryzen 9 7950X 16-Core Processor",
        "Apple M1",
        "PowerPC G4 (7450)",
    ]

    print("1. UNIFIED DETECTION TEST")
    print("-" * 80)
    for cpu_brand in test_cpus:
        cpu_info = detect_all_cpu_architectures(cpu_brand)
        vintage_tag = "[VINTAGE]" if cpu_info.get("is_vintage") else "[MODERN]"

        print(f"{vintage_tag} {cpu_brand}")
        print(f"  → {cpu_info['vendor']:15s} {cpu_info['architecture']:20s}")
        print(f"  → Year: {cpu_info['year']:4d} | Multiplier: {cpu_info['base_multiplier']}x")
        print(f"  → {cpu_info['description']}")
        print()

    print("=" * 80)
    print("2. MINER CLIENT SIMULATION")
    print("-" * 80)

    # Detect local CPU
    local_hardware = detect_hardware_for_miner()
    print("Local Hardware Detection:")
    print(f"  CPU Brand: {local_hardware['cpu_brand']}")
    print(f"  Device Family: {local_hardware['device_family']}")
    print(f"  Architecture: {local_hardware['device_arch']}")
    print(f"  Year: {local_hardware['cpu_year']}")
    print(f"  Base Multiplier: {local_hardware['expected_multiplier']}x")
    print(f"  Vintage: {local_hardware['is_vintage']}")
    print(f"  Description: {local_hardware['description']}")
    print()

    # Simulate attestation payload
    attestation_payload = {
        "miner": "test-wallet-address",
        "device": local_hardware,
        "nonce": 123456789,
        # ... other fields
    }

    print("=" * 80)
    print("3. SERVER-SIDE VALIDATION SIMULATION")
    print("-" * 80)

    # Validate the attestation
    is_valid, reason, detected_arch, detected_mult = validate_cpu_claim(attestation_payload)

    print(f"Validation Result: {'✅ VALID' if is_valid else '❌ INVALID'}")
    print(f"Reason: {reason}")
    print(f"Detected Architecture: {detected_arch}")
    print(f"Detected Multiplier: {detected_mult}x")
    print()

    print("=" * 80)
    print("4. TIME DECAY SIMULATION")
    print("-" * 80)

    # Test time decay on vintage CPUs
    vintage_test_cases = [
        ("Intel 80386DX", 3.0, 1985),
        ("MC68040", 2.4, 1990),
        ("Pentium III", 2.0, 1999),
        ("AMD K6-2", 2.2, 1997),
    ]

    print("Simulating decay at different chain ages:")
    print()

    for cpu_name, base_mult, year in vintage_test_cases:
        print(f"{cpu_name} ({year}, base {base_mult}x):")
        for chain_years in [0, 1, 3, 5, 10]:
            # Simulate chain age by adjusting genesis timestamp
            genesis = int(1764706927 - (chain_years * 365.25 * 24 * 3600))
            decayed = apply_time_decay(base_mult, year, genesis)
            print(f"  Chain age {chain_years:2d} years → {decayed:.4f}x")
        print()

    print("=" * 80)
    print("5. DIFFICULTY ADJUSTMENT SIMULATION")
    print("-" * 80)

    base_difficulty = 1000.0
    print(f"Base Mining Difficulty: {base_difficulty}")
    print()

    for cpu_brand in test_cpus[:6]:  # Just vintage CPUs
        cpu_info = detect_all_cpu_architectures(cpu_brand)
        adjusted = adjust_difficulty_for_vintage(base_difficulty, cpu_info)
        age = 2025 - cpu_info["year"]
        reduction = base_difficulty / adjusted if adjusted > 0 else 1

        print(f"{cpu_brand}")
        print(f"  Age: {age} years | Adjusted: {adjusted:.2f} ({reduction:.0f}x easier)")
        print()


if __name__ == "__main__":
    demo()
