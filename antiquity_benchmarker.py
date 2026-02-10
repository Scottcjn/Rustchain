#!/usr/bin/env python3
"""
RustChain: Antiquity Benchmarker v1.0.0
=======================================
A utility to verify your hardware's antiquity multiplier for the RustChain network.
Author: Muhammet Simsek (@muhammetsimssek)
"""

import sys
import platform
import subprocess
from cpu_architecture_detection import INTEL_GENERATIONS, AMD_GENERATIONS, CPUInfo

def get_cpu_brand_string():
    """Platform-independent way to get CPU brand string."""
    try:
        if platform.system() == "Windows":
            return subprocess.check_output(["wmic", "cpu", "get", "name"]).decode().split("\n")[1].strip()
        elif platform.system() == "Darwin":
            return subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"]).decode().strip()
        else:
            # Linux
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":")[1].strip()
    except Exception:
        return "Unknown CPU"

def calculate_antiquity_score():
    brand = get_cpu_brand_string()
    print(f"--- RustChain Hardware Audit ---")
    print(f"Detected CPU: {brand}")
    print(f"System: {platform.system()} {platform.machine()}")
    
    # Simulating detection logic based on cpu_architecture_detection patterns
    multiplier = 1.0
    detected_gen = "Modern/Unknown"
    
    vendor = "intel" if "intel" in brand.lower() else "amd"
    generations = INTEL_GENERATIONS if vendor == "intel" else AMD_GENERATIONS
    
    import re
    for gen, info in generations.items():
        for pattern in info["patterns"]:
            if re.search(pattern, brand, re.IGNORECASE):
                multiplier = info["base_multiplier"]
                detected_gen = info["description"]
                break
        if multiplier > 1.0:
            break
            
    print(f"\n--- Result ---")
    print(f"Generation: {detected_gen}")
    print(f"Antiquity Multiplier: {multiplier}x")
    
    if multiplier > 1.2:
        print("\n[GOLDEN HARDWARE] Your system is a relic! High earning potential detected.")
    elif multiplier > 1.0:
        print("\n[CLASSIC HARDWARE] Good antiquity score. Worth mining.")
    else:
        print("\n[MODERN HARDWARE] 1.0x baseline. You help secure the network!")

if __name__ == "__main__":
    calculate_antiquity_score()
