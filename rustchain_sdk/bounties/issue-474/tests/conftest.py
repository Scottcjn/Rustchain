#!/usr/bin/env python3
"""
Pytest fixtures for Epoch Determinism Simulator tests
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from epoch_determinism_simulator import (
    DeterministicRNG,
    EpochDeterminismSimulator,
    MinerState,
    BlockHeader,
    EpochState,
    EPOCH_SLOTS
)
from cross_node_replay import CrossNodeReplayHarness


@pytest.fixture
def default_rng():
    """Provide a default deterministic RNG."""
    return DeterministicRNG(seed=42)


@pytest.fixture
def rng_factory():
    """Factory for creating RNGs with custom seeds."""
    def _create(seed=42):
        return DeterministicRNG(seed=seed)
    return _create


@pytest.fixture
def sample_miners():
    """Provide a list of sample miners."""
    return [
        MinerState("miner-1", "pk1", 1000, "Intel 8086", 1978, 3650),
        MinerState("miner-2", "pk2", 2000, "Intel 386", 1985, 2500),
        MinerState("miner-3", "pk3", 1500, "Intel Pentium", 1993, 1800),
    ]


@pytest.fixture
def vintage_miner():
    """Provide a vintage miner with high antiquity score."""
    return MinerState(
        miner_id="vintage",
        public_key="pk_vintage" + "0" * 28,
        stake=5000,
        cpu_model="Intel 8086",
        release_year=1978,
        uptime_days=10000
    )


@pytest.fixture
def modern_miner():
    """Provide a modern miner with low antiquity score."""
    return MinerState(
        miner_id="modern",
        public_key="pk_modern" + "0" * 28,
        stake=1000,
        cpu_model="Intel Core i9",
        release_year=2020,
        uptime_days=100
    )


@pytest.fixture
def initialized_simulator(sample_miners):
    """Provide a simulator initialized with sample miners."""
    sim = EpochDeterminismSimulator(seed=42)
    sim.initialize_chain(sample_miners)
    return sim


@pytest.fixture
def simulator_factory():
    """Factory for creating simulators with custom configuration."""
    def _create(seed=42, miners=None, node_id="test-node"):
        sim = EpochDeterminismSimulator(seed=seed, node_id=node_id)
        if miners:
            sim.initialize_chain(miners)
        return sim
    return _create


@pytest.fixture
def sample_block():
    """Provide a sample block header."""
    return BlockHeader(
        slot=1,
        epoch=0,
        producer="miner-1",
        parent_hash="parent" + "0" * 10,
        timestamp=1000,
        transactions_hash="tx" + "0" * 14,
        state_hash="state" + "0" * 11,
        signature="sig" + "0" * 13
    )


@pytest.fixture
def epoch_state():
    """Provide a sample epoch state."""
    return EpochState(
        epoch=0,
        start_slot=0,
        end_slot=EPOCH_SLOTS - 1
    )


@pytest.fixture
def replay_harness():
    """Provide a configured replay harness."""
    return CrossNodeReplayHarness(node_count=3)


@pytest.fixture
def replay_harness_factory():
    """Factory for creating replay harnesses."""
    def _create(node_count=3, seed=42, miners=None):
        harness = CrossNodeReplayHarness(node_count=node_count)
        if miners:
            harness.initialize_nodes(seed=seed, initial_miners=miners)
        return harness
    return _create


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def temp_output_path(tmp_path):
    """Provide a temporary output file path."""
    return tmp_path / "output.json"
