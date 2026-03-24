"""
Hardware detection for rustchainnode.
Auto-detects CPU architecture, thread count, and antiquity score.
"""

import os
import platform
import subprocess
import json
from pathlib import Path


def detect_cpu_info() -> dict:
    """Detect CPU architecture and estimate antiquity."""
    arch = platform.machine().lower()
    system = platform.system().lower()
    cpu_count = os.cpu_count() or 1

    # Map architectures to RustChain types
    arch_map = {
        "x86_64": "modern_x86",
        "amd64": "modern_x86",
        "aarch64": "arm64",
        "arm64": "arm64",
        "ppc64": "ppc64",
        "ppc64le": "ppc64le",
        "ppc": "ppc",
        "i386": "x86_32",
        "i686": "x86_32",
    }
    arch_type = arch_map.get(arch, "unknown")

    # Antiquity multipliers (vintage = higher)
    antiquity_map = {
        "ppc": 2.5,
        "ppc64": 2.0,
        "ppc64le": 1.8,
        "x86_32": 1.5,
        "arm64": 1.0,
        "modern_x86": 1.0,
        "unknown": 1.0,
    }
    antiquity = antiquity_map.get(arch_type, 1.0)

    # Optimal thread count: 1 per CPU (RIP-200: 1 CPU = 1 vote)
    optimal_threads = cpu_count

    return {
        "arch": arch,
        "arch_type": arch_type,
        "system": system,
        "cpu_count": cpu_count,
        "optimal_threads": optimal_threads,
        "antiquity_multiplier": antiquity,
        "python_version": platform.python_version(),
    }


def get_optimal_config(wallet: str, port: int = 8099) -> dict:
    """Generate optimal node configuration based on hardware."""
    hw = detect_cpu_info()
    return {
        "wallet": wallet,
        "port": port,
        "threads": hw["optimal_threads"],
        "arch_type": hw["arch_type"],
        "antiquity_multiplier": hw["antiquity_multiplier"],
        "node_url": "https://50.28.86.131",
        "auto_configured": True,
    }
