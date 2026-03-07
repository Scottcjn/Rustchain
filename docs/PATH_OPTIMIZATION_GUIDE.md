# RustChain Path Optimization Guide

**Issue #618 Rework**: Architecture-aligned path optimization with live network integration.

This guide covers the path optimization module for routing transactions through the RustChain network optimally.

## Overview

The path optimization module provides intelligent routing for transactions and attestations through the RustChain network. It analyzes:

- **Network topology** - Real miner and validator distribution
- **Hardware characteristics** - Vintage vs modern hardware latency profiles  
- **Path strategies** - Fastest, cheapest, most reliable, or balanced
- **Live network data** - Fetched from actual RustChain endpoints

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│  (Miner CLI, Wallet, Attestation Service)                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              NetworkPathService (Live Integration)          │
│  • Fetches real miner data from /api/miners                │
│  • Gets epoch info from /epoch                              │
│  • Builds topology graph from live network                  │
│  • Auto-refreshes every 60 seconds                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                PathOptimizer (Algorithm Layer)              │
│  • Dijkstra's algorithm for shortest path                   │
│  • Multi-strategy optimization                               │
│  • Graph management (nodes, edges)                          │
│  • Path cost calculation                                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              RustChainClient (API Layer)                    │
│  • HTTP client for node communication                        │
│  • Endpoint: https://rustchain.org                          │
│  • Endpoints: /epoch, /api/miners, /health                  │
└─────────────────────────────────────────────────────────────┘
```

## Installation

```bash
# Install the SDK
cd sdk
pip install -e .

# Or install from PyPI (when published)
pip install rustchain-sdk
```

## Quick Start

### Basic Path Finding

```python
from rustchain import RustChainClient, NetworkPathService, PathStrategy

# Initialize client and path service
client = RustChainClient("https://rustchain.org", verify_ssl=False)
service = NetworkPathService(client)

# Refresh network data from live endpoints
result = service.refresh_network_data()
print(f"Refreshed {result['nodes_added']} nodes from epoch {result['epoch']}")

# Find optimal path from miner to validator
paths = service.find_optimal_path(
    "miner_abc123",
    "validator_network",
    PathStrategy.BALANCED
)

if paths:
    path = paths[0]
    print(f"Path: {' -> '.join(path.nodes)}")
    print(f"Latency: {path.total_latency_ms}ms")
    print(f"Fee: {path.total_fee:.6f} RTC")
    print(f"Success Probability: {path.success_probability:.2%}")

client.close()
```

### Using Different Strategies

```python
from rustchain import PathStrategy

# Fastest path (minimize latency)
fastest = service.find_optimal_path(
    "miner_g4_001",
    "validator_network",
    PathStrategy.FASTEST
)

# Cheapest path (minimize fees)
cheapest = service.find_optimal_path(
    "miner_g4_001",
    "validator_network",
    PathStrategy.CHEAPEST
)

# Most reliable path (maximize success probability)
reliable = service.find_optimal_path(
    "miner_g4_001",
    "validator_network",
    PathStrategy.MOST_RELIBLE
)

# Balanced path (weighted combination)
balanced = service.find_optimal_path(
    "miner_g4_001",
    "validator_network",
    PathStrategy.BALANCED
)
```

## API Reference

### PathStrategy

Enumeration of path optimization strategies:

- `FASTEST` - Minimize total latency
- `CHEAPEST` - Minimize total fees
- `MOST_RELIBLE` - Maximize success probability
- `BALANCED` - Weighted combination (40% latency, 30% fee, 30% reliability)

### NetworkNode

Represents a node in the network graph:

```python
from rustchain.path import NetworkNode

node = NetworkNode(
    node_id="miner_g4_001",
    node_type="miner",           # 'miner', 'validator', 'relay'
    latency_ms=120.0,            # Network latency
    reliability=0.95,            # 0.0 to 1.0
    capacity=1.0,                # Relative capacity
    geography="US-West",         # Optional geography
    architecture="PowerPC G4"    # Hardware architecture
)
```

### PathOptimizer

Core pathfinding engine:

```python
from rustchain.path import PathOptimizer, PathStrategy

optimizer = PathOptimizer()

# Add nodes
optimizer.add_node(NetworkNode("A", "miner"))
optimizer.add_node(NetworkNode("B", "relay"))
optimizer.add_node(NetworkNode("C", "validator"))

# Add edges
optimizer.add_edge("A", "B", latency_ms=50.0, fee=0.001, reliability=0.95)
optimizer.add_edge("B", "C", latency_ms=30.0, fee=0.001, reliability=0.98)

# Find path
path = optimizer.find_path("A", "C", PathStrategy.FASTEST)
print(f"Path: {path.nodes}")  # ['A', 'B', 'C']
```

### NetworkPathService

High-level service with live network integration:

```python
from rustchain import RustChainClient, NetworkPathService

client = RustChainClient("https://rustchain.org", verify_ssl=False)
service = NetworkPathService(client)

# Refresh from live network
service.refresh_network_data()

# Get network stats
stats = service.get_network_stats()
print(f"Total nodes: {stats['total_nodes']}")
print(f"Healthy nodes: {stats['healthy_nodes']}")
print(f"Avg latency: {stats['avg_latency_ms']}ms")

# Check if data is fresh
if not service.is_fresh():
    service.refresh_network_data()
```

## Live Network Integration

### Endpoints Used

The path module integrates with these live RustChain endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/epoch` | GET | Current epoch number and slot |
| `/api/miners` | GET | List of all active miners |
| `/health` | GET | Node health status |

### Data Refresh

Network data is automatically refreshed:

- **Interval**: Every 60 seconds
- **Auto-refresh**: Triggered when finding paths with stale data
- **Manual refresh**: Call `service.refresh_network_data()`

```python
# Manual refresh
result = service.refresh_network_data()
if result["success"]:
    print(f"Refreshed {result['nodes_added']} nodes")
else:
    print(f"Refresh failed: {result['error']}")
```

### Hardware Latency Profiles

The module estimates latency based on hardware architecture:

| Architecture | Estimated Latency |
|-------------|-------------------|
| PowerPC G3 | 150ms |
| PowerPC G4 | 120ms |
| PowerPC G5 | 100ms |
| x86_64 | 80ms |
| ARM | 90ms |
| Unknown | 100ms |

## Use Cases

### 1. Transaction Routing

Route transactions through the optimal path to minimize fees or latency:

```python
def route_transaction(from_miner, amount):
    """Route a transaction optimally"""
    paths = service.find_optimal_path(
        from_miner,
        "validator_network",
        PathStrategy.CHEAPEST
    )
    
    if paths:
        path = paths[0]
        if path.success_probability > 0.9:
            # Proceed with transaction
            print(f"Routing via {path.hop_count} hops")
            print(f"Total fee: {path.total_fee:.6f} RTC")
            return True
    return False
```

### 2. Attestation Path Optimization

Optimize attestation submission paths:

```python
def submit_attestation_optimal(miner_id, attestation_data):
    """Submit attestation via optimal path"""
    paths = service.find_optimal_path(
        f"miner_{miner_id[:16]}",
        "validator_network",
        PathStrategy.MOST_RELIBLE
    )
    
    if paths and paths[0].success_probability > 0.95:
        # Submit via most reliable path
        result = client.submit_attestation(attestation_data)
        return result
    else:
        raise Exception("No reliable path available")
```

### 3. Network Monitoring

Monitor network health and topology:

```python
def monitor_network_health():
    """Monitor network health metrics"""
    stats = service.get_network_stats()
    
    print(f"Network Health Report:")
    print(f"  Total Nodes: {stats['total_nodes']}")
    print(f"  Healthy: {stats['healthy_nodes']} ({stats['healthy_nodes']/stats['total_nodes']:.1%})")
    print(f"  Avg Latency: {stats['avg_latency_ms']}ms")
    print(f"  Avg Reliability: {stats['avg_reliability']:.2%}")
    print(f"  Data Age: {stats['refresh_age_seconds']}s")
    
    return stats['healthy_nodes'] / stats['total_nodes'] > 0.8
```

### 4. Multi-Path Comparison

Compare different path strategies:

```python
def compare_paths(from_node, to_node):
    """Compare all path strategies"""
    print(f"Path Comparison: {from_node} -> {to_node}\n")
    
    for strategy in PathStrategy:
        paths = service.find_optimal_path(from_node, to_node, strategy)
        
        if paths:
            path = paths[0]
            print(f"{strategy.value.upper()}:")
            print(f"  Latency: {path.total_latency_ms}ms")
            print(f"  Fee: {path.total_fee:.6f} RTC")
            print(f"  Reliability: {path.success_probability:.2%}")
            print(f"  Hops: {path.hop_count}")
            print()
```

## Testing

### Unit Tests

Run unit tests (no network required):

```bash
cd sdk
pytest tests/test_path.py -v
```

### Integration Tests

Run integration tests (requires network access):

```bash
cd sdk
pytest tests/test_path_integration.py -v -m integration
```

### Manual Verification

Verify with live network:

```python
from rustchain import RustChainClient, NetworkPathService, PathStrategy

client = RustChainClient("https://rustchain.org", verify_ssl=False)
service = NetworkPathService(client)

# Refresh and verify
result = service.refresh_network_data()
assert result["success"] is True
assert result["epoch"] > 0

# Get stats
stats = service.get_network_stats()
print(f"Network has {stats['total_nodes']} nodes")
print(f"Average latency: {stats['avg_latency_ms']}ms")

# Find a path
miner_nodes = [n for n in service.optimizer.nodes if n.startswith("miner_")]
if miner_nodes:
    paths = service.find_optimal_path(miner_nodes[0], "validator_network")
    assert len(paths) > 0
    print(f"Found path with {paths[0].hop_count} hops")

client.close()
print("✓ All verifications passed")
```

## Run and Verify Steps

### Step 1: Install Dependencies

```bash
cd /path/to/rustchain-wt/issue618-rework2/sdk
pip install -e ".[dev]"
```

### Step 2: Run Unit Tests

```bash
# Run path module unit tests
pytest tests/test_path.py -v

# Expected output:
# test_path.py::TestNetworkNode::test_create_node PASSED
# test_path.py::TestPathSegment::test_create_segment PASSED
# test_path.py::TestPathOptimizer::test_find_path_simple PASSED
# ...
```

### Step 3: Run Integration Tests

```bash
# Run integration tests against live node
pytest tests/test_path_integration.py -v -m integration

# Expected output:
# test_path_integration.py::TestLivePathOptimization::test_refresh_with_live_data PASSED
# test_path_integration.py::TestLivePathOptimization::test_network_stats_from_live PASSED
# ...
```

### Step 4: Manual Verification

```bash
# Run manual verification script
python -c "
from rustchain import RustChainClient, NetworkPathService
client = RustChainClient('https://rustchain.org', verify_ssl=False)
service = NetworkPathService(client)
result = service.refresh_network_data()
print(f'✓ Refreshed {result[\"nodes_added\"]} nodes from epoch {result[\"epoch\"]}')
stats = service.get_network_stats()
print(f'✓ Network has {stats[\"total_nodes\"]} nodes')
print(f'✓ Average latency: {stats[\"avg_latency_ms\"]}ms')
client.close()
"
```

### Step 5: Verify Live Endpoints

```bash
# Verify live endpoints are accessible
curl -sk https://rustchain.org/health | jq .
curl -sk https://rustchain.org/epoch | jq .
curl -sk https://rustchain.org/api/miners | jq '. | length'

# Expected: Health OK, epoch > 0, miners >= 0
```

## Performance Considerations

- **Pathfinding Complexity**: O(E + V log V) using Dijkstra's algorithm
- **Refresh Interval**: 60 seconds (configurable)
- **Memory**: O(V + E) for graph storage
- **Network Calls**: 2 per refresh (epoch + miners)

## Error Handling

```python
from rustchain import RustChainClient, NetworkPathService
from rustchain.exceptions import ConnectionError, APIError

client = RustChainClient("https://rustchain.org", verify_ssl=False, timeout=10)
service = NetworkPathService(client)

try:
    result = service.refresh_network_data()
    if not result["success"]:
        print(f"Refresh failed: {result['error']}")
        # Fallback to cached data or retry
except ConnectionError as e:
    print(f"Connection failed: {e}")
    # Handle network error
except APIError as e:
    print(f"API error: {e}")
    # Handle API error
finally:
    client.close()
```

## Troubleshooting

### No Paths Found

**Problem**: `find_optimal_path()` returns empty list

**Solutions**:
1. Check if network data is refreshed: `service.refresh_network_data()`
2. Verify node IDs exist: `print(service.optimizer.nodes.keys())`
3. Check for typos in node IDs

### Stale Data

**Problem**: Network stats show old data

**Solutions**:
1. Force refresh: `service.refresh_network_data()`
2. Check refresh interval: `print(service._refresh_interval)`
3. Verify data freshness: `if not service.is_fresh(): refresh()`

### Connection Errors

**Problem**: Cannot connect to live node

**Solutions**:
1. Check network connectivity
2. Verify URL: `https://rustchain.org`
3. Try with `verify_ssl=False` for self-signed certs
4. Increase timeout: `RustChainClient(..., timeout=30)`

## Related Documentation

- [SDK README](../sdk/README.md)
- [API Reference](../docs/api-reference.md)
- [Protocol Overview](../docs/protocol-overview.md)

## License

MIT License - See [LICENSE](../sdk/LICENSE) for details.
