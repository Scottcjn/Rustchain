#!/usr/bin/env python3
"""
Integration tests for Cross-Node Replay Harness

Tests cover:
- Event recording and replay
- Cross-node state convergence
- Determinism verification
- Divergence detection
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from epoch_determinism_simulator import (
    EpochDeterminismSimulator,
    MinerState,
    EPOCH_SLOTS,
    DEFAULT_SEED
)
from cross_node_replay import (
    CrossNodeReplayHarness,
    ReplayLog,
    ReplayStatus,
    load_replay_log,
    save_replay_log,
    create_miners_from_replay_log
)


class TestReplayLog(unittest.TestCase):
    """Tests for replay log creation and loading."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.miners = [
            MinerState("m1", "pk1", 1000, "CPU1", 1980, 365),
            MinerState("m2", "pk2", 2000, "CPU2", 1985, 400),
        ]
        
    def test_record_simulation(self):
        """Recording produces valid replay log."""
        harness = CrossNodeReplayHarness(node_count=1)
        harness.initialize_nodes(seed=42, initial_miners=self.miners)
        
        replay_log = harness.record_simulation(num_epochs=2)
        
        self.assertEqual(replay_log.seed, 42)
        self.assertEqual(replay_log.total_epochs, 2)
        self.assertEqual(replay_log.total_slots, 2 * EPOCH_SLOTS)
        self.assertGreater(replay_log.total_events, 0)
        self.assertTrue(len(replay_log.expected_final_hash) > 0)
        
    def test_replay_log_roundtrip(self):
        """Replay log survives save/load roundtrip."""
        harness = CrossNodeReplayHarness(node_count=1)
        harness.initialize_nodes(seed=42, initial_miners=self.miners)
        
        original_log = harness.record_simulation(num_epochs=1)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            save_replay_log(original_log, Path(f.name))
            temp_path = Path(f.name)
            
        try:
            loaded_log = load_replay_log(temp_path)
            
            self.assertEqual(loaded_log.seed, original_log.seed)
            self.assertEqual(loaded_log.total_epochs, original_log.total_epochs)
            self.assertEqual(loaded_log.expected_final_hash, original_log.expected_final_hash)
            self.assertEqual(len(loaded_log.events), len(original_log.events))
        finally:
            temp_path.unlink()


class TestCrossNodeReplay(unittest.TestCase):
    """Tests for cross-node replay functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.miners = [
            MinerState("m1", "pk1", 1000, "CPU1", 1980, 365),
            MinerState("m2", "pk2", 2000, "CPU2", 1985, 400),
            MinerState("m3", "pk3", 1500, "CPU3", 1990, 500),
        ]
        
    def test_single_node_replay(self):
        """Single node replay succeeds."""
        harness = CrossNodeReplayHarness(node_count=1)
        harness.initialize_nodes(seed=42, initial_miners=self.miners)
        
        replay_log = harness.record_simulation(num_epochs=2)
        result = harness.replay_all(replay_log)
        
        self.assertTrue(result.all_converged)
        self.assertEqual(result.nodes_tested, 1)
        
    def test_multi_node_convergence(self):
        """Multiple nodes converge to same state."""
        harness = CrossNodeReplayHarness(node_count=5)
        harness.initialize_nodes(seed=42, initial_miners=self.miners)
        
        replay_log = harness.record_simulation(num_epochs=3)
        result = harness.replay_all(replay_log)
        
        self.assertTrue(result.all_converged)
        self.assertEqual(result.nodes_tested, 5)
        
        # All nodes should have same final state hash
        state_hashes = set()
        for node_state in result.node_states.values():
            state_hashes.add(node_state["state_hash"])
        self.assertEqual(len(state_hashes), 1)
        
    def test_replay_determinism(self):
        """Replay is deterministic across multiple runs."""
        harness = CrossNodeReplayHarness(node_count=3)
        harness.initialize_nodes(seed=42, initial_miners=self.miners)
        
        replay_log = harness.record_simulation(num_epochs=2)
        
        # Run replay multiple times
        results = []
        for _ in range(3):
            # Reinitialize harness
            harness = CrossNodeReplayHarness(node_count=3)
            result = harness.replay_all(replay_log)
            results.append(result.replay_log_hash)
            
        # All runs should produce same hash
        self.assertEqual(len(set(results)), 1)
        
    def test_different_seeds_diverge(self):
        """Different seeds produce different state hashes."""
        seeds = [1, 42, 100, 999]
        final_hashes = []
        
        for seed in seeds:
            harness = CrossNodeReplayHarness(node_count=1)
            harness.initialize_nodes(seed=seed, initial_miners=self.miners)
            replay_log = harness.record_simulation(num_epochs=2)
            final_hashes.append(replay_log.expected_final_hash)
            
        # All hashes should be unique
        self.assertEqual(len(set(final_hashes)), len(seeds))


class TestDeterminismVerification(unittest.TestCase):
    """Tests for determinism verification."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.miners = [
            MinerState("m1", "pk1", 1000, "CPU1", 1980, 365),
            MinerState("m2", "pk2", 2000, "CPU2", 1985, 400),
        ]
        
    def test_verify_determinism_pass(self):
        """Verification passes for deterministic simulation."""
        harness = CrossNodeReplayHarness(node_count=3)
        harness.initialize_nodes(seed=42, initial_miners=self.miners)
        
        replay_log = harness.record_simulation(num_epochs=2)
        is_deterministic, message = harness.verify_determinism(replay_log)
        
        self.assertTrue(is_deterministic)
        self.assertIn("identical", message)
        
    def test_verify_with_scenario_file(self):
        """Verification works with scenario files."""
        scenario_path = Path(__file__).parent.parent / "fixtures" / "scenario_basic.json"
        
        if scenario_path.exists():
            with open(scenario_path) as f:
                scenario = json.load(f)
                
            # Convert scenario miners to MinerState
            miners = []
            for m in scenario['miners']:
                miners.append(MinerState(
                    miner_id=m.get('id', m.get('miner_id', 'unknown')),
                    public_key=m.get('public_key', 'pk_default'),
                    stake=m.get('stake', 1000),
                    cpu_model=m.get('cpu_model', 'CPU'),
                    release_year=m.get('release_year', 2000),
                    uptime_days=m.get('uptime_days', 365)
                ))
            
            harness = CrossNodeReplayHarness(node_count=3)
            harness.initialize_nodes(seed=scenario['seed'], initial_miners=miners)
            
            replay_log = harness.record_simulation(num_epochs=scenario['epochs'])
            is_deterministic, _ = harness.verify_determinism(replay_log)
            
            self.assertTrue(is_deterministic)


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling."""
    
    def test_empty_miner_list(self):
        """Simulation handles empty miner list gracefully."""
        harness = CrossNodeReplayHarness(node_count=1)
        harness.initialize_nodes(seed=42, initial_miners=[])
        
        replay_log = harness.record_simulation(num_epochs=1)
        
        # Should complete but with no blocks
        self.assertEqual(replay_log.total_epochs, 1)
        
    def test_single_miner(self):
        """Single miner scenario works correctly."""
        miners = [MinerState("solo", "pk_solo", 1000, "CPU", 1980, 365)]
        
        harness = CrossNodeReplayHarness(node_count=2)
        harness.initialize_nodes(seed=42, initial_miners=miners)
        
        replay_log = harness.record_simulation(num_epochs=2)
        result = harness.replay_all(replay_log)
        
        self.assertTrue(result.all_converged)
        
    def test_large_epoch_count(self):
        """Simulation handles many epochs."""
        miners = [
            MinerState("m1", "pk1", 1000, "CPU1", 1980, 365),
            MinerState("m2", "pk2", 2000, "CPU2", 1985, 400),
        ]
        
        harness = CrossNodeReplayHarness(node_count=2)
        harness.initialize_nodes(seed=42, initial_miners=miners)
        
        # Simulate 5 epochs (720 slots)
        replay_log = harness.record_simulation(num_epochs=5)
        
        self.assertEqual(replay_log.total_slots, 5 * EPOCH_SLOTS)
        self.assertGreater(replay_log.total_events, 0)


class TestReplayResult(unittest.TestCase):
    """Tests for replay result structure."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.miners = [
            MinerState("m1", "pk1", 1000, "CPU1", 1980, 365),
            MinerState("m2", "pk2", 2000, "CPU2", 1985, 400),
        ]
        
    def test_result_structure(self):
        """Replay result has expected structure."""
        harness = CrossNodeReplayHarness(node_count=2)
        harness.initialize_nodes(seed=42, initial_miners=self.miners)
        
        replay_log = harness.record_simulation(num_epochs=1)
        result = harness.replay_all(replay_log)
        
        # Check required fields
        self.assertTrue(len(result.replay_log_hash) > 0)
        self.assertGreater(result.nodes_tested, 0)
        self.assertIsInstance(result.all_converged, bool)
        self.assertIsInstance(result.node_states, dict)
        self.assertGreater(result.total_execution_time_ms, 0)
        self.assertGreater(result.verified_at, 0)
        
    def test_node_state_structure(self):
        """Node state has expected structure."""
        harness = CrossNodeReplayHarness(node_count=1)
        harness.initialize_nodes(seed=42, initial_miners=self.miners)
        
        replay_log = harness.record_simulation(num_epochs=1)
        result = harness.replay_all(replay_log)
        
        for node_id, state in result.node_states.items():
            self.assertIn("node_id", state)
            self.assertIn("status", state)
            self.assertIn("state_hash", state)
            self.assertIn("events_processed", state)
            
            # Status should be completed (check both enum and string forms)
            status = state["status"]
            if hasattr(status, 'value'):
                self.assertEqual(status.value, "completed")
            else:
                self.assertEqual(status, "completed")


if __name__ == "__main__":
    unittest.main()
