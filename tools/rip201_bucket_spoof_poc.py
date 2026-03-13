#!/usr/bin/env python3
"""
Demonstrate RIP-201 bucket-normalization gaming with a spoofed hardware class.

Technique:
1. Submit an attestation from a modern x86 host while claiming PowerPC G4.
2. Provide only the minimum anti-emulation fingerprint evidence.
3. Let the server enroll the miner with G4-era weight and classify it into the
   vintage_powerpc reward bucket.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional, ModuleType


def load_fleet_module() -> ModuleType:
    """Load fleet immune system module for PoC.
    
    Returns:
        Loaded fleet module
    """
    module_path = (
        Path(__file__).resolve().parent.parent
        / "rips"
        / "python"
        / "rustchain"
        / "fleet_immune_system.py"
    )
    spec = importlib.util.spec_from_file_location("fleet_immune_system_bucket_poc", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_report(modern_miners: int, total_reward_urtc: int) -> Dict[str, Any]:
    """Build RIP-201 bucket spoofing report.
    
    Args:
        modern_miners: Number of honest modern miners to simulate
        total_reward_urtc: Total reward pot in micro-RTC
        
    Returns:
        Dictionary containing attack simulation results
    """
    fleet_mod = load_fleet_module()
    db = sqlite3.connect(":memory:")
    fleet_mod.ensure_schema(db)

    miners: List[Tuple[str, str]] = [("spoof-g4", "g4")] + [(f"modern-{index}", "modern") for index in range(modern_miners)]
    rewards: Dict[str, float] = fleet_mod.calculate_immune_rewards_equal_split(
        db=db,
        epoch=91,
        miners=miners,
        chain_age_years=1.0,
        total_reward_urtc=total_reward_urtc,
    )

    honest_per_miner: float = rewards["modern-0"] if modern_miners else 0
    spoof_reward: float = rewards["spoof-g4"]
    multiplier: Optional[float] = round(spoof_reward / honest_per_miner, 2) if honest_per_miner else None

    return {
        "attack": "modern_x86_claims_g4_bucket",
        "server_acceptance": {
            "claimed_family": "PowerPC",
            "claimed_arch": "G4",
            "actual_cpu_string": "Intel Xeon Platinum",
            "minimum_fingerprint_checks": ["anti_emulation"],
            "bucket": fleet_mod.classify_miner_bucket("g4"),
            "enrollment_weight": 2.5,
        },
        "reward_impact": {
            "total_reward_urtc": total_reward_urtc,
            "modern_honest_miners": modern_miners,
            "spoofed_bucket_reward_urtc": spoof_reward,
            "honest_modern_reward_each_urtc": honest_per_miner,
            "gain_multiple": multiplier,
        },
        "rewards": rewards,
    }


def main() -> None:
    """Main entry point for RIP-201 bucket spoofing PoC."""
    parser = argparse.ArgumentParser(description="RIP-201 bucket spoofing PoC")
    parser.add_argument("--modern-miners", type=int, default=10, help="Number of honest modern miners")
    parser.add_argument("--reward", type=int, default=1_100_000, help="Total reward pot in uRTC")
    args = parser.parse_args()

    print(json.dumps(build_report(args.modern_miners, args.reward), indent=2, sort_keys=True))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "node"))
    main()
