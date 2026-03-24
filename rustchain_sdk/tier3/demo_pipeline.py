#!/usr/bin/env python3
"""
Multi-Agent Pipeline Demo Script

Demonstrates the complete autonomous multi-agent pipeline
with verifiable RTC transaction flow.

Usage:
    python demo_pipeline.py [--mode mock|real] [--runs N]
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tier3.agents import PipelineOrchestrator
from tier3.agents.reward_agent import RewardTier
from tier3.agents.validator_agent import ValidationLevel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sample_poa(miner_id: int) -> dict:
    """Create a sample PoA submission"""
    import hashlib
    
    hardware_configs = [
        ("PowerPC G4", 450, "19990101"),
        ("PowerPC G3", 350, "19970601"),
        ("Pentium III", 550, "19990301"),
        ("Athlon XP", 1200, "20010601"),
        ("Pentium 4", 2400, "20020101"),
    ]
    
    cpu_type, mhz, bios_date = hardware_configs[miner_id % len(hardware_configs)]
    
    # Generate a mock proof hash
    proof_data = f"miner_{miner_id}_{cpu_type}_{mhz}_{bios_date}"
    proof_hash = hashlib.sha256(proof_data.encode()).hexdigest()
    
    return {
        "submitter": f"0xMINER{miner_id:03d}",
        "validator": f"0xVALIDATOR{(miner_id % 3) + 1:03d}",
        "hardware_id": f"HW-{cpu_type.replace(' ', '-')}-{miner_id:03d}",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "entropy_source": f"bios_date_{bios_date}_loop_counter_{miner_id * 847362}",
        "cpu_type": cpu_type,
        "cpu_mhz": mhz,
        "claimed_amount": 100.0 + (miner_id * 10),
        "proof_hash": proof_hash,
        "miner_note": f"Vintage hardware miner #{miner_id}"
    }


def run_demo(mode: str = "mock", num_runs: int = 3, artifact_dir: str = "./artifacts"):
    """Run the multi-agent pipeline demo"""
    
    print("=" * 70)
    print("  RustChain Tier 3: Autonomous Multi-Agent Pipeline Demo")
    print("=" * 70)
    print(f"\nMode: {mode.upper()}")
    print(f"Pipeline Runs: {num_runs}")
    print(f"Artifact Directory: {artifact_dir}")
    print()
    
    # Initialize orchestrator
    orchestrator = PipelineOrchestrator(
        mode=mode,
        artifact_dir=artifact_dir,
        validation_level=ValidationLevel.STANDARD
    )
    
    results = []
    
    for i in range(num_runs):
        print(f"\n{'='*70}")
        print(f"  Pipeline Run #{i + 1}/{num_runs}")
        print(f"{'='*70}")
        
        # Create PoA submission
        poa = create_sample_poa(i)
        print(f"\n📝 PoA Submission:")
        print(f"   Submitter: {poa['submitter']}")
        print(f"   Hardware: {poa['cpu_type']} @ {poa['cpu_mhz']}MHz")
        print(f"   Hardware ID: {poa['hardware_id']}")
        
        # Determine reward tier based on miner ID
        tier = [RewardTier.MICRO, RewardTier.STANDARD, RewardTier.MAJOR, RewardTier.CRITICAL][i % 4]
        print(f"   Reward Tier: {tier.value.upper()}")
        
        # Execute pipeline
        execution = orchestrator.execute_pipeline(poa, reward_tier=tier)
        
        # Display results
        print(f"\n{'✓' if execution.status == 'completed' else '✗'} Status: {execution.status.upper()}")
        print(f"⏱  Duration: {execution.duration_ms:.2f}ms")
        
        if execution.validation_result:
            score = execution.validation_result.get('score', 0)
            valid = execution.validation_result.get('valid', False)
            print(f"🔍 Validation: {'PASSED' if valid else 'FAILED'} (Score: {score:.1f})")
        
        if execution.settlement_result:
            block = execution.settlement_result.get('block_height', 0)
            confirmations = execution.settlement_result.get('confirmations', 0)
            print(f"⛓️  Settlement: Block #{block} ({confirmations} confirmations)")
        
        if execution.reward_result:
            amount = execution.reward_result.get('amount', 0)
            tier_name = execution.reward_result.get('tier', 'unknown')
            print(f"💰 Reward: {amount:.2f} RTC ({tier_name} tier)")
        
        if execution.artifacts:
            print(f"📁 Artifacts: {len(execution.artifacts)} files generated")
        
        if execution.errors:
            print(f"⚠️  Errors: {execution.errors}")
        
        results.append({
            "run": i + 1,
            "status": execution.status,
            "duration_ms": execution.duration_ms,
            "validation_score": execution.validation_result.get('score') if execution.validation_result else None,
            "reward_amount": execution.reward_result.get('amount') if execution.reward_result else None
        })
    
    # Summary
    print(f"\n{'='*70}")
    print("  DEMO SUMMARY")
    print(f"{'='*70}")
    
    stats = orchestrator.get_stats()
    print(f"\n📊 Pipeline Statistics:")
    print(f"   Total Executions: {stats['total_executions']}")
    print(f"   Successful: {stats['successful']}")
    print(f"   Failed: {stats['failed']}")
    print(f"   Success Rate: {stats['success_rate']}%")
    print(f"   Average Duration: {stats['average_duration_ms']:.2f}ms")
    
    print(f"\n🤖 Agent Statistics:")
    print(f"   Validator: {stats['validator_stats']['total_validated']} validated, "
          f"{stats['validator_stats']['total_rejected']} rejected")
    print(f"   Settlement: {stats['settlement_stats']['total_settled']} settled")
    print(f"   Reward: {stats['reward_stats']['total_distributed']} distributions, "
          f"{stats['reward_stats']['total_recipients']} recipients")
    
    # Export report
    report_path = orchestrator.export_full_report()
    print(f"\n📄 Full Report: {report_path}")
    
    # Display results table
    print(f"\n{'='*70}")
    print("  EXECUTION RESULTS")
    print(f"{'='*70}")
    print(f"{'Run':<5} {'Status':<12} {'Duration':<15} {'Score':<10} {'Reward':<10}")
    print(f"{'-'*70}")
    for r in results:
        score_str = f"{r['validation_score']:.1f}" if r['validation_score'] else "N/A"
        reward_str = f"{r['reward_amount']:.2f}" if r['reward_amount'] else "N/A"
        print(f"{r['run']:<5} {r['status']:<12} {r['duration_ms']:<15.2f} {score_str:<10} {reward_str:<10}")
    
    print(f"\n{'='*70}")
    print("  Demo completed successfully!")
    print(f"{'='*70}\n")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="RustChain Tier 3 Multi-Agent Pipeline Demo"
    )
    parser.add_argument(
        "--mode",
        choices=["mock", "real"],
        default="mock",
        help="Operation mode (default: mock)"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of pipeline runs (default: 3)"
    )
    parser.add_argument(
        "--artifact-dir",
        type=str,
        default="./artifacts",
        help="Directory for artifacts (default: ./artifacts)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    run_demo(
        mode=args.mode,
        num_runs=args.runs,
        artifact_dir=args.artifact_dir
    )


if __name__ == "__main__":
    main()
