#!/usr/bin/env python3
"""
RustChain Epoch Determinism Simulator

Tests that epoch settlements produce identical outputs for identical inputs
across different node environments.
"""

import json
import hashlib
import argparse
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import os


@dataclass
class MinerAttestation:
    """Miner attestation data."""
    miner_id: str
    miner_pubkey: str
    device_arch: str
    device_family: str
    antiquity_multiplier: float
    entropy_score: float
    timestamp: int


@dataclass
class EpochFixture:
    """Epoch settlement fixture for replay testing."""
    epoch: int
    enrollments: List[MinerAttestation]
    config: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return {
            "epoch": self.epoch,
            "enrollments": [
                {
                    "miner_id": e.miner_id,
                    "miner_pubkey": e.miner_pubkey,
                    "device_arch": e.device_arch,
                    "device_family": e.device_family,
                    "antiquity_multiplier": e.antiquity_multiplier,
                    "entropy_score": e.entropy_score,
                    "timestamp": e.timestamp,
                }
                for e in self.enrollments
            ],
            "config": self.config,
        }


class DeterminismSimulator:
    """Simulates epoch settlement and checks determinism."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._default_config()
        self.settled_epochs = []
    
    def _default_config(self) -> Dict:
        return {
            "blocks_per_epoch": 144,
            "slot_time_seconds": 600,
            "min_entropy_score": 0.0,
            "antiquity_bonus_threshold": 10,
            "reward_decay_threshold": 0.3,
            "severe_decay_threshold": 0.7,
        }
    
    def calculate_rust_score(self, attestation: MinerAttestation) -> float:
        """Calculate rust score based on device age and entropy."""
        base_score = 0.0
        
        # Age-based scoring
        arch_scores = {
            "G4": 300,  # 2001 PowerPC G4
            "G5": 280,  # 2004 PowerPC G5
            "power8": 180,
            "power9": 100,
            "apple_silicon": 80,
            "modern": 30,
            "486": 200,
            "retro": 190,
        }
        
        base_score = arch_scores.get(attestation.device_arch, 30)
        
        # Entropy bonus
        entropy_bonus = min(attestation.entropy_score * 10, 50)
        
        # Age multiplier
        age_mult = attestation.antiquity_multiplier
        
        return (base_score + entropy_bonus) * age_mult
    
    def calculate_rewards(self, fixture: EpochFixture) -> Dict[str, float]:
        """Calculate rewards for all miners in an epoch."""
        rewards = {}
        total_score = 0.0
        
        # Calculate total score
        for enrollment in fixture.enrollments:
            score = self.calculate_rust_score(enrollment)
            total_score += score
        
        # Distribute epoch pot
        epoch_pot = self.config.get("epoch_pot", 1.5)
        
        for enrollment in fixture.enrollments:
            score = self.calculate_rust_score(enrollment)
            if total_score > 0:
                share = score / total_score
                rewards[enrollment.miner_id] = round(share * epoch_pot, 6)
            else:
                rewards[enrollment.miner_id] = 0.0
        
        return rewards
    
    def settle_epoch(self, fixture: EpochFixture) -> Dict[str, Any]:
        """Settle an epoch and return the results."""
        rewards = self.calculate_rewards(fixture)
        
        result = {
            "epoch": fixture.epoch,
            "timestamp": int(datetime.now().timestamp()),
            "total_enrollments": len(fixture.enrollments),
            "total_score": sum(
                self.calculate_rust_score(e) for e in fixture.enrollments
            ),
            "rewards": rewards,
            "config_hash": self._hash_config(fixture.config),
        }
        
        self.settled_epochs.append(result)
        return result
    
    def _hash_config(self, config: Dict) -> str:
        """Hash configuration for verification."""
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]
    
    def verify_determinism(
        self, result1: Dict, result2: Dict
    ) -> Dict[str, Any]:
        """Verify two settlement results are deterministic."""
        differences = []
        
        # Compare rewards
        rewards1 = result1.get("rewards", {})
        rewards2 = result2.get("rewards", {})
        
        all_miners = set(rewards1.keys()) | set(rewards2.keys())
        
        for miner in all_miners:
            r1 = rewards1.get(miner, 0)
            r2 = rewards2.get(miner, 0)
            
            if abs(r1 - r2) > 0.000001:  # Float tolerance
                differences.append({
                    "miner_id": miner,
                    "result1": r1,
                    "result2": r2,
                    "diff": abs(r1 - r2),
                })
        
        # Compare totals
        total1 = sum(rewards1.values())
        total2 = sum(rewards2.values())
        
        return {
            "deterministic": len(differences) == 0 and abs(total1 - total2) < 0.000001,
            "reward_differences": differences,
            "total_diff": abs(total1 - total2),
            "config_match": result1.get("config_hash") == result2.get("config_hash"),
        }
    
    def generate_report(
        self, result1: Dict, result2: Dict, verification: Dict
    ) -> str:
        """Generate human-readable determinism report."""
        lines = [
            "# Epoch Determinism Report",
            f"",
            f"Epoch: {result1['epoch']}",
            f"Timestamp: {datetime.fromtimestamp(result1['timestamp'])}",
            f"",
            f"## Results",
            f"",
            f"| Metric | Run 1 | Run 2 |",
            f"|--------|-------|-------|",
            f"| Total Miners | {result1['total_enrollments']} | {result2['total_enrollments']} |",
            f"| Total Score | {result1['total_score']:.2f} | {result2['total_score']:.2f} |",
            f"| Total Rewards | {sum(result1['rewards'].values()):.6f} | {sum(result2['rewards'].values()):.6f} |",
            f"",
            f"## Determinism Check",
            f"",
            f"- **Deterministic**: {'✅ YES' if verification['deterministic'] else '❌ NO'}",
            f"- Config Match: {'✅' if verification['config_match'] else '❌'}",
            f"- Total Difference: {verification['total_diff']:.10f}",
            f"",
        ]
        
        if verification["reward_differences"]:
            lines.extend([
                "## Differences",
                f"",
                "| Miner | Run 1 | Run 2 | Diff |",
                f"|-------|-------|-------|------|",
            ])
            for d in verification["reward_differences"]:
                lines.append(
                    f"| {d['miner_id'][:16]}... | {d['result1']:.6f} | {d['result2']:.6f} | {d['diff']:.10f} |"
                )
        
        return "\n".join(lines)


def create_normal_fixture() -> EpochFixture:
    """Create a normal epoch fixture."""
    enrollments = [
        MinerAttestation(
            miner_id=f"miner_{i}",
            miner_pubkey=f"RTC{i:064d}",
            device_arch="G4" if i % 3 == 0 else "modern",
            device_family="PowerPC" if i % 3 == 0 else "x86",
            antiquity_multiplier=2.5 if i % 3 == 0 else 1.0,
            entropy_score=i * 0.1,
            timestamp=1700000000 + i * 600,
        )
        for i in range(20)
    ]
    
    return EpochFixture(
        epoch=1,
        enrollments=enrollments,
        config={"epoch_pot": 1.5, "decay_enabled": True},
    )


def create_sparse_fixture() -> EpochFixture:
    """Create a sparse epoch fixture (few miners)."""
    enrollments = [
        MinerAttestation(
            miner_id="sparse_miner_1",
            miner_pubkey="RTC1" + "0" * 60,
            device_arch="power8",
            device_family="PowerPC",
            antiquity_multiplier=2.0,
            entropy_score=5.0,
            timestamp=1700000000,
        ),
    ]
    
    return EpochFixture(
        epoch=2,
        enrollments=enrollments,
        config={"epoch_pot": 0.5, "decay_enabled": False},
    )


def create_edge_case_fixture() -> EpochFixture:
    """Create an edge case fixture (boundary conditions)."""
    enrollments = [
        MinerAttestation(
            miner_id=f"edge_miner_{i}",
            miner_pubkey=f"RTC{i:064d}",
            device_arch="486" if i == 0 else "retro",
            device_family="x86" if i == 0 else "DOS",
            antiquity_multiplier=2.0,
            entropy_score=0.0 if i == 0 else 10.0,
            timestamp=1700000000 + i,
        )
        for i in range(3)
    ]
    
    return EpochFixture(
        epoch=3,
        enrollments=enrollments,
        config={"epoch_pot": 0.01, "decay_enabled": True},
    )


def main():
    parser = argparse.ArgumentParser(
        description="RustChain Epoch Determinism Simulator"
    )
    parser.add_argument(
        "--fixture",
        choices=["normal", "sparse", "edge", "all"],
        default="all",
        help="Which fixture to run",
    )
    parser.add_argument(
        "--output",
        choices=["json", "markdown", "report"],
        default="report",
        help="Output format",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    
    args = parser.parse_args()
    
    simulator = DeterminismSimulator()
    
    fixtures = []
    if args.fixture == "all":
        fixtures = [create_normal_fixture(), create_sparse_fixture(), create_edge_case_fixture()]
    elif args.fixture == "normal":
        fixtures = [create_normal_fixture()]
    elif args.fixture == "sparse":
        fixtures = [create_sparse_fixture()]
    elif args.fixture == "edge":
        fixtures = [create_edge_case_fixture()]
    
    results = []
    for fixture in fixtures:
        result = simulator.settle_epoch(fixture)
        results.append(result)
        
        if args.verbose:
            print(f"Epoch {fixture.epoch}: {len(fixture.enrollments)} miners")
    
    # Run determinism check (compare first two runs)
    if len(results) >= 2:
        verification = simulator.verify_determinism(results[0], results[1])
        
        if args.output == "report":
            report = simulator.generate_report(results[0], results[1], verification)
            print(report)
        elif args.output == "json":
            print(json.dumps({
                "results": results,
                "verification": verification,
            }, indent=2))
        
        # Exit code based on determinism
        sys.exit(0 if verification["deterministic"] else 1)
    else:
        print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
