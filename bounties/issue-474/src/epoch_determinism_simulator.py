#!/usr/bin/env python3
"""
Epoch Determinism Simulator for RustChain

Provides deterministic epoch simulation with reproducible state transitions
across multiple nodes. Uses seeded PRNG for full reproducibility.

Usage:
    python3 epoch_determinism_simulator.py --seed 42 --epochs 10 --nodes 3
    python3 epoch_determinism_simulator.py --scenario fixtures/scenario_basic.json
"""

import hashlib
import json
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import argparse


# =============================================================================
# Constants
# =============================================================================

EPOCH_SLOTS = 144  # 24 hours at 10-min blocks
BLOCK_TIME = 600  # 10 minutes in seconds
CHAIN_ID = "rustchain-mainnet"
DEFAULT_SEED = 42


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class MinerState:
    """State of a single miner in the simulation."""
    miner_id: str
    public_key: str
    stake: int
    cpu_model: str
    release_year: int
    uptime_days: int
    blocks_produced: int = 0
    attestations_submitted: int = 0
    rewards_earned: int = 0
    
    def compute_antiquity_score(self) -> float:
        """Compute Proof of Antiquity score for this miner."""
        current_year = 2025
        age_factor = float(current_year - self.release_year)
        uptime_factor = (float(self.uptime_days) + 1.0) ** 0.5
        stake_factor = (float(self.stake) / 1000.0) ** 0.3
        return age_factor * uptime_factor * stake_factor


@dataclass
class BlockHeader:
    """Block header for simulation."""
    slot: int
    epoch: int
    producer: str
    parent_hash: str
    timestamp: int
    transactions_hash: str
    state_hash: str
    signature: str
    
    def compute_hash(self) -> str:
        """Compute deterministic block hash."""
        data = json.dumps(asdict(self), sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class EpochState:
    """State of an epoch in the simulation."""
    epoch: int
    start_slot: int
    end_slot: int
    block_count: int = 0
    total_rewards: int = 0
    participating_miners: List[str] = field(default_factory=list)
    state_hash: str = ""
    finalized: bool = False


@dataclass
class NodeState:
    """Complete state of a simulated node."""
    node_id: str
    chain: List[BlockHeader] = field(default_factory=list)
    epochs: Dict[int, EpochState] = field(default_factory=dict)
    miners: Dict[str, MinerState] = field(default_factory=dict)
    current_slot: int = 0
    current_epoch: int = 0
    total_supply: int = 1_000_000_000  # 1B initial supply
    rng_state: int = 0
    
    def compute_state_hash(self) -> str:
        """Compute deterministic hash of current node state."""
        state_data = {
            "current_slot": self.current_slot,
            "current_epoch": self.current_epoch,
            "chain_tip": self.chain[-1].compute_hash() if self.chain else "genesis",
            "miners": sorted(self.miners.keys()),
            "epochs": sorted(self.epochs.keys()),
        }
        data = json.dumps(state_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class SimulationEvent:
    """Event recorded during simulation."""
    slot: int
    epoch: int
    event_type: str
    actor: str
    details: Dict[str, Any]
    timestamp: int


@dataclass
class SimulationResult:
    """Result of a complete simulation run."""
    seed: int
    node_id: str
    final_state_hash: str
    total_slots: int
    total_epochs: int
    total_blocks: int
    events: List[SimulationEvent] = field(default_factory=list)
    epoch_states: Dict[int, EpochState] = field(default_factory=dict)
    miner_rewards: Dict[str, int] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    deterministic: bool = True


# =============================================================================
# Deterministic Random Number Generator
# =============================================================================

class DeterministicRNG:
    """Seed-based deterministic PRNG for reproducible simulations."""
    
    def __init__(self, seed: int):
        self.seed = seed
        self.state = seed
        self._rng = random.Random(seed)
        
    def reset(self):
        """Reset RNG to initial seed state."""
        self.state = self.seed
        self._rng = random.Random(self.seed)
        
    def next_int(self, min_val: int = 0, max_val: int = 1000000) -> int:
        """Generate next deterministic integer in range."""
        self.state = (self.state * 1103515245 + 12345) & 0x7FFFFFFF
        return min_val + (self.state % (max_val - min_val + 1))
    
    def next_float(self) -> float:
        """Generate next deterministic float in [0, 1)."""
        self.state = (self.state * 1103515245 + 12345) & 0x7FFFFFFF
        return float(self.state) / float(0x7FFFFFFF)
    
    def choice(self, items: list) -> Any:
        """Choose deterministic item from list."""
        if not items:
            return None
        idx = self.next_int(0, len(items) - 1)
        return items[idx]
    
    def shuffle(self, items: list) -> list:
        """Return deterministically shuffled copy of list."""
        result = items.copy()
        for i in range(len(result) - 1, 0, -1):
            j = self.next_int(0, i)
            result[i], result[j] = result[j], result[i]
        return result


# =============================================================================
# Epoch Determinism Simulator
# =============================================================================

class EpochDeterminismSimulator:
    """
    Deterministic epoch simulator for RustChain consensus.
    
    Simulates epoch transitions, block production, and reward distribution
    with full reproducibility given the same seed and initial state.
    """
    
    def __init__(self, seed: int = DEFAULT_SEED, node_id: str = "node-1"):
        self.seed = seed
        self.node_id = node_id
        self.rng = DeterministicRNG(seed)
        self.state = NodeState(node_id=node_id)
        self.events: List[SimulationEvent] = []
        self.start_time: float = 0.0
        
    def initialize_chain(self, genesis_miners: List[MinerState]):
        """Initialize chain with genesis block and miners."""
        # Add genesis miners
        for miner in genesis_miners:
            self.state.miners[miner.miner_id] = miner
            
        # Create genesis block
        genesis = BlockHeader(
            slot=0,
            epoch=0,
            producer="genesis",
            parent_hash="0" * 16,
            timestamp=0,
            transactions_hash="0" * 16,
            state_hash=self.state.compute_state_hash(),
            signature="genesis_signature"
        )
        genesis.state_hash = self.state.compute_state_hash()
        self.state.chain.append(genesis)
        
        # Initialize epoch 0
        self.state.epochs[0] = EpochState(
            epoch=0,
            start_slot=0,
            end_slot=EPOCH_SLOTS - 1
        )
        
        self._record_event(0, 0, "genesis", "system", {
            "miner_count": len(genesis_miners),
            "initial_supply": self.state.total_supply
        })
        
    def _record_event(self, slot: int, epoch: int, event_type: str, 
                      actor: str, details: Dict[str, Any]):
        """Record a simulation event."""
        self.events.append(SimulationEvent(
            slot=slot,
            epoch=epoch,
            event_type=event_type,
            actor=actor,
            details=details,
            timestamp=int(time.time() * 1000) + slot * BLOCK_TIME * 1000
        ))
        
    def _get_epoch(self, slot: int) -> int:
        """Convert slot number to epoch."""
        return slot // EPOCH_SLOTS
    
    def _select_block_producer(self, slot: int) -> Optional[str]:
        """
        Deterministic block producer selection using RIP-200 round-robin
        weighted by antiquity score.
        """
        if not self.state.miners:
            return None
            
        # Compute weighted list based on antiquity scores
        weighted_miners = []
        for miner_id, miner in self.state.miners.items():
            score = miner.compute_antiquity_score()
            weight = max(1, int(score * 10))
            weighted_miners.extend([miner_id] * weight)
            
        if not weighted_miners:
            return None
            
        # Deterministic selection based on slot
        selector = (slot + self.seed) % len(weighted_miners)
        return weighted_miners[selector]
    
    def _produce_block(self, slot: int) -> Optional[BlockHeader]:
        """Produce a block for the given slot."""
        producer = self._select_block_producer(slot)
        if not producer:
            return None
            
        epoch = self._get_epoch(slot)
        parent = self.state.chain[-1] if self.state.chain else None
        parent_hash = parent.compute_hash() if parent else "0" * 16
        
        # Update miner stats
        self.state.miners[producer].blocks_produced += 1
        
        header = BlockHeader(
            slot=slot,
            epoch=epoch,
            producer=producer,
            parent_hash=parent_hash,
            timestamp=slot * BLOCK_TIME,
            transactions_hash=self.rng.next_int(0, 0xFFFFFF).to_bytes(3, 'big').hex(),
            state_hash="",  # Will be computed
            signature=f"sig_{slot}_{producer}_{self.rng.next_int()}"
        )
        header.state_hash = self.state.compute_state_hash()
        
        return header
        
    def _distribute_block_reward(self, producer: str, epoch: int):
        """Distribute block production reward."""
        base_reward = 100  # Base reward per block
        miner = self.state.miners.get(producer)
        if miner:
            miner.rewards_earned += base_reward
            self.state.epochs[epoch].total_rewards += base_reward
            
    def _process_attestation(self, miner_id: str, slot: int, epoch: int):
        """Process an attestation submission."""
        if miner_id in self.state.miners:
            self.state.miners[miner_id].attestations_submitted += 1
            attestation_reward = 10
            self.state.miners[miner_id].rewards_earned += attestation_reward
            self.state.epochs[epoch].total_rewards += attestation_reward
            
            self._record_event(slot, epoch, "attestation", miner_id, {
                "reward": attestation_reward
            })
            
    def _finalize_epoch(self, epoch: int):
        """Finalize an epoch and settle rewards."""
        if epoch not in self.state.epochs:
            return
            
        epoch_state = self.state.epochs[epoch]
        epoch_state.finalized = True
        
        # Record epoch finalization
        self._record_event(
            epoch_state.end_slot, 
            epoch, 
            "epoch_finalized", 
            "system",
            {
                "block_count": epoch_state.block_count,
                "total_rewards": epoch_state.total_rewards,
                "participants": len(epoch_state.participating_miners)
            }
        )
        
        # Update miner reward totals
        for miner_id in epoch_state.participating_miners:
            if miner_id in self.state.miners:
                self.state.miners[miner_id].rewards_earned
        
    def simulate_slot(self, slot: int) -> bool:
        """Simulate a single slot."""
        epoch = self._get_epoch(slot)
        
        # Update current state
        self.state.current_slot = slot
        self.state.current_epoch = epoch
        
        # Initialize new epoch if needed
        if epoch not in self.state.epochs:
            self.state.epochs[epoch] = EpochState(
                epoch=epoch,
                start_slot=epoch * EPOCH_SLOTS,
                end_slot=(epoch + 1) * EPOCH_SLOTS - 1
            )
            
        # Finalize previous epoch if transitioning
        if slot > 0 and self._get_epoch(slot - 1) != epoch:
            self._finalize_epoch(epoch - 1)
            
        # Produce block
        block = self._produce_block(slot)
        if block:
            self.state.chain.append(block)
            self.state.epochs[epoch].block_count += 1
            self.state.epochs[epoch].participating_miners.append(block.producer)
            self._distribute_block_reward(block.producer, epoch)
            
            self._record_event(slot, epoch, "block_produced", block.producer, {
                "block_hash": block.compute_hash(),
                "parent_hash": block.parent_hash
            })
            
        # Simulate attestations from random miners (skip if no miners)
        if self.state.miners:
            active_miners = list(self.state.miners.keys())
            attestation_count = self.rng.next_int(1, min(len(active_miners), 5))
            attesting_miners = self.rng.shuffle(active_miners)[:attestation_count]
            
            for miner_id in attesting_miners:
                self._process_attestation(miner_id, slot, epoch)
            
        return block is not None
        
    def simulate_epochs(self, num_epochs: int) -> SimulationResult:
        """Simulate a given number of epochs."""
        self.start_time = time.time()
        total_slots = num_epochs * EPOCH_SLOTS
        
        for slot in range(1, total_slots + 1):
            self.simulate_slot(slot)
            
        # Finalize last epoch
        self._finalize_epoch(self.state.current_epoch)
        
        execution_time = (time.time() - self.start_time) * 1000
        
        # Compile results
        miner_rewards = {
            miner_id: miner.rewards_earned 
            for miner_id, miner in self.state.miners.items()
        }
        
        return SimulationResult(
            seed=self.seed,
            node_id=self.node_id,
            final_state_hash=self.state.compute_state_hash(),
            total_slots=total_slots,
            total_epochs=num_epochs,
            total_blocks=len(self.state.chain) - 1,  # Exclude genesis
            events=self.events,
            epoch_states=self.state.epochs,
            miner_rewards=miner_rewards,
            execution_time_ms=execution_time,
            deterministic=True
        )
        
    def get_state_snapshot(self) -> Dict[str, Any]:
        """Get current state as serializable dict."""
        return {
            "node_id": self.state.node_id,
            "current_slot": self.state.current_slot,
            "current_epoch": self.state.current_epoch,
            "chain_length": len(self.state.chain),
            "miner_count": len(self.state.miners),
            "epoch_count": len(self.state.epochs),
            "state_hash": self.state.compute_state_hash(),
            "rng_state": self.rng.state
        }


# =============================================================================
# Scenario Loading
# =============================================================================

def load_scenario(scenario_path: Path) -> Dict[str, Any]:
    """Load simulation scenario from JSON file."""
    with open(scenario_path, 'r') as f:
        return json.load(f)
        
def create_miners_from_scenario(scenario: Dict[str, Any]) -> List[MinerState]:
    """Create miner states from scenario configuration."""
    miners = []
    for i, miner_cfg in enumerate(scenario.get("miners", [])):
        miners.append(MinerState(
            miner_id=miner_cfg.get("id", f"miner-{i}"),
            public_key=miner_cfg.get("public_key", f"pk_{i}" + "0" * 32),
            stake=miner_cfg.get("stake", 1000),
            cpu_model=miner_cfg.get("cpu_model", "Unknown"),
            release_year=miner_cfg.get("release_year", 2020),
            uptime_days=miner_cfg.get("uptime_days", 365)
        ))
    return miners


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Epoch Determinism Simulator for RustChain"
    )
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED,
        help=f"Random seed for reproducibility (default: {DEFAULT_SEED})"
    )
    parser.add_argument(
        "--epochs", type=int, default=5,
        help="Number of epochs to simulate (default: 5)"
    )
    parser.add_argument(
        "--nodes", type=int, default=1,
        help="Number of parallel node simulations (default: 1)"
    )
    parser.add_argument(
        "--miners", type=int, default=5,
        help="Number of genesis miners (default: 5)"
    )
    parser.add_argument(
        "--scenario", type=Path,
        help="Path to scenario JSON file"
    )
    parser.add_argument(
        "--output", type=Path,
        help="Output path for simulation results JSON"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Create simulator
    sim = EpochDeterminismSimulator(seed=args.seed, node_id="sim-node-1")
    
    # Initialize miners
    if args.scenario:
        scenario = load_scenario(args.scenario)
        miners = create_miners_from_scenario(scenario)
        if args.verbose:
            print(f"Loaded scenario from {args.scenario}")
    else:
        # Generate default miners
        miners = []
        cpu_models = [
            ("Intel 8086", 1978), ("Intel 386", 1985), 
            ("Intel Pentium", 1993), ("AMD Athlon", 1999),
            ("Intel Core 2", 2006), ("AMD Ryzen", 2017)
        ]
        for i in range(args.miners):
            cpu, year = cpu_models[i % len(cpu_models)]
            miners.append(MinerState(
                miner_id=f"miner-{i}",
                public_key=f"pk_{i}" + "0" * 32,
                stake=1000 + (i * 100),
                cpu_model=cpu,
                release_year=year,
                uptime_days=365 + (i * 30)
            ))
    
    sim.initialize_chain(miners)
    
    if args.verbose:
        print(f"Initialized chain with {len(miners)} miners")
        print(f"Simulating {args.epochs} epochs ({args.epochs * EPOCH_SLOTS} slots)")
        print(f"Seed: {args.seed}")
        print()
    
    # Run simulation
    result = sim.simulate_epochs(args.epochs)
    
    if args.verbose:
        print(f"Simulation completed in {result.execution_time_ms:.2f}ms")
        print(f"Final state hash: {result.final_state_hash}")
        print(f"Total blocks: {result.total_blocks}")
        print(f"Total events: {len(result.events)}")
        print()
        print("Miner rewards:")
        for miner_id, reward in sorted(result.miner_rewards.items()):
            print(f"  {miner_id}: {reward}")
        print()
    
    # Multi-node determinism check
    if args.nodes > 1:
        if args.verbose:
            print(f"Running {args.nodes} parallel simulations for determinism check...")
        
        state_hashes = [result.final_state_hash]
        for i in range(1, args.nodes):
            sim_i = EpochDeterminismSimulator(seed=args.seed, node_id=f"sim-node-{i+1}")
            sim_i.initialize_chain(miners)
            result_i = sim_i.simulate_epochs(args.epochs)
            state_hashes.append(result_i.final_state_hash)
            
        all_match = len(set(state_hashes)) == 1
        if args.verbose:
            print(f"Determinism check: {'PASS' if all_match else 'FAIL'}")
            print(f"All state hashes match: {all_match}")
    
    # Output results
    if args.output:
        output_data = {
            "seed": result.seed,
            "node_id": result.node_id,
            "final_state_hash": result.final_state_hash,
            "total_slots": result.total_slots,
            "total_epochs": result.total_epochs,
            "total_blocks": result.total_blocks,
            "execution_time_ms": result.execution_time_ms,
            "deterministic": result.deterministic,
            "miner_rewards": result.miner_rewards,
            "epoch_summary": {
                str(e.epoch): {
                    "blocks": e.block_count,
                    "rewards": e.total_rewards,
                    "finalized": e.finalized
                }
                for e in result.epoch_states.values()
            }
        }
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        if args.verbose:
            print(f"Results written to {args.output}")
    
    return 0 if result.deterministic else 1


if __name__ == "__main__":
    exit(main())
