"""
Unit tests for RustChain Path Optimization Module

Tests pathfinding algorithms, network topology, and optimization strategies
without requiring network access.
"""

import pytest
from rustchain.path import (
    PathOptimizer,
    NetworkPathService,
    PathStrategy,
    NetworkNode,
    PathSegment,
    TransactionPath,
)


class TestNetworkNode:
    """Test NetworkNode dataclass"""
    
    def test_create_node(self):
        """Test creating a basic node"""
        node = NetworkNode(
            node_id="test_node",
            node_type="miner"
        )
        assert node.node_id == "test_node"
        assert node.node_type == "miner"
        assert node.latency_ms == 0.0
        assert node.reliability == 1.0
        assert node.capacity == 1.0
        
    def test_node_health(self):
        """Test node health checking"""
        import time
        
        # Fresh node should be healthy
        node = NetworkNode(
            node_id="test_node",
            node_type="validator",
            last_seen=int(time.time())
        )
        assert node.is_healthy() is True
        
        # Old node should be unhealthy
        old_node = NetworkNode(
            node_id="old_node",
            node_type="miner",
            last_seen=int(time.time()) - 600  # 10 minutes ago
        )
        assert old_node.is_healthy(max_age_seconds=300) is False
        
    def test_node_with_geography(self):
        """Test node with geography and architecture"""
        node = NetworkNode(
            node_id="g4_miner",
            node_type="miner",
            geography="US-West",
            architecture="PowerPC G4"
        )
        assert node.geography == "US-West"
        assert node.architecture == "PowerPC G4"


class TestPathSegment:
    """Test PathSegment dataclass"""
    
    def test_create_segment(self):
        """Test creating a path segment"""
        segment = PathSegment(
            from_node="node_a",
            to_node="node_b",
            latency_ms=50.0,
            fee=0.001,
            reliability=0.95
        )
        assert segment.from_node == "node_a"
        assert segment.to_node == "node_b"
        assert segment.latency_ms == 50.0
        assert segment.fee == 0.001
        assert segment.reliability == 0.95
        
    def test_cost_score(self):
        """Test cost score calculation"""
        segment = PathSegment(
            from_node="a",
            to_node="b",
            latency_ms=100.0,
            fee=0.01,
            reliability=0.9
        )
        # cost_score = fee * 100 + latency_ms = 0.01 * 100 + 100 = 101
        assert segment.cost_score == 101.0


class TestTransactionPath:
    """Test TransactionPath dataclass"""
    
    def test_create_path(self):
        """Test creating a transaction path"""
        segments = [
            PathSegment("a", "b", 50.0, 0.001, 0.95),
            PathSegment("b", "c", 30.0, 0.001, 0.98),
        ]
        path = TransactionPath(
            path_id="test_path",
            segments=segments,
            total_latency_ms=80.0,
            total_fee=0.002,
            success_probability=0.931,  # 0.95 * 0.98
            strategy=PathStrategy.FASTEST,
            nodes=["a", "b", "c"]
        )
        assert path.path_id == "test_path"
        assert path.hop_count == 2
        assert len(path.segments) == 2
        
    def test_path_to_dict(self):
        """Test converting path to dictionary"""
        segments = [
            PathSegment("a", "b", 50.0, 0.001, 0.95),
        ]
        path = TransactionPath(
            path_id="test",
            segments=segments,
            total_latency_ms=50.0,
            total_fee=0.001,
            success_probability=0.95,
            strategy=PathStrategy.BALANCED,
            nodes=["a", "b"]
        )
        path_dict = path.to_dict()
        
        assert path_dict["path_id"] == "test"
        assert path_dict["hop_count"] == 1
        assert path_dict["nodes"] == ["a", "b"]
        assert len(path_dict["segments"]) == 1
        assert path_dict["strategy"] == "balanced"


class TestPathOptimizer:
    """Test PathOptimizer class"""
    
    @pytest.fixture
    def optimizer(self):
        """Create optimizer with test network"""
        opt = PathOptimizer()
        
        # Create a simple network: A -- B -- C
        opt.add_node(NetworkNode("A", "miner"))
        opt.add_node(NetworkNode("B", "relay"))
        opt.add_node(NetworkNode("C", "validator"))
        
        # Add edges
        opt.add_edge("A", "B", latency_ms=50.0, fee=0.001, reliability=0.95)
        opt.add_edge("B", "C", latency_ms=30.0, fee=0.001, reliability=0.98)
        
        return opt
    
    def test_add_node(self, optimizer):
        """Test adding nodes"""
        optimizer.add_node(NetworkNode("D", "miner"))
        assert "D" in optimizer.nodes
        
    def test_remove_node(self, optimizer):
        """Test removing nodes"""
        assert optimizer.remove_node("B") is True
        assert "B" not in optimizer.nodes
        # Edge should also be removed
        assert ("A", "B") not in optimizer.edges
        
    def test_remove_nonexistent_node(self, optimizer):
        """Test removing a node that doesn't exist"""
        assert optimizer.remove_node("Z") is False
        
    def test_add_edge_invalid_node(self, optimizer):
        """Test adding edge with invalid node"""
        with pytest.raises(ValueError):
            optimizer.add_edge("A", "Z", latency_ms=50.0)
            
    def test_find_path_simple(self, optimizer):
        """Test finding a simple path"""
        path = optimizer.find_path("A", "C", PathStrategy.FASTEST)
        
        assert path is not None
        assert path.nodes == ["A", "B", "C"]
        assert path.hop_count == 2
        assert path.total_latency_ms == 80.0  # 50 + 30
        assert abs(path.total_fee - 0.002) < 0.0001
        assert path.strategy == PathStrategy.FASTEST
        
    def test_find_path_same_node(self, optimizer):
        """Test finding path from node to itself"""
        path = optimizer.find_path("A", "A", PathStrategy.FASTEST)
        
        assert path is not None
        assert path.nodes == ["A"]
        assert path.hop_count == 0
        assert path.total_latency_ms == 0.0
        assert path.total_fee == 0.0
        
    def test_find_path_no_route(self):
        """Test finding path when no route exists"""
        opt = PathOptimizer()
        opt.add_node(NetworkNode("A", "miner"))
        opt.add_node(NetworkNode("B", "validator"))
        # No edge between A and B
        
        path = opt.find_path("A", "B")
        assert path is None
        
    def test_find_path_invalid_nodes(self, optimizer):
        """Test finding path with invalid nodes"""
        path = optimizer.find_path("A", "Z")
        assert path is None
        
        path = optimizer.find_path("Z", "A")
        assert path is None
        
    def test_find_all_paths(self, optimizer):
        """Test finding multiple paths with different strategies"""
        paths = optimizer.find_all_paths("A", "C", max_paths=3)
        
        assert len(paths) > 0
        assert all(isinstance(p, TransactionPath) for p in paths)
        # All paths should reach from A to C
        assert all(p.nodes[0] == "A" and p.nodes[-1] == "C" for p in paths)
        
    def test_strategy_fastest(self):
        """Test FASTEST strategy prioritizes latency"""
        opt = PathOptimizer()
        opt.add_node(NetworkNode("A", "miner"))
        opt.add_node(NetworkNode("B", "relay"))
        opt.add_node(NetworkNode("C", "validator"))
        
        # Two paths: A-B-C (fast) and A-C (slow direct)
        opt.add_edge("A", "B", latency_ms=10.0, fee=0.01)
        opt.add_edge("B", "C", latency_ms=10.0, fee=0.01)
        opt.add_edge("A", "C", latency_ms=100.0, fee=0.001)
        
        path = opt.find_path("A", "C", PathStrategy.FASTEST)
        # Should prefer A-B-C (20ms) over A-C (100ms)
        assert path.total_latency_ms == 20.0
        
    def test_strategy_cheapest(self):
        """Test CHEAPEST strategy prioritizes low fees"""
        opt = PathOptimizer()
        opt.add_node(NetworkNode("A", "miner"))
        opt.add_node(NetworkNode("B", "relay"))
        opt.add_node(NetworkNode("C", "validator"))
        
        # Two paths: A-B-C (expensive) and A-C (cheap direct)
        opt.add_edge("A", "B", latency_ms=10.0, fee=0.1)
        opt.add_edge("B", "C", latency_ms=10.0, fee=0.1)
        opt.add_edge("A", "C", latency_ms=100.0, fee=0.001)
        
        path = opt.find_path("A", "C", PathStrategy.CHEAPEST)
        # Should prefer A-C (0.001 fee) over A-B-C (0.2 fee)
        assert abs(path.total_fee - 0.001) < 0.0001
        
    def test_strategy_most_reliable(self):
        """Test MOST_RELIBLE strategy prioritizes reliability"""
        opt = PathOptimizer()
        opt.add_node(NetworkNode("A", "miner"))
        opt.add_node(NetworkNode("B", "relay"))
        opt.add_node(NetworkNode("C", "validator"))
        
        # Two paths: A-B-C (unreliable) and A-C (reliable direct)
        opt.add_edge("A", "B", latency_ms=10.0, reliability=0.5)
        opt.add_edge("B", "C", latency_ms=10.0, reliability=0.5)
        opt.add_edge("A", "C", latency_ms=100.0, reliability=0.99)
        
        path = opt.find_path("A", "C", PathStrategy.MOST_RELIBLE)
        # Should prefer A-C (0.99 reliability) over A-B-C (0.25 reliability)
        assert path.success_probability > 0.9
        
    def test_get_network_stats(self, optimizer):
        """Test getting network statistics"""
        stats = optimizer.get_network_stats()
        
        assert stats["total_nodes"] == 3
        assert stats["total_edges"] == 2  # A-B and B-C
        assert "healthy_nodes" in stats
        assert "node_types" in stats
        assert "avg_latency_ms" in stats
        assert "avg_reliability" in stats
        
    def test_get_network_stats_empty(self):
        """Test stats with empty network"""
        opt = PathOptimizer()
        stats = opt.get_network_stats()
        
        assert stats["total_nodes"] == 0
        assert stats["total_edges"] == 0
        assert stats["avg_latency_ms"] == 0
        
    def test_clear(self, optimizer):
        """Test clearing the optimizer"""
        optimizer.clear()
        assert len(optimizer.nodes) == 0
        assert len(optimizer.edges) == 0


class TestNetworkPathService:
    """Test NetworkPathService class"""
    
    @pytest.fixture
    def mock_client(self):
        """Create mock RustChain client"""
        class MockClient:
            def epoch(self):
                return {
                    "epoch": 100,
                    "slot": 14400,
                    "blocks_per_epoch": 144,
                    "enrolled_miners": 3
                }
                
            def miners(self):
                return [
                    {
                        "miner": "abc123def456",
                        "device_arch": "G4",
                        "hardware_type": "PowerPC G4",
                        "antiquity_multiplier": 2.5
                    },
                    {
                        "miner": "xyz789ghi012",
                        "device_arch": "G5",
                        "hardware_type": "PowerPC G5",
                        "antiquity_multiplier": 2.0
                    },
                ]
                
        return MockClient()
    
    def test_create_service(self, mock_client):
        """Test creating the service"""
        service = NetworkPathService(mock_client)
        assert service.client == mock_client
        assert service.optimizer is not None
        
    def test_refresh_network_data(self, mock_client):
        """Test refreshing network data"""
        service = NetworkPathService(mock_client)
        result = service.refresh_network_data()
        
        assert result["success"] is True
        assert result["nodes_added"] > 0
        assert result["epoch"] == 100
        
    def test_refresh_with_error(self):
        """Test refresh when client fails"""
        class FailingClient:
            def epoch(self):
                raise Exception("Connection failed")
                
            def miners(self):
                raise Exception("Connection failed")
        
        service = NetworkPathService(FailingClient())
        result = service.refresh_network_data()
        
        assert result["success"] is False
        assert "error" in result
        
    def test_find_optimal_path(self, mock_client):
        """Test finding optimal path"""
        service = NetworkPathService(mock_client)
        service.refresh_network_data()
        
        # Find path from miner to validator
        paths = service.find_optimal_path(
            "miner_abc123def456",
            "validator_network"
        )
        
        assert len(paths) > 0
        path = paths[0]
        assert "miner_abc123def456" in path.nodes
        assert "validator_network" in path.nodes
        
    def test_find_optimal_path_auto_refresh(self, mock_client):
        """Test that path finding auto-refreshes stale data"""
        service = NetworkPathService(mock_client)
        service._last_refresh = 0  # Force refresh
        service._refresh_interval = 0
        
        paths = service.find_optimal_path("miner_abc", "validator")
        # Should have auto-refreshed
        assert service._last_refresh > 0
        
    def test_get_network_stats(self, mock_client):
        """Test getting network stats"""
        service = NetworkPathService(mock_client)
        service.refresh_network_data()
        
        stats = service.get_network_stats()
        
        assert "total_nodes" in stats
        assert "last_refresh" in stats
        assert "refresh_age_seconds" in stats
        
    def test_is_fresh(self, mock_client):
        """Test data freshness check"""
        service = NetworkPathService(mock_client)
        
        # Initially not fresh
        assert service.is_fresh() is False
        
        # After refresh, should be fresh
        service.refresh_network_data()
        assert service.is_fresh() is True
        
    def test_latency_estimation(self, mock_client):
        """Test latency estimation by hardware type"""
        service = NetworkPathService(mock_client)
        
        # Test different hardware types
        g3_miner = {"device_arch": "G3", "hardware_type": "PowerPC G3"}
        g4_miner = {"device_arch": "G4", "hardware_type": "PowerPC G4"}
        g5_miner = {"device_arch": "G5", "hardware_type": "PowerPC G5"}
        x86_miner = {"device_arch": "x86_64", "hardware_type": "Intel"}
        arm_miner = {"device_arch": "ARM", "hardware_type": "ARM"}
        unknown_miner = {"device_arch": "UNKNOWN", "hardware_type": "Unknown"}
        
        assert service._estimate_latency(g3_miner) == 150.0
        assert service._estimate_latency(g4_miner) == 120.0
        assert service._estimate_latency(g5_miner) == 100.0
        assert service._estimate_latency(x86_miner) == 80.0
        assert service._estimate_latency(arm_miner) == 90.0
        assert service._estimate_latency(unknown_miner) == 100.0


class TestPathIntegration:
    """Integration tests for path optimization"""
    
    def test_realistic_network(self):
        """Test with a more realistic network topology"""
        optimizer = PathOptimizer()
        
        # Create a star topology: multiple miners -> relay -> validator
        optimizer.add_node(NetworkNode("validator", "validator", reliability=0.99))
        optimizer.add_node(NetworkNode("relay1", "relay", reliability=0.97))
        optimizer.add_node(NetworkNode("relay2", "relay", reliability=0.96))
        
        for i in range(5):
            optimizer.add_node(NetworkNode(f"miner_{i}", "miner", reliability=0.95))
            # Connect miners to relays
            optimizer.add_edge(f"miner_{i}", "relay1", latency_ms=50 + i*10, fee=0.001)
            optimizer.add_edge(f"miner_{i}", "relay2", latency_ms=60 + i*10, fee=0.0008)
        
        # Connect relays to validator
        optimizer.add_edge("relay1", "validator", latency_ms=20, fee=0.002, reliability=0.98)
        optimizer.add_edge("relay2", "validator", latency_ms=25, fee=0.0015, reliability=0.97)
        
        # Find path from miner to validator
        path = optimizer.find_path("miner_0", "validator", PathStrategy.BALANCED)
        
        assert path is not None
        assert path.nodes[0] == "miner_0"
        assert path.nodes[-1] == "validator"
        assert path.success_probability > 0.9
        
    def test_path_probability_calculation(self):
        """Test that path success probability is calculated correctly"""
        optimizer = PathOptimizer()
        
        optimizer.add_node(NetworkNode("A", "miner"))
        optimizer.add_node(NetworkNode("B", "relay"))
        optimizer.add_node(NetworkNode("C", "validator"))
        
        # Edges with known reliability
        optimizer.add_edge("A", "B", reliability=0.9)
        optimizer.add_edge("B", "C", reliability=0.8)
        
        path = optimizer.find_path("A", "C")
        
        # Success probability should be product of edge reliabilities
        expected_prob = 0.9 * 0.8
        assert abs(path.success_probability - expected_prob) < 0.001
