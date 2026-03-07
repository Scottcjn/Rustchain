#!/usr/bin/env python3
"""
RustChain Path Optimization Example

Demonstrates path optimization with live RustChain network data.
Shows how to find optimal routes for transactions and attestations.

Usage:
    python examples/path_optimization_example.py

Requirements:
    pip install rustchain-sdk
"""

import sys
from rustchain import RustChainClient, NetworkPathService, PathStrategy
from rustchain.path import PathOptimizer, NetworkNode


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)


def print_section(text):
    """Print section header"""
    print(f"\n{text}")
    print("-" * 40)


def example_basic_pathfinding():
    """Example 1: Basic pathfinding with mock network"""
    print_header("Example 1: Basic Pathfinding")
    
    # Create optimizer
    optimizer = PathOptimizer()
    
    # Build a simple network topology
    print_section("Building Network Topology")
    
    # Add validator
    optimizer.add_node(NetworkNode(
        node_id="validator_main",
        node_type="validator",
        latency_ms=50,
        reliability=0.99
    ))
    print("✓ Added main validator")
    
    # Add relay nodes
    optimizer.add_node(NetworkNode(
        node_id="relay_us",
        node_type="relay",
        latency_ms=30,
        reliability=0.97,
        geography="US-East"
    ))
    optimizer.add_node(NetworkNode(
        node_id="relay_eu",
        node_type="relay",
        latency_ms=40,
        reliability=0.96,
        geography="EU-West"
    ))
    print("✓ Added relay nodes (US, EU)")
    
    # Add miners with different hardware
    miners = [
        ("miner_g4_vintage", "PowerPC G4", 120),
        ("miner_g5_classic", "PowerPC G5", 100),
        ("miner_x86_modern", "x86_64", 80),
    ]
    
    for miner_id, arch, latency in miners:
        optimizer.add_node(NetworkNode(
            node_id=miner_id,
            node_type="miner",
            latency_ms=latency,
            reliability=0.95,
            architecture=arch
        ))
        
        # Connect miner to nearest relay
        optimizer.add_edge(
            miner_id,
            "relay_us" if "g4" in miner_id else "relay_eu",
            latency_ms=latency,
            fee=0.0001,
            reliability=0.95
        )
        print(f"✓ Added {arch} miner ({latency}ms base latency)")
    
    # Connect relays to validator
    optimizer.add_edge("relay_us", "validator_main", latency_ms=25, fee=0.0002)
    optimizer.add_edge("relay_eu", "validator_main", latency_ms=35, fee=0.0002)
    print("✓ Connected relays to validator")
    
    # Find paths
    print_section("Finding Optimal Paths")
    
    for strategy in PathStrategy:
        path = optimizer.find_path("miner_g4_vintage", "validator_main", strategy)
        
        if path:
            print(f"\n{strategy.value.upper()} Strategy:")
            print(f"  Path: {' -> '.join(path.nodes)}")
            print(f"  Total Latency: {path.total_latency_ms:.1f}ms")
            print(f"  Total Fee: {path.total_fee:.6f} RTC")
            print(f"  Success Probability: {path.success_probability:.2%}")
            print(f"  Hop Count: {path.hop_count}")
    
    # Network statistics
    print_section("Network Statistics")
    stats = optimizer.get_network_stats()
    print(f"Total Nodes: {stats['total_nodes']}")
    print(f"Total Edges: {stats['total_edges']}")
    print(f"Healthy Nodes: {stats['healthy_nodes']}")
    print(f"Node Types: {stats['node_types']}")
    print(f"Avg Latency: {stats['avg_latency_ms']:.1f}ms")
    print(f"Avg Reliability: {stats['avg_reliability']:.2%}")


def example_live_network():
    """Example 2: Pathfinding with live RustChain network"""
    print_header("Example 2: Live Network Integration")
    
    try:
        # Initialize client and service
        print_section("Connecting to Live Network")
        client = RustChainClient("https://rustchain.org", verify_ssl=False, timeout=10)
        service = NetworkPathService(client)
        print("✓ Connected to RustChain node")
        
        # Refresh network data
        print_section("Refreshing Network Data")
        result = service.refresh_network_data()
        
        if result["success"]:
            print(f"✓ Refreshed {result['nodes_added']} nodes")
            print(f"✓ Current Epoch: {result['epoch']}")
            print(f"✓ Timestamp: {result['timestamp']}")
        else:
            print(f"✗ Refresh failed: {result.get('error', 'Unknown error')}")
            return
        
        # Network statistics
        print_section("Live Network Statistics")
        stats = service.get_network_stats()
        print(f"Total Nodes: {stats['total_nodes']}")
        print(f"Total Edges: {stats['total_edges']}")
        print(f"Healthy Nodes: {stats['healthy_nodes']}")
        print(f"Data Age: {stats['refresh_age_seconds']}s")
        
        if stats['avg_latency_ms'] > 0:
            print(f"Avg Latency: {stats['avg_latency_ms']:.1f}ms")
            print(f"Avg Reliability: {stats['avg_reliability']:.2%}")
        
        # Find paths if miners exist
        miner_nodes = [
            node_id for node_id in service.optimizer.nodes.keys()
            if node_id.startswith("miner_")
        ]
        
        if miner_nodes:
            print_section(f"Path Optimization ({len(miner_nodes)} miners)")
            
            # Test with first miner
            test_miner = miner_nodes[0]
            print(f"Testing with miner: {test_miner}\n")
            
            for strategy in PathStrategy:
                paths = service.find_optimal_path(
                    test_miner,
                    "validator_network",
                    strategy
                )
                
                if paths:
                    path = paths[0]
                    print(f"{strategy.value.upper()}:")
                    print(f"  Path: {' -> '.join(path.nodes)}")
                    print(f"  Latency: {path.total_latency_ms:.1f}ms")
                    print(f"  Fee: {path.total_fee:.6f} RTC")
                    print(f"  Reliability: {path.success_probability:.2%}")
                    print(f"  Hops: {path.hop_count}")
                    print()
        else:
            print("ℹ No miners currently enrolled in network")
        
        # Data freshness
        print_section("Data Freshness")
        print(f"Is Fresh: {service.is_fresh()}")
        print(f"Last Refresh: {stats['last_refresh']}")
        print(f"Refresh Interval: {service._refresh_interval}s")
        
        client.close()
        print("\n✓ Connection closed")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        print("\nNote: Live network tests require internet connectivity")
        print("and the RustChain node to be online.")


def example_strategy_comparison():
    """Example 3: Comparing path strategies"""
    print_header("Example 3: Strategy Comparison")
    
    optimizer = PathOptimizer()
    
    # Create a more complex network
    print_section("Building Test Network")
    
    # Add nodes
    optimizer.add_node(NetworkNode("source", "miner", latency_ms=100))
    optimizer.add_node(NetworkNode("relay1", "relay", latency_ms=50))
    optimizer.add_node(NetworkNode("relay2", "relay", latency_ms=60))
    optimizer.add_node(NetworkNode("relay3", "relay", latency_ms=40))
    optimizer.add_node(NetworkNode("destination", "validator", latency_ms=30))
    
    # Add multiple paths with different characteristics
    # Path 1: Fast but expensive
    optimizer.add_edge("source", "relay1", latency_ms=20, fee=0.01, reliability=0.95)
    optimizer.add_edge("relay1", "destination", latency_ms=15, fee=0.01, reliability=0.95)
    
    # Path 2: Slow but cheap
    optimizer.add_edge("source", "relay2", latency_ms=100, fee=0.001, reliability=0.90)
    optimizer.add_edge("relay2", "destination", latency_ms=80, fee=0.001, reliability=0.90)
    
    # Path 3: Balanced
    optimizer.add_edge("source", "relay3", latency_ms=50, fee=0.005, reliability=0.98)
    optimizer.add_edge("relay3", "destination", latency_ms=40, fee=0.005, reliability=0.98)
    
    print("✓ Created network with 3 alternative paths")
    print("  Path 1: Fast (35ms) but expensive (0.02 RTC)")
    print("  Path 2: Slow (180ms) but cheap (0.002 RTC)")
    print("  Path 3: Balanced (90ms, 0.01 RTC)")
    
    # Compare strategies
    print_section("Strategy Comparison Results")
    
    results = []
    for strategy in PathStrategy:
        path = optimizer.find_path("source", "destination", strategy)
        if path:
            results.append((strategy, path))
    
    print(f"\n{'Strategy':<15} {'Latency':<12} {'Fee':<12} {'Reliability':<12} {'Hops'}")
    print("-" * 60)
    
    for strategy, path in results:
        print(f"{strategy.value:<15} {path.total_latency_ms:>8.1f}ms  "
              f"{path.total_fee:>10.6f}  {path.success_probability:>10.2%}  {path.hop_count:>4}")


def main():
    """Run all examples"""
    print("\n" + "█" * 60)
    print(" RustChain Path Optimization Examples")
    print(" Issue #618 Rework - Live Network Integration")
    print("█" * 60)
    
    # Example 1: Basic pathfinding (no network required)
    example_basic_pathfinding()
    
    # Example 2: Live network (requires internet)
    example_live_network()
    
    # Example 3: Strategy comparison
    example_strategy_comparison()
    
    print_header("Examples Complete")
    print("✓ All examples executed successfully")
    print("\nFor more information, see:")
    print("  - docs/PATH_OPTIMIZATION_GUIDE.md")
    print("  - sdk/README.md")
    print("  - docs/api-reference.md")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
