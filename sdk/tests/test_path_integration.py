"""
Integration tests for RustChain Path Optimization (against live node)

These tests require network access to https://rustchain.org
Tests verify that path optimization works with real network data.
"""

import pytest
from rustchain import RustChainClient, NetworkPathService, PathStrategy


# Test against live RustChain node
LIVE_NODE_URL = "https://rustchain.org"


@pytest.mark.integration
class TestLivePathOptimization:
    """Test path optimization against live RustChain network"""
    
    @pytest.fixture
    def client(self):
        """Create client for live testing"""
        client = RustChainClient(LIVE_NODE_URL, verify_ssl=False, timeout=10)
        yield client
        client.close()
    
    @pytest.fixture
    def path_service(self, client):
        """Create path service with live client"""
        service = NetworkPathService(client)
        yield service
    
    def test_refresh_with_live_data(self, path_service):
        """Test refreshing network data from live node"""
        result = path_service.refresh_network_data()
        
        assert result["success"] is True
        assert result["nodes_added"] >= 1  # At least validator node
        assert "epoch" in result
        assert result["epoch"] > 0
        
    def test_network_stats_from_live(self, path_service):
        """Test getting network stats from live data"""
        # Refresh first
        path_service.refresh_network_data()
        
        stats = path_service.get_network_stats()
        
        assert "total_nodes" in stats
        assert "total_edges" in stats
        assert "healthy_nodes" in stats
        
        # Should have at least the validator node
        assert stats["total_nodes"] >= 1
        
        # Stats should include timing info
        assert "last_refresh" in stats
        assert "refresh_age_seconds" in stats
        assert stats["refresh_age_seconds"] >= 0
        
    def test_find_path_live_network(self, path_service):
        """Test finding paths in live network"""
        # Refresh network data
        path_service.refresh_network_data()
        
        # Get list of miners to test with
        stats = path_service.get_network_stats()
        
        # If we have miners, test path finding
        if stats["total_nodes"] > 1:
            # Find path from any miner to validator
            miner_nodes = [
                node_id for node_id in path_service.optimizer.nodes.keys()
                if node_id.startswith("miner_")
            ]
            
            if miner_nodes:
                paths = path_service.find_optimal_path(
                    miner_nodes[0],
                    "validator_network",
                    PathStrategy.FASTEST
                )
                
                assert len(paths) > 0
                path = paths[0]
                
                # Path should connect miner to validator
                assert path.nodes[0] == miner_nodes[0]
                assert "validator" in path.nodes[-1]
                
                # Path should have reasonable metrics
                assert path.total_latency_ms > 0
                assert path.total_fee >= 0
                assert 0 <= path.success_probability <= 1
    
    def test_all_strategies_live(self, path_service):
        """Test all path strategies with live data"""
        path_service.refresh_network_data()
        
        miner_nodes = [
            node_id for node_id in path_service.optimizer.nodes.keys()
            if node_id.startswith("miner_")
        ]
        
        if not miner_nodes:
            pytest.skip("No miners available in live network")
        
        # Test each strategy
        for strategy in PathStrategy:
            paths = path_service.find_optimal_path(
                miner_nodes[0],
                "validator_network",
                strategy
            )
            
            if paths:
                path = paths[0]
                assert path.strategy == strategy
                
                # Verify path is valid
                assert len(path.nodes) >= 2
                assert path.hop_count >= 1
    
    def test_data_freshness(self, path_service):
        """Test that data freshness is tracked correctly"""
        # Initially stale
        assert path_service.is_fresh() is False
        
        # Refresh
        path_service.refresh_network_data()
        
        # Should be fresh now
        assert path_service.is_fresh() is True
        
        # Manually age the data
        import time
        path_service._last_refresh = int(time.time()) - 120
        path_service._refresh_interval = 60
        
        # Should be stale again
        assert path_service.is_fresh() is False
    
    def test_auto_refresh_on_stale_data(self, path_service):
        """Test that path finding triggers refresh when data is stale"""
        # Set last refresh to force refresh
        path_service._last_refresh = 0
        path_service._refresh_interval = 0
        
        # This should trigger auto-refresh
        paths = path_service.find_optimal_path(
            "miner_test",
            "validator_network"
        )
        
        # Should have refreshed (even if no path found)
        assert path_service._last_refresh > 0


@pytest.mark.integration
class TestLiveNetworkTopology:
    """Test network topology discovery from live data"""
    
    @pytest.fixture
    def client(self):
        """Create client for live testing"""
        client = RustChainClient(LIVE_NODE_URL, verify_ssl=False, timeout=10)
        yield client
        client.close()
    
    def test_miner_architecture_distribution(self, client):
        """Test analyzing miner architecture distribution"""
        service = NetworkPathService(client)
        result = service.refresh_network_data()
        
        if not result["success"]:
            pytest.skip("Failed to refresh network data")
        
        # Count architectures
        arch_counts = {}
        for node_id, node in service.optimizer.nodes.items():
            if node.node_type == "miner" and node.architecture:
                arch = node.architecture
                arch_counts[arch] = arch_counts.get(arch, 0) + 1
        
        # Should have some miners
        if arch_counts:
            print(f"\nMiner Architecture Distribution:")
            for arch, count in sorted(arch_counts.items(), key=lambda x: -x[1]):
                print(f"  {arch}: {count} miners")
    
    def test_network_latency_estimation(self, client):
        """Test latency estimation for live network"""
        service = NetworkPathService(client)
        service.refresh_network_data()
        
        # Get latency stats
        stats = service.get_network_stats()
        
        if stats["total_edges"] > 0:
            print(f"\nNetwork Latency Stats:")
            print(f"  Average Latency: {stats['avg_latency_ms']}ms")
            print(f"  Average Reliability: {stats['avg_reliability']:.2%}")
            print(f"  Total Edges: {stats['total_edges']}")


@pytest.mark.integration
class TestPathOptimizationScenarios:
    """Test various path optimization scenarios with live data"""
    
    @pytest.fixture
    def service(self):
        """Create service with live client"""
        client = RustChainClient(LIVE_NODE_URL, verify_ssl=False, timeout=10)
        service = NetworkPathService(client)
        service.refresh_network_data()
        yield service
        client.close()
    
    def test_fastest_path_characteristics(self, service):
        """Test characteristics of fastest paths"""
        miner_nodes = [
            node_id for node_id in service.optimizer.nodes.keys()
            if node_id.startswith("miner_")
        ]
        
        if not miner_nodes:
            pytest.skip("No miners available")
        
        paths = service.find_optimal_path(
            miner_nodes[0],
            "validator_network",
            PathStrategy.FASTEST
        )
        
        if paths:
            path = paths[0]
            print(f"\nFastest Path:")
            print(f"  Latency: {path.total_latency_ms}ms")
            print(f"  Hops: {path.hop_count}")
            print(f"  Nodes: {' -> '.join(path.nodes)}")
    
    def test_cheapest_path_characteristics(self, service):
        """Test characteristics of cheapest paths"""
        miner_nodes = [
            node_id for node_id in service.optimizer.nodes.keys()
            if node_id.startswith("miner_")
        ]
        
        if not miner_nodes:
            pytest.skip("No miners available")
        
        paths = service.find_optimal_path(
            miner_nodes[0],
            "validator_network",
            PathStrategy.CHEAPEST
        )
        
        if paths:
            path = paths[0]
            print(f"\nCheapest Path:")
            print(f"  Fee: {path.total_fee:.6f} RTC")
            print(f"  Hops: {path.hop_count}")
            print(f"  Success Probability: {path.success_probability:.2%}")
    
    def test_reliable_path_characteristics(self, service):
        """Test characteristics of most reliable paths"""
        miner_nodes = [
            node_id for node_id in service.optimizer.nodes.keys()
            if node_id.startswith("miner_")
        ]
        
        if not miner_nodes:
            pytest.skip("No miners available")
        
        paths = service.find_optimal_path(
            miner_nodes[0],
            "validator_network",
            PathStrategy.MOST_RELIBLE
        )
        
        if paths:
            path = paths[0]
            print(f"\nMost Reliable Path:")
            print(f"  Success Probability: {path.success_probability:.2%}")
            print(f"  Latency: {path.total_latency_ms}ms")
            print(f"  Hops: {path.hop_count}")
