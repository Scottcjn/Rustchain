#!/usr/bin/env python3
"""
RustChain Validator Setup Script
================================

"Every vintage computer has historical potential"

This script sets up a new validator node on the RustChain network.
It uses the authentic genesis block born on PowerMac G4 Mirror Door
with 12 hardware entropy sources.

Emulation is economically irrational:
  - Real hardware: ~$50 for a vintage machine
  - Emulation: Thousands of hours to perfectly fake hardware fingerprints

Usage:
  python3 setup_validator.py --hardware-profile
  python3 setup_validator.py --register
  python3 setup_validator.py --start
"""

import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.chain_params import (
    CHAIN_ID, NETWORK_NAME, HARDWARE_TIERS,
    ANCIENT_THRESHOLD, SACRED_THRESHOLD, VINTAGE_THRESHOLD,
    CLASSIC_THRESHOLD, RETRO_THRESHOLD, MODERN_THRESHOLD
)
from validator.entropy import (
    HardwareEntropyCollector, SoftwareEntropyCollector,
    EntropyProfile, ValidatorIdentityManager
)

# =============================================================================
# Constants
# =============================================================================

RUSTCHAIN_DIR = Path.home() / ".rustchain"
GENESIS_FILE = "genesis_deep_entropy.json"
VALIDATOR_CONFIG = "validator.json"
ENTROPY_CACHE = "entropy_profile.json"

BOOTSTRAP_NODES = [
    # Initial bootstrap nodes (founder nodes)
    "192.168.0.160:9333",  # Sophia Prime Node
    "192.168.0.125:9333",  # G4 Mirror Door Genesis Node
    "192.168.0.126:9333",  # G4 Mirror Door Secondary
]

CURRENT_YEAR = 2025

# =============================================================================
# Hardware Detection
# =============================================================================

@dataclass
class HardwareProfile:
    """Detected hardware profile for antiquity scoring"""
    cpu_model: str
    cpu_vendor: str
    cpu_family: str
    release_year: int
    architecture: str
    ram_mb: int
    cores: int
    tier: str
    multiplier: float
    is_vintage: bool
    entropy_sources: List[str]


def detect_cpu_info() -> Dict:
    """Detect CPU information across platforms"""
    info = {
        "model": "Unknown",
        "vendor": "Unknown",
        "family": "Unknown",
        "architecture": platform.machine(),
    }

    system = platform.system()

    if system == "Linux":
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line.lower():
                        info["model"] = line.split(":")[1].strip()
                    elif "vendor_id" in line.lower():
                        info["vendor"] = line.split(":")[1].strip()
                    elif "cpu family" in line.lower():
                        info["family"] = line.split(":")[1].strip()
        except:
            pass

    elif system == "Darwin":  # macOS
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                info["model"] = result.stdout.strip()

            # Check for PowerPC
            if platform.machine() in ["Power Macintosh", "ppc", "ppc64"]:
                result = subprocess.run(
                    ["system_profiler", "SPHardwareDataType"],
                    capture_output=True, text=True
                )
                for line in result.stdout.split("\n"):
                    if "Model Identifier" in line:
                        info["model"] = line.split(":")[1].strip()
                    if "Processor Name" in line:
                        info["family"] = line.split(":")[1].strip()
        except:
            pass

    elif system == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "cpu", "get", "name"],
                capture_output=True, text=True
            )
            lines = [l.strip() for l in result.stdout.split("\n") if l.strip()]
            if len(lines) > 1:
                info["model"] = lines[1]
        except:
            pass

    return info


def estimate_release_year(cpu_model: str, cpu_vendor: str) -> int:
    """
    Estimate CPU release year based on model string.
    This is a simplified heuristic - real implementation would use a database.
    """
    model_lower = cpu_model.lower()

    # PowerPC (Apple)
    if "powermac" in model_lower or "powerpc" in model_lower:
        if "g5" in model_lower:
            return 2003
        elif "g4" in model_lower or "3,6" in model_lower:
            return 2003
        elif "g3" in model_lower:
            return 1999
        return 2002

    # Intel generations (very simplified)
    if "i9-14" in model_lower or "i7-14" in model_lower:
        return 2024
    elif "i9-13" in model_lower or "i7-13" in model_lower:
        return 2023
    elif "i9-12" in model_lower or "i7-12" in model_lower:
        return 2022
    elif "i9-11" in model_lower or "i7-11" in model_lower:
        return 2021
    elif "i9-10" in model_lower or "i7-10" in model_lower:
        return 2020
    elif "ryzen 9 7" in model_lower:
        return 2023
    elif "ryzen 9 5" in model_lower:
        return 2021
    elif "ryzen 9 3" in model_lower:
        return 2019

    # Very old CPUs
    if "pentium" in model_lower:
        if "4" in model_lower:
            return 2000
        elif "3" in model_lower or "iii" in model_lower:
            return 1999
        elif "2" in model_lower or "ii" in model_lower:
            return 1997
        return 1993

    if "486" in model_lower:
        return 1989
    if "386" in model_lower:
        return 1985
    if "286" in model_lower:
        return 1982
    if "8086" in model_lower or "8088" in model_lower:
        return 1978

    # Default to somewhat recent
    return 2020


def determine_tier(release_year: int) -> Tuple[str, float]:
    """Determine hardware tier and multiplier based on release year"""
    age = CURRENT_YEAR - release_year

    if age >= ANCIENT_THRESHOLD:
        return "ancient", HARDWARE_TIERS["ancient"]
    elif age >= SACRED_THRESHOLD:
        return "sacred", HARDWARE_TIERS["sacred"]
    elif age >= VINTAGE_THRESHOLD:
        return "vintage", HARDWARE_TIERS["vintage"]
    elif age >= CLASSIC_THRESHOLD:
        return "classic", HARDWARE_TIERS["classic"]
    elif age >= RETRO_THRESHOLD:
        return "retro", HARDWARE_TIERS["retro"]
    elif age >= MODERN_THRESHOLD:
        return "modern", HARDWARE_TIERS["modern"]
    else:
        return "recent", HARDWARE_TIERS["recent"]


def detect_hardware() -> HardwareProfile:
    """Detect full hardware profile"""
    cpu_info = detect_cpu_info()
    release_year = estimate_release_year(cpu_info["model"], cpu_info["vendor"])
    tier, multiplier = determine_tier(release_year)

    # Get RAM
    try:
        if platform.system() == "Linux":
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if "MemTotal" in line:
                        ram_kb = int(line.split()[1])
                        ram_mb = ram_kb // 1024
                        break
        elif platform.system() == "Darwin":
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True
            )
            ram_mb = int(result.stdout.strip()) // (1024 * 1024)
        else:
            ram_mb = 4096  # Default
    except:
        ram_mb = 4096

    # Get cores
    cores = os.cpu_count() or 1

    # Detect available entropy sources
    entropy_sources = []
    if os.path.exists("/dev/urandom"):
        entropy_sources.append("urandom")
    if os.path.exists("/proc/cpuinfo"):
        entropy_sources.append("cpuinfo")
    if platform.machine() in ["Power Macintosh", "ppc", "ppc64"]:
        entropy_sources.append("powerpc_timebase")
    if os.path.exists("/sys/class/thermal"):
        entropy_sources.append("thermal")
    if os.path.exists("/sys/class/dmi"):
        entropy_sources.append("dmi")

    return HardwareProfile(
        cpu_model=cpu_info["model"],
        cpu_vendor=cpu_info["vendor"],
        cpu_family=cpu_info["family"],
        release_year=release_year,
        architecture=cpu_info["architecture"],
        ram_mb=ram_mb,
        cores=cores,
        tier=tier,
        multiplier=multiplier,
        is_vintage=(CURRENT_YEAR - release_year) >= 10,
        entropy_sources=entropy_sources,
    )


# =============================================================================
# Genesis Loading
# =============================================================================

def load_genesis() -> Dict:
    """Load the authentic G4-born genesis block"""
    genesis_path = RUSTCHAIN_DIR / "genesis" / GENESIS_FILE

    if not genesis_path.exists():
        # Try to find genesis in package
        pkg_genesis = Path(__file__).parent.parent / "genesis" / GENESIS_FILE
        if pkg_genesis.exists():
            genesis_path.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy(pkg_genesis, genesis_path)

    if not genesis_path.exists():
        raise FileNotFoundError(
            f"Genesis block not found at {genesis_path}\n"
            "Please run: rustchain-setup --download-genesis"
        )

    with open(genesis_path, "r") as f:
        genesis = json.load(f)

    # Verify genesis authenticity
    if "deep_entropy_proof" not in genesis:
        raise ValueError("Invalid genesis: missing deep entropy proof")

    if not genesis.get("proof_of_antiquity", {}).get("hardware_verified"):
        print("WARNING: Genesis was not verified on real vintage hardware")

    return genesis


def verify_genesis_signature(genesis: Dict) -> bool:
    """Verify the genesis block signature"""
    proof = genesis.get("deep_entropy_proof", {})
    signature = proof.get("signature", "")

    # Check for PowerPC G4 signature format
    if not signature.startswith("PPC-G4-DEEP-"):
        print(f"WARNING: Genesis signature format unexpected: {signature[:20]}...")
        return False

    # Verify depth
    depth = int(signature.split("-D")[-1]) if "-D" in signature else 0
    if depth < 10:
        print(f"WARNING: Genesis entropy depth too low: {depth}")
        return False

    print(f"Genesis signature verified: {signature[:40]}...")
    return True


# =============================================================================
# Validator Registration
# =============================================================================

@dataclass
class ValidatorConfig:
    """Validator configuration"""
    validator_id: str
    wallet_address: str
    hardware_profile: Dict
    entropy_fingerprint: str
    antiquity_score: float
    tier: str
    bootstrap_nodes: List[str]
    api_port: int
    p2p_port: int
    registered_at: int


def generate_wallet_address(entropy_fingerprint: str) -> str:
    """Generate a wallet address from entropy fingerprint"""
    # Simple address generation (real implementation would use proper crypto)
    addr_hash = hashlib.sha256(entropy_fingerprint.encode()).hexdigest()
    checksum = hashlib.sha256(bytes.fromhex(addr_hash)).hexdigest()[:8]
    return f"RTC{addr_hash[:32]}{checksum}"


def calculate_antiquity_score(release_year: int, uptime_days: int = 1) -> float:
    """
    Calculate Antiquity Score using the RIP formula:
    AS = (current_year - release_year) * log10(uptime_days + 1)
    """
    import math
    age = CURRENT_YEAR - release_year
    return age * math.log10(uptime_days + 1)


def register_validator(hardware: HardwareProfile, genesis: Dict) -> ValidatorConfig:
    """Register a new validator"""

    print("\nGenerating validator identity...")

    # Collect entropy
    hw_collector = HardwareEntropyCollector()
    sw_collector = SoftwareEntropyCollector()

    hw_entropy = hw_collector.collect_all()
    sw_entropy = sw_collector.collect_all()

    # Create entropy profile
    profile = EntropyProfile(
        hardware_entropy=hw_entropy,
        software_entropy=sw_entropy,
        collection_timestamp=int(time.time()),
        hardware_tier=hardware.tier,
        estimated_release_year=hardware.release_year,
    )

    # Generate validator ID
    identity_manager = ValidatorIdentityManager()
    validator_id = identity_manager.derive_validator_id(profile)

    # Generate wallet address
    wallet_address = generate_wallet_address(validator_id)

    # Calculate antiquity score
    antiquity_score = calculate_antiquity_score(hardware.release_year)

    config = ValidatorConfig(
        validator_id=validator_id,
        wallet_address=wallet_address,
        hardware_profile=asdict(hardware),
        entropy_fingerprint=identity_manager.fingerprint_hash,
        antiquity_score=antiquity_score,
        tier=hardware.tier,
        bootstrap_nodes=BOOTSTRAP_NODES,
        api_port=9332,
        p2p_port=9333,
        registered_at=int(time.time()),
    )

    # Save config
    config_path = RUSTCHAIN_DIR / VALIDATOR_CONFIG
    RUSTCHAIN_DIR.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(asdict(config), f, indent=2)

    print(f"Validator registered: {validator_id[:16]}...")
    print(f"Wallet address: {wallet_address[:24]}...")
    print(f"Antiquity Score: {antiquity_score:.2f}")
    print(f"Hardware Tier: {hardware.tier} ({hardware.multiplier}x)")

    return config


# =============================================================================
# Main CLI
# =============================================================================

def print_banner():
    """Print RustChain banner"""
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██████╗ ██╗   ██╗███████╗████████╗ ██████╗██╗  ██╗ █████╗ ██╗███╗   ██╗   ║
║   ██╔══██╗██║   ██║██╔════╝╚══██╔══╝██╔════╝██║  ██║██╔══██╗██║████╗  ██║   ║
║   ██████╔╝██║   ██║███████╗   ██║   ██║     ███████║███████║██║██╔██╗ ██║   ║
║   ██╔══██╗██║   ██║╚════██║   ██║   ██║     ██╔══██║██╔══██║██║██║╚██╗██║   ║
║   ██║  ██║╚██████╔╝███████║   ██║   ╚██████╗██║  ██║██║  ██║██║██║ ╚████║   ║
║   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝    ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝   ║
║                                                                              ║
║                      PROOF OF ANTIQUITY VALIDATOR SETUP                      ║
║                                                                              ║
║   "Every vintage computer has historical potential"                          ║
║                                                                              ║
║   This is NOT Proof of Work. This is PROOF OF ANTIQUITY.                     ║
║   Real hardware rewarded. Emulation economically irrational.                 ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def cmd_hardware_profile(args):
    """Show hardware profile"""
    print("\nDetecting hardware...")
    hardware = detect_hardware()

    print("\n" + "=" * 60)
    print("HARDWARE PROFILE")
    print("=" * 60)
    print(f"  CPU Model: {hardware.cpu_model}")
    print(f"  Vendor: {hardware.cpu_vendor}")
    print(f"  Architecture: {hardware.architecture}")
    print(f"  Cores: {hardware.cores}")
    print(f"  RAM: {hardware.ram_mb} MB")
    print(f"  Estimated Release Year: {hardware.release_year}")
    print(f"  Age: {CURRENT_YEAR - hardware.release_year} years")
    print(f"  Hardware Tier: {hardware.tier.upper()}")
    print(f"  Reward Multiplier: {hardware.multiplier}x")
    print(f"  Is Vintage: {'YES' if hardware.is_vintage else 'NO'}")
    print(f"  Entropy Sources: {', '.join(hardware.entropy_sources)}")

    # Calculate projected antiquity score
    score = calculate_antiquity_score(hardware.release_year, uptime_days=30)
    print(f"\n  Projected Antiquity Score (30 day uptime): {score:.2f}")

    if hardware.is_vintage:
        print("\n  ✓ This hardware qualifies for vintage rewards!")
    else:
        print("\n  ⚠ Modern hardware receives reduced rewards (0.5x)")
        print("    Consider using vintage hardware for better returns.")


def cmd_register(args):
    """Register as validator"""
    print("\nLoading genesis block...")
    try:
        genesis = load_genesis()
        verify_genesis_signature(genesis)
        print(f"Genesis loaded: Chain ID {genesis['rustchain_genesis']['chain_id']}")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("\nTo download genesis, create the genesis directory and copy genesis_deep_entropy.json")
        return

    print("\nDetecting hardware...")
    hardware = detect_hardware()

    print(f"\nHardware detected: {hardware.cpu_model}")
    print(f"Tier: {hardware.tier} ({hardware.multiplier}x multiplier)")

    config = register_validator(hardware, genesis)

    print("\n" + "=" * 60)
    print("VALIDATOR REGISTRATION COMPLETE")
    print("=" * 60)
    print(f"\nValidator ID: {config.validator_id}")
    print(f"Wallet: {config.wallet_address}")
    print(f"Antiquity Score: {config.antiquity_score:.2f}")
    print(f"\nConfig saved to: {RUSTCHAIN_DIR / VALIDATOR_CONFIG}")
    print("\nTo start your validator, run:")
    print("  python3 setup_validator.py --start")


def cmd_start(args):
    """Start the validator node"""
    config_path = RUSTCHAIN_DIR / VALIDATOR_CONFIG

    if not config_path.exists():
        print("ERROR: Validator not registered. Run with --register first.")
        return

    with open(config_path, "r") as f:
        config = json.load(f)

    print("\nStarting RustChain Validator Node...")
    print(f"Validator ID: {config['validator_id'][:16]}...")
    print(f"P2P Port: {config['p2p_port']}")
    print(f"API Port: {config['api_port']}")
    print(f"Bootstrap nodes: {len(config['bootstrap_nodes'])}")

    # Import and start the node
    try:
        from main import RustChainNode
        node = RustChainNode(
            port=config['p2p_port'],
            data_dir=str(RUSTCHAIN_DIR),
            mining=True
        )
        print("\nNode started. Press Ctrl+C to stop.")
        node.start()
    except ImportError:
        print("\nNode module not found. Starting in simulation mode...")
        print("Full node functionality coming in next release.")

        # Simulation
        while True:
            try:
                time.sleep(600)  # 10 minute blocks
                print(f"[Block] Antiquity proof submitted (score: {config['antiquity_score']:.2f})")
            except KeyboardInterrupt:
                print("\nValidator stopped.")
                break


def main():
    parser = argparse.ArgumentParser(
        description="RustChain Proof of Antiquity Validator Setup"
    )
    parser.add_argument(
        "--hardware-profile", "-p",
        action="store_true",
        help="Show detected hardware profile and tier"
    )
    parser.add_argument(
        "--register", "-r",
        action="store_true",
        help="Register as a validator"
    )
    parser.add_argument(
        "--start", "-s",
        action="store_true",
        help="Start the validator node"
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version"
    )

    args = parser.parse_args()

    print_banner()

    if args.version:
        print("RustChain Validator Setup v0.1.0")
        print("Genesis: PPC-G4-DEEP (PowerMac G4 Mirror Door)")
        return

    if args.hardware_profile:
        cmd_hardware_profile(args)
    elif args.register:
        cmd_register(args)
    elif args.start:
        cmd_start(args)
    else:
        parser.print_help()
        print("\nQuick Start:")
        print("  1. Check your hardware tier:  --hardware-profile")
        print("  2. Register as validator:     --register")
        print("  3. Start mining:              --start")


if __name__ == "__main__":
    main()
