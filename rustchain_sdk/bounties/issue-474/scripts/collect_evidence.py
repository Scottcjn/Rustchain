#!/usr/bin/env python3
"""
Generate evidence for bounty submission.

Collects simulation results, verification proofs, and test outcomes.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

def run_command(cmd, capture=True):
    """Run a shell command."""
    result = subprocess.run(
        cmd, 
        shell=True, 
        capture_output=capture, 
        text=True
    )
    return result.returncode, result.stdout, result.stderr

def main():
    script_dir = Path(__file__).parent.parent
    evidence_dir = script_dir / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    
    print("Collecting evidence for Issue #474...")
    print()
    
    # 1. Generate replay log
    print("1. Generating replay log...")
    replay_log_path = evidence_dir / "replay_log.json"
    code, out, err = run_command(
        f"python3 src/cross_node_replay.py --record --seed 42 --epochs 5 --nodes 3 --output {replay_log_path}"
    )
    if code != 0:
        print(f"Error generating replay log: {err}")
        return 1
    print(f"   Created: {replay_log_path}")
    
    # 2. Verify determinism
    print("2. Verifying determinism...")
    verification_path = evidence_dir / "verification.json"
    code, out, err = run_command(
        f"python3 src/cross_node_replay.py --verify {replay_log_path} --output {verification_path}"
    )
    if code != 0:
        print(f"Error verifying determinism: {err}")
        return 1
    print(f"   Created: {verification_path}")
    
    # 3. Run test suite
    print("3. Running test suite...")
    test_output_path = evidence_dir / "test_results.txt"
    code, out, err = run_command(
        f"python3 -m pytest tests/ -v --tb=short"
    )
    with open(test_output_path, 'w') as f:
        f.write(out)
        f.write(err)
    if code != 0:
        print(f"Tests failed! Check {test_output_path}")
        return 1
    print(f"   Created: {test_output_path}")
    
    # 4. Generate summary
    print("4. Generating summary...")
    
    # Load verification result
    with open(verification_path) as f:
        verification = json.load(f)
        
    # Load replay log
    with open(replay_log_path) as f:
        replay_log = json.load(f)
    
    summary = {
        "bounty": "issue-474",
        "title": "Epoch Determinism Simulator + Cross-Node Replay Harness",
        "generated_at": int(time.time() * 1000),
        "simulation": {
            "seed": replay_log["seed"],
            "epochs": replay_log["total_epochs"],
            "slots": replay_log["total_slots"],
            "events": replay_log["total_events"],
            "nodes": replay_log["node_count"],
            "expected_final_hash": replay_log["expected_final_hash"]
        },
        "verification": {
            "deterministic": verification.get("deterministic", True),
            "message": verification.get("message", "Verified")
        },
        "tests": {
            "passed": True,
            "output_file": "test_results.txt"
        },
        "files": [
            "src/epoch_determinism_simulator.py",
            "src/cross_node_replay.py",
            "tests/test_epoch_simulator.py",
            "tests/test_cross_node_replay.py",
            "tests/conftest.py",
            "fixtures/scenario_basic.json",
            "fixtures/scenario_single_miner.json",
            "fixtures/scenario_stress.json",
            "fixtures/scenario_seed_test.json",
            "README.md",
            "docs/IMPLEMENTATION.md",
            "docs/RUNBOOK.md"
        ]
    }
    
    summary_path = evidence_dir / "summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"   Created: {summary_path}")
    
    # 5. List evidence
    print()
    print("Evidence collected:")
    for f in sorted(evidence_dir.iterdir()):
        size = f.stat().st_size
        print(f"   {f.name}: {size} bytes")
    
    print()
    print("Evidence collection complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
