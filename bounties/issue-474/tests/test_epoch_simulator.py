#!/usr/bin/env python3
"""
Unit tests for Epoch Determinism Simulator

Tests cover:
- Deterministic RNG behavior
- Miner antiquity score calculation
- Block producer selection
- Epoch transitions
- State hash consistency
"""

import json
import sys
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from epoch_determinism_simulator import (
    DeterministicRNG,
    EpochDeterminismSimulator,
    MinerState,
    BlockHeader,
    EpochState,
    EPOCH_SLOTS,
    DEFAULT_SEED
)


class TestDeterministicRNG(unittest.TestCase):
    """Tests for deterministic random number generator."""
    
    def test_reproducibility(self):
        """Same seed produces identical sequence."""
        rng1 = DeterministicRNG(seed=42)
        rng2 = DeterministicRNG(seed=42)
        
        seq1 = [rng1.next_int() for _ in range(100)]
        seq2 = [rng2.next_int() for _ in range(100)]
        
        self.assertEqual(seq1, seq2)
        
    def test_different_seeds(self):
        """Different seeds produce different sequences."""
        rng1 = DeterministicRNG(seed=42)
        rng2 = DeterministicRNG(seed=43)
        
        seq1 = [rng1.next_int() for _ in range(10)]
        seq2 = [rng2.next_int() for _ in range(10)]
        
        self.assertNotEqual(seq1, seq2)
        
    def test_reset(self):
        """Reset returns RNG to initial state."""
        rng = DeterministicRNG(seed=123)
        
        seq1 = [rng.next_int() for _ in range(50)]
        rng.reset()
        seq2 = [rng.next_int() for _ in range(50)]
        
        self.assertEqual(seq1, seq2)
        
    def test_range_bounds(self):
        """next_int respects min/max bounds."""
        rng = DeterministicRNG(seed=42)
        
        for _ in range(100):
            val = rng.next_int(10, 20)
            self.assertGreaterEqual(val, 10)
            self.assertLessEqual(val, 20)
            
    def test_choice_determinism(self):
        """choice returns deterministic items."""
        rng1 = DeterministicRNG(seed=42)
        rng2 = DeterministicRNG(seed=42)
        
        items = ["a", "b", "c", "d", "e"]
        choices1 = [rng1.choice(items) for _ in range(20)]
        choices2 = [rng2.choice(items) for _ in range(20)]
        
        self.assertEqual(choices1, choices2)


class TestMinerState(unittest.TestCase):
    """Tests for miner state and antiquity scoring."""
    
    def test_antiquity_score_vintage(self):
        """Vintage CPUs get higher scores."""
        vintage = MinerState(
            miner_id="vintage",
            public_key="pk_v",
            stake=1000,
            cpu_model="Intel 8086",
            release_year=1978,
            uptime_days=3650
        )
        
        modern = MinerState(
            miner_id="modern",
            public_key="pk_m",
            stake=1000,
            cpu_model="Intel Core",
            release_year=2020,
            uptime_days=100
        )
        
        self.assertGreater(
            vintage.compute_antiquity_score(),
            modern.compute_antiquity_score()
        )
        
    def test_antiquity_score_uptime(self):
        """Higher uptime increases score."""
        miner1 = MinerState(
            miner_id="m1",
            public_key="pk_1",
            stake=1000,
            cpu_model="CPU",
            release_year=1990,
            uptime_days=100
        )
        
        miner2 = MinerState(
            miner_id="m2",
            public_key="pk_2",
            stake=1000,
            cpu_model="CPU",
            release_year=1990,
            uptime_days=1000
        )
        
        self.assertGreater(
            miner2.compute_antiquity_score(),
            miner1.compute_antiquity_score()
        )
        
    def test_antiquity_score_stake(self):
        """Higher stake increases score (diminishing returns)."""
        miner1 = MinerState(
            miner_id="m1",
            public_key="pk_1",
            stake=1000,
            cpu_model="CPU",
            release_year=1990,
            uptime_days=365
        )
        
        miner2 = MinerState(
            miner_id="m2",
            public_key="pk_2",
            stake=10000,
            cpu_model="CPU",
            release_year=1990,
            uptime_days=365
        )
        
        self.assertGreater(
            miner2.compute_antiquity_score(),
            miner1.compute_antiquity_score()
        )


class TestBlockHeader(unittest.TestCase):
    """Tests for block header hashing."""
    
    def test_hash_determinism(self):
        """Same header produces same hash."""
        header = BlockHeader(
            slot=1,
            epoch=0,
            producer="miner-1",
            parent_hash="parent123",
            timestamp=1000,
            transactions_hash="tx456",
            state_hash="state789",
            signature="sig000"
        )
        
        hash1 = header.compute_hash()
        hash2 = header.compute_hash()
        
        self.assertEqual(hash1, hash2)
        
    def test_hash_uniqueness(self):
        """Different headers produce different hashes."""
        header1 = BlockHeader(
            slot=1,
            epoch=0,
            producer="miner-1",
            parent_hash="parent",
            timestamp=1000,
            transactions_hash="tx",
            state_hash="state",
            signature="sig1"
        )
        
        header2 = BlockHeader(
            slot=2,  # Different slot
            epoch=0,
            producer="miner-1",
            parent_hash="parent",
            timestamp=1000,
            transactions_hash="tx",
            state_hash="state",
            signature="sig1"
        )
        
        self.assertNotEqual(
            header1.compute_hash(),
            header2.compute_hash()
        )


class TestEpochDeterminismSimulator(unittest.TestCase):
    """Tests for the main simulator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.miners = [
            MinerState("m1", "pk1", 1000, "CPU1", 1980, 365),
            MinerState("m2", "pk2", 2000, "CPU2", 1985, 400),
            MinerState("m3", "pk3", 1500, "CPU3", 1990, 500),
        ]
        
    def test_initialization(self):
        """Simulator initializes with genesis block."""
        sim = EpochDeterminismSimulator(seed=42)
        sim.initialize_chain(self.miners)
        
        self.assertEqual(len(sim.state.chain), 1)  # Genesis block
        self.assertEqual(sim.state.current_slot, 0)
        self.assertEqual(sim.state.current_epoch, 0)
        self.assertEqual(len(sim.state.miners), 3)
        
    def test_slot_to_epoch(self):
        """Slot to epoch conversion is correct."""
        sim = EpochDeterminismSimulator(seed=42)
        
        self.assertEqual(sim._get_epoch(0), 0)
        self.assertEqual(sim._get_epoch(143), 0)
        self.assertEqual(sim._get_epoch(144), 1)
        self.assertEqual(sim._get_epoch(287), 1)
        self.assertEqual(sim._get_epoch(288), 2)
        
    def test_block_production(self):
        """Blocks are produced for slots."""
        sim = EpochDeterminismSimulator(seed=42)
        sim.initialize_chain(self.miners)
        
        # Simulate first slot
        produced = sim.simulate_slot(1)
        
        self.assertTrue(produced)
        self.assertEqual(len(sim.state.chain), 2)  # Genesis + 1
        self.assertEqual(sim.state.current_slot, 1)
        
    def test_deterministic_simulation(self):
        """Same seed produces identical results."""
        def run_sim():
            sim = EpochDeterminismSimulator(seed=12345)
            sim.initialize_chain(self.miners)
            result = sim.simulate_epochs(2)
            return result.final_state_hash
            
        hash1 = run_sim()
        hash2 = run_sim()
        
        self.assertEqual(hash1, hash2)
        
    def test_different_seeds_diverge(self):
        """Different seeds produce different results."""
        def run_sim(seed):
            sim = EpochDeterminismSimulator(seed=seed)
            sim.initialize_chain(self.miners)
            result = sim.simulate_epochs(2)
            return result.final_state_hash
            
        hashes = [run_sim(s) for s in [1, 42, 100, 999]]
        
        # All hashes should be unique
        self.assertEqual(len(set(hashes)), len(hashes))
        
    def test_epoch_finalization(self):
        """Epochs are finalized after completion."""
        sim = EpochDeterminismSimulator(seed=42)
        sim.initialize_chain(self.miners)
        
        # Simulate one full epoch
        result = sim.simulate_epochs(1)
        
        self.assertTrue(result.epoch_states[0].finalized)
        self.assertGreater(result.epoch_states[0].block_count, 0)
        
    def test_miner_rewards(self):
        """Miners earn rewards for blocks and attestations."""
        sim = EpochDeterminismSimulator(seed=42)
        sim.initialize_chain(self.miners)
        
        result = sim.simulate_epochs(2)
        
        # All miners should have earned something
        for miner_id, reward in result.miner_rewards.items():
            self.assertGreater(reward, 0)
            
    def test_state_hash_consistency(self):
        """State hash is consistent across simulation."""
        sim = EpochDeterminismSimulator(seed=42)
        sim.initialize_chain(self.miners)
        
        # Get initial state hash
        initial_hash = sim.state.compute_state_hash()
        
        # Simulate some slots
        for slot in range(1, 10):
            sim.simulate_slot(slot)
            
        # State hash should have changed
        final_hash = sim.state.compute_state_hash()
        self.assertNotEqual(initial_hash, final_hash)
        
    def test_multi_node_determinism(self):
        """Multiple nodes with same seed converge."""
        results = []
        
        for i in range(5):
            sim = EpochDeterminismSimulator(seed=777, node_id=f"node-{i}")
            sim.initialize_chain(self.miners)
            result = sim.simulate_epochs(3)
            results.append(result.final_state_hash)
            
        # All nodes should have identical final state
        self.assertEqual(len(set(results)), 1)


class TestScenarioLoading(unittest.TestCase):
    """Tests for scenario file loading."""
    
    def test_load_basic_scenario(self):
        """Basic scenario loads correctly."""
        scenario_path = Path(__file__).parent.parent / "fixtures" / "scenario_basic.json"
        
        if scenario_path.exists():
            with open(scenario_path) as f:
                scenario = json.load(f)
                
            self.assertIn("miners", scenario)
            self.assertIn("seed", scenario)
            self.assertGreater(len(scenario["miners"]), 0)


if __name__ == "__main__":
    unittest.main()
