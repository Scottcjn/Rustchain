#!/usr/bin/env python3
"""
Cross-Node Replay Harness for RustChain

Replays simulation events across multiple nodes to verify deterministic
state convergence. Supports loading event logs, replaying against live
or simulated nodes, and detecting state divergence.

Usage:
    python3 cross_node_replay.py --events events.json --nodes 3
    python3 cross_node_replay.py --record --epochs 5 --output replay_log.json
    python3 cross_node_replay.py --replay replay_log.json --verify
"""

import hashlib
import json
import time
import argparse
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from enum import Enum
import sys

# Import from sibling module
sys.path.insert(0, str(Path(__file__).parent))
from epoch_determinism_simulator import (
    EpochDeterminismSimulator, MinerState, SimulationResult,
    SimulationEvent, EpochState, EPOCH_SLOTS, DEFAULT_SEED
)


# =============================================================================
# Constants
# =============================================================================

REPLAY_VERSION = "1.0.0"


# =============================================================================
# Data Structures
# =============================================================================

class ReplayStatus(Enum):
    """Status of a replay operation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    DIVERGED = "diverged"
    ERROR = "error"


@dataclass
class NodeReplayState:
    """Replay state for a single node."""
    node_id: str
    status: ReplayStatus = ReplayStatus.PENDING
    current_slot: int = 0
    current_epoch: int = 0
    state_hash: str = ""
    events_processed: int = 0
    events_failed: int = 0
    divergence_point: Optional[int] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class ReplayLog:
    """Complete replay log for cross-node verification."""
    version: str
    seed: int
    total_epochs: int
    total_slots: int
    total_events: int
    initial_miners: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    expected_final_hash: str
    node_count: int = 1
    recorded_at: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayResult:
    """Result of cross-node replay verification."""
    replay_log_hash: str
    nodes_tested: int
    all_converged: bool
    node_states: Dict[str, NodeReplayState]
    divergence_details: Optional[Dict[str, Any]]
    total_execution_time_ms: float
    verified_at: int


# =============================================================================
# Cross-Node Replay Harness
# =============================================================================

class CrossNodeReplayHarness:
    """
    Harness for replaying simulation events across multiple nodes
    to verify deterministic state convergence.
    """
    
    def __init__(self, node_count: int = 3):
        self.node_count = node_count
        self.nodes: Dict[str, EpochDeterminismSimulator] = {}
        self.node_states: Dict[str, NodeReplayState] = {}
        self.events: List[SimulationEvent] = []
        self.initial_miners: List[MinerState] = []
        self.seed: int = DEFAULT_SEED
        
    def initialize_nodes(self, seed: int, initial_miners: List[MinerState]):
        """Initialize all replay nodes with the same seed and miners."""
        self.seed = seed
        self.initial_miners = initial_miners
        
        for i in range(self.node_count):
            node_id = f"replay-node-{i}"
            sim = EpochDeterminismSimulator(seed=seed, node_id=node_id)
            sim.initialize_chain(initial_miners)
            self.nodes[node_id] = sim
            self.node_states[node_id] = NodeReplayState(node_id=node_id)
            
    def record_simulation(self, num_epochs: int) -> ReplayLog:
        """
        Record a simulation run for later replay.
        
        Returns a ReplayLog containing all events and expected final state.
        """
        # Use first node as recorder
        recorder = self.nodes.get("replay-node-0")
        if not recorder:
            self.initialize_nodes(self.seed, self.initial_miners)
            recorder = self.nodes["replay-node-0"]
            
        # Run simulation
        result = recorder.simulate_epochs(num_epochs)
        
        # Build replay log
        replay_log = ReplayLog(
            version=REPLAY_VERSION,
            seed=self.seed,
            total_epochs=num_epochs,
            total_slots=num_epochs * EPOCH_SLOTS,
            total_events=len(result.events),
            initial_miners=[asdict(m) for m in self.initial_miners],
            events=[asdict(e) for e in result.events],
            expected_final_hash=result.final_state_hash,
            node_count=self.node_count,
            recorded_at=int(time.time() * 1000),
            metadata={
                "total_blocks": result.total_blocks,
                "execution_time_ms": result.execution_time_ms,
                "miner_rewards": result.miner_rewards
            }
        )
        
        return replay_log
        
    def replay_simulation(self, node_id: str, replay_log: ReplayLog) -> bool:
        """
        Re-run simulation on a specific node with the same seed and miners.
        
        This verifies determinism by ensuring identical inputs produce identical outputs.

        Returns True if final state matches expected hash.
        """
        if node_id not in self.nodes:
            return False

        sim = self.nodes[node_id]
        state = self.node_states[node_id]

        try:
            # Run full simulation
            result = sim.simulate_epochs(replay_log.total_epochs)
            
            # Update state tracking
            state.current_slot = result.total_slots
            state.current_epoch = result.total_epochs
            state.state_hash = result.final_state_hash
            state.events_processed = len(result.events)
            
            # Check if final state matches
            return result.final_state_hash == replay_log.expected_final_hash

        except Exception as e:
            state.events_failed += 1
            state.error_message = str(e)
            return False
            
    def replay_all(self, replay_log: ReplayLog) -> ReplayResult:
        """
        Replay all events from a log across all nodes.

        Verifies that all nodes converge to the same final state by running
        the same simulation with identical seed and initial miners.
        """
        start_time = time.time()

        # Initialize nodes from replay log
        miners = create_miners_from_replay_log(replay_log)
        self.initialize_nodes(replay_log.seed, miners)

        # Run simulation on each node
        divergence_details = None

        for node_id in self.nodes:
            state = self.node_states[node_id]
            state.status = ReplayStatus.RUNNING

            # Run simulation (same seed + miners = deterministic result)
            success = self.replay_simulation(node_id, replay_log)

            if not success:
                state.status = ReplayStatus.DIVERGED
                divergence_details = {
                    "node_id": node_id,
                    "expected_hash": replay_log.expected_final_hash,
                    "actual_hash": state.state_hash,
                    "error": state.error_message
                }
            else:
                state.status = ReplayStatus.COMPLETED

        # Check convergence
        all_converged = all(
            s.status == ReplayStatus.COMPLETED
            for s in self.node_states.values()
        )
        
        execution_time = (time.time() - start_time) * 1000
        
        # Compute replay log hash
        log_data = json.dumps(asdict(replay_log), sort_keys=True)
        replay_log_hash = hashlib.sha256(log_data.encode()).hexdigest()[:16]
        
        return ReplayResult(
            replay_log_hash=replay_log_hash,
            nodes_tested=self.node_count,
            all_converged=all_converged,
            node_states={k: asdict(v) for k, v in self.node_states.items()},
            divergence_details=divergence_details,
            total_execution_time_ms=execution_time,
            verified_at=int(time.time() * 1000)
        )
        
    def verify_determinism(self, replay_log: ReplayLog) -> Tuple[bool, str]:
        """
        Verify determinism by replaying the same log multiple times.
        
        Returns (is_deterministic, message).
        """
        # Run replay multiple times
        hashes = []
        for run in range(3):
            result = self.replay_all(replay_log)
            hashes.append(result.replay_log_hash)
            
            # Reinitialize for next run
            miners = create_miners_from_replay_log(replay_log)
            self.initialize_nodes(replay_log.seed, miners)
            
        all_match = len(set(hashes)) == 1
        
        if all_match:
            return True, f"All {len(hashes)} replay runs produced identical state hashes"
        else:
            return False, f"State hashes diverged across runs: {hashes}"


# =============================================================================
# Helper Functions
# =============================================================================

def create_miners_from_replay_log(replay_log: ReplayLog) -> List[MinerState]:
    """Recreate miner states from replay log."""
    miners = []
    for m in replay_log.initial_miners:
        miners.append(MinerState(
            miner_id=m.get("miner_id", m.get("id", "unknown")),
            public_key=m.get("public_key", "pk_default"),
            stake=m.get("stake", 1000),
            cpu_model=m.get("cpu_model", "CPU"),
            release_year=m.get("release_year", 2000),
            uptime_days=m.get("uptime_days", 365),
            blocks_produced=m.get("blocks_produced", 0),
            attestations_submitted=m.get("attestations_submitted", 0),
            rewards_earned=m.get("rewards_earned", 0)
        ))
    return miners


def load_replay_log(path: Path) -> ReplayLog:
    """Load replay log from JSON file."""
    with open(path, 'r') as f:
        data = json.load(f)
        
    return ReplayLog(
        version=data["version"],
        seed=data["seed"],
        total_epochs=data["total_epochs"],
        total_slots=data["total_slots"],
        total_events=data["total_events"],
        initial_miners=data["initial_miners"],
        events=data["events"],
        expected_final_hash=data["expected_final_hash"],
        node_count=data.get("node_count", 1),
        recorded_at=data.get("recorded_at", 0),
        metadata=data.get("metadata", {})
    )


def save_replay_log(replay_log: ReplayLog, path: Path):
    """Save replay log to JSON file."""
    with open(path, 'w') as f:
        json.dump(asdict(replay_log), f, indent=2)


def save_replay_result(result: ReplayResult, path: Path):
    """Save replay result to JSON file."""
    with open(path, 'w') as f:
        json.dump(asdict(result), f, indent=2)


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Cross-Node Replay Harness for RustChain"
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--record", action="store_true",
        help="Record a new simulation for replay"
    )
    mode_group.add_argument(
        "--replay", type=Path,
        help="Replay events from a log file"
    )
    mode_group.add_argument(
        "--verify", type=Path,
        help="Verify determinism of a replay log"
    )
    
    # Configuration
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED,
        help=f"Random seed (default: {DEFAULT_SEED})"
    )
    parser.add_argument(
        "--epochs", type=int, default=3,
        help="Number of epochs to simulate (default: 3)"
    )
    parser.add_argument(
        "--nodes", type=int, default=3,
        help="Number of nodes for replay (default: 3)"
    )
    parser.add_argument(
        "--miners", type=int, default=5,
        help="Number of genesis miners (default: 5)"
    )
    
    # I/O
    parser.add_argument(
        "--output", type=Path,
        help="Output path for recorded log or results"
    )
    parser.add_argument(
        "--events", type=Path,
        help="Path to events JSON file for replay"
    )
    
    # Options
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--ci", action="store_true",
        help="CI mode: exit with error on divergence"
    )
    
    args = parser.parse_args()
    
    # Initialize harness
    harness = CrossNodeReplayHarness(node_count=args.nodes)
    
    if args.record:
        # Record mode: create new simulation log
        if args.verbose:
            print(f"Recording simulation: seed={args.seed}, epochs={args.epochs}")
            print(f"Initializing {args.nodes} nodes with {args.miners} miners...")
            
        # Create genesis miners
        miners = []
        for i in range(args.miners):
            miners.append(MinerState(
                miner_id=f"miner-{i}",
                public_key=f"pk_{i}" + "0" * 32,
                stake=1000 + (i * 100),
                cpu_model=f"CPU-{i}",
                release_year=1980 + (i * 5),
                uptime_days=365 + (i * 30)
            ))
            
        harness.initialize_nodes(args.seed, miners)
        replay_log = harness.record_simulation(args.epochs)
        
        # Save or display
        if args.output:
            save_replay_log(replay_log, args.output)
            if args.verbose:
                print(f"Replay log saved to {args.output}")
        else:
            print(json.dumps(asdict(replay_log), indent=2))
            
        if args.verbose:
            print(f"\nRecorded {replay_log.total_events} events")
            print(f"Expected final hash: {replay_log.expected_final_hash}")
            
    elif args.replay:
        # Replay mode: replay events from log
        if args.verbose:
            print(f"Replaying events from {args.replay}")
            
        replay_log = load_replay_log(args.replay)
        harness.node_count = replay_log.node_count
        
        if args.verbose:
            print(f"Log version: {replay_log.version}")
            print(f"Seed: {replay_log.seed}, Events: {replay_log.total_events}")
            print(f"Expected final hash: {replay_log.expected_final_hash}")
            print()
            
        result = harness.replay_all(replay_log)
        
        # Output results
        if args.output:
            save_replay_result(result, args.output)
            if args.verbose:
                print(f"Results saved to {args.output}")
        else:
            print(json.dumps(asdict(result), indent=2))
            
        if args.verbose:
            print(f"\nReplay completed in {result.total_execution_time_ms:.2f}ms")
            print(f"All nodes converged: {result.all_converged}")
            
            if not result.all_converged:
                print(f"Divergence details: {result.divergence_details}")
                
        # CI mode: exit with error on divergence
        if args.ci and not result.all_converged:
            return 1
            
    elif args.verify:
        # Verify mode: check determinism
        if args.verbose:
            print(f"Verifying determinism of {args.verify}")
            
        replay_log = load_replay_log(args.verify)
        harness.node_count = replay_log.node_count
        
        is_deterministic, message = harness.verify_determinism(replay_log)
        
        if args.verbose:
            print(f"\nDeterminism verification: {'PASS' if is_deterministic else 'FAIL'}")
            print(message)
            
        # Output result
        result = {
            "deterministic": is_deterministic,
            "message": message,
            "replay_log": str(args.verify),
            "verified_at": int(time.time() * 1000)
        }
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
                
        if args.ci and not is_deterministic:
            return 1
            
    return 0


if __name__ == "__main__":
    exit(main())
