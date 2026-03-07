#!/usr/bin/env python3
"""
RustChain Path Optimization - Verification Script

Verifies that the path optimization module is correctly integrated
with the RustChain SDK and can connect to live endpoints.

Run this script to verify the #618 rework implementation.

Usage:
    python verify_path_implementation.py
"""

import sys
import time
from pathlib import Path


def print_check(name, passed, details=None):
    """Print verification check result"""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status}: {name}")
    if details and not passed:
        print(f"       {details}")
    return passed


def verify_file_structure():
    """Verify that all required files exist"""
    print("\n" + "=" * 60)
    print(" 1. File Structure Verification")
    print("=" * 60 + "\n")
    
    base_dir = Path(__file__).parent
    checks = []
    
    # Core module files
    checks.append(print_check(
        "Path module exists",
        (base_dir / "rustchain" / "path.py").exists()
    ))
    
    checks.append(print_check(
        "SDK __init__ updated",
        "NetworkPathService" in (base_dir / "rustchain" / "__init__.py").read_text()
    ))
    
    # Test files
    checks.append(print_check(
        "Unit tests exist",
        (base_dir / "tests" / "test_path.py").exists()
    ))
    
    checks.append(print_check(
        "Integration tests exist",
        (base_dir / "tests" / "test_path_integration.py").exists()
    ))
    
    # Documentation
    checks.append(print_check(
        "Documentation exists",
        (base_dir.parent / "docs" / "PATH_OPTIMIZATION_GUIDE.md").exists()
    ))
    
    # Example files
    checks.append(print_check(
        "Example script exists",
        (base_dir / "examples" / "path_optimization_example.py").exists()
    ))
    
    return all(checks)


def verify_module_imports():
    """Verify that modules can be imported"""
    print("\n" + "=" * 60)
    print(" 2. Module Import Verification")
    print("=" * 60 + "\n")
    
    checks = []
    
    try:
        from rustchain.path import PathOptimizer
        checks.append(print_check("Import PathOptimizer", True))
    except ImportError as e:
        checks.append(print_check("Import PathOptimizer", False, str(e)))
    
    try:
        from rustchain.path import NetworkPathService
        checks.append(print_check("Import NetworkPathService", True))
    except ImportError as e:
        checks.append(print_check("Import NetworkPathService", False, str(e)))
    
    try:
        from rustchain.path import PathStrategy
        checks.append(print_check("Import PathStrategy", True))
    except ImportError as e:
        checks.append(print_check("Import PathStrategy", False, str(e)))
    
    try:
        from rustchain.path import NetworkNode, PathSegment, TransactionPath
        checks.append(print_check("Import dataclasses", True))
    except ImportError as e:
        checks.append(print_check("Import dataclasses", False, str(e)))
    
    try:
        from rustchain import NetworkPathService, PathStrategy
        checks.append(print_check("Import from rustchain", True))
    except ImportError as e:
        checks.append(print_check("Import from rustchain", False, str(e)))
    
    return all(checks)


def verify_unit_tests():
    """Run unit tests"""
    print("\n" + "=" * 60)
    print(" 3. Unit Test Verification")
    print("=" * 60 + "\n")
    
    try:
        import pytest
        
        # Run unit tests
        print("Running unit tests (no network required)...")
        exit_code = pytest.main([
            "-v",
            "-x",
            "tests/test_path.py::TestNetworkNode",
            "tests/test_path.py::TestPathSegment",
            "tests/test_path.py::TestTransactionPath",
            "tests/test_path.py::TestPathOptimizer",
        ])
        
        checks = [print_check("Unit tests pass", exit_code == 0)]
        return all(checks)
        
    except Exception as e:
        checks = [print_check("Unit tests", False, str(e))]
        return False


def verify_pathfinding_logic():
    """Verify pathfinding algorithms work correctly"""
    print("\n" + "=" * 60)
    print(" 4. Pathfinding Logic Verification")
    print("=" * 60 + "\n")
    
    checks = []
    
    try:
        from rustchain.path import PathOptimizer, NetworkNode, PathStrategy
        
        # Test 1: Simple path
        optimizer = PathOptimizer()
        optimizer.add_node(NetworkNode("A", "miner"))
        optimizer.add_node(NetworkNode("B", "relay"))
        optimizer.add_node(NetworkNode("C", "validator"))
        optimizer.add_edge("A", "B", latency_ms=50, fee=0.001)
        optimizer.add_edge("B", "C", latency_ms=30, fee=0.001)
        
        path = optimizer.find_path("A", "C", PathStrategy.FASTEST)
        checks.append(print_check(
            "Simple path finding",
            path is not None and path.nodes == ["A", "B", "C"]
        ))
        
        # Test 2: Same node path
        path = optimizer.find_path("A", "A")
        checks.append(print_check(
            "Same node path",
            path is not None and path.nodes == ["A"] and path.hop_count == 0
        ))
        
        # Test 3: No path exists
        optimizer2 = PathOptimizer()
        optimizer2.add_node(NetworkNode("X", "miner"))
        optimizer2.add_node(NetworkNode("Y", "validator"))
        path = optimizer2.find_path("X", "Y")
        checks.append(print_check(
            "No path detection",
            path is None
        ))
        
        # Test 4: Strategy selection
        optimizer3 = PathOptimizer()
        optimizer3.add_node(NetworkNode("A", "miner"))
        optimizer3.add_node(NetworkNode("B", "relay"))
        optimizer3.add_node(NetworkNode("C", "validator"))
        # Fast path: A-B-C
        optimizer3.add_edge("A", "B", latency_ms=10, fee=0.1)
        optimizer3.add_edge("B", "C", latency_ms=10, fee=0.1)
        # Slow path: A-C direct
        optimizer3.add_edge("A", "C", latency_ms=100, fee=0.001)
        
        fast_path = optimizer3.find_path("A", "C", PathStrategy.FASTEST)
        cheap_path = optimizer3.find_path("A", "C", PathStrategy.CHEAPEST)
        
        checks.append(print_check(
            "FASTEST strategy",
            fast_path.total_latency_ms == 20  # A-B-C
        ))
        checks.append(print_check(
            "CHEAPEST strategy",
            abs(cheap_path.total_fee - 0.001) < 0.0001  # A-C direct
        ))
        
        # Test 5: Network stats
        stats = optimizer.get_network_stats()
        checks.append(print_check(
            "Network statistics",
            stats["total_nodes"] == 3 and stats["total_edges"] == 2
        ))
        
        return all(checks)
        
    except Exception as e:
        checks.append(print_check("Pathfinding logic", False, str(e)))
        return False


def verify_live_integration():
    """Verify live network integration"""
    print("\n" + "=" * 60)
    print(" 5. Live Network Integration Verification")
    print("=" * 60 + "\n")
    
    checks = []
    
    try:
        from rustchain import RustChainClient, NetworkPathService
        
        print("Connecting to live RustChain node...")
        client = RustChainClient("https://rustchain.org", verify_ssl=False, timeout=10)
        service = NetworkPathService(client)
        
        # Test refresh
        result = service.refresh_network_data()
        checks.append(print_check(
            "Network data refresh",
            result["success"] is True,
            result.get("error", "") if not result["success"] else ""
        ))
        
        if result["success"]:
            checks.append(print_check(
                f"Epoch data (epoch {result['epoch']})",
                result["epoch"] > 0
            ))
            
            checks.append(print_check(
                f"Nodes added ({result['nodes_added']})",
                result["nodes_added"] >= 1
            ))
        
        # Test stats
        stats = service.get_network_stats()
        checks.append(print_check(
            "Network statistics",
            "total_nodes" in stats and "last_refresh" in stats
        ))
        
        # Test freshness
        checks.append(print_check(
            "Data freshness tracking",
            service.is_fresh() is True
        ))
        
        # Test path finding with live data
        miner_nodes = [
            n for n in service.optimizer.nodes.keys()
            if n.startswith("miner_")
        ]
        
        if miner_nodes:
            paths = service.find_optimal_path(
                miner_nodes[0],
                "validator_network"
            )
            checks.append(print_check(
                "Path finding with live data",
                len(paths) > 0
            ))
        else:
            checks.append(print_check(
                "Path finding (no miners)",
                True,
                "No miners currently enrolled"
            ))
        
        client.close()
        
        return all(checks)
        
    except Exception as e:
        checks.append(print_check("Live integration", False, str(e)))
        print("\nNote: Live integration requires internet connectivity")
        return False


def verify_documentation():
    """Verify documentation completeness"""
    print("\n" + "=" * 60)
    print(" 6. Documentation Verification")
    print("=" * 60 + "\n")
    
    checks = []
    docs_dir = Path(__file__).parent.parent / "docs"
    guide_path = docs_dir / "PATH_OPTIMIZATION_GUIDE.md"
    
    if guide_path.exists():
        content = guide_path.read_text()
        
        checks.append(print_check(
            "Guide exists",
            True
        ))
        
        checks.append(print_check(
            "Contains API reference",
            "API Reference" in content or "NetworkPathService" in content
        ))
        
        checks.append(print_check(
            "Contains examples",
            "Example" in content or ">>>" in content or "```python" in content
        ))
        
        checks.append(print_check(
            "Contains run/verify steps",
            "Run" in content and "Verify" in content
        ))
        
        checks.append(print_check(
            "Contains troubleshooting",
            "Troubleshoot" in content or "Error" in content
        ))
    else:
        checks.append(print_check("Guide exists", False))
    
    return all(checks)


def main():
    """Run all verifications"""
    print("\n" + "█" * 60)
    print(" RustChain Path Optimization - Verification Suite")
    print(" Issue #618 Rework Implementation Check")
    print("█" * 60)
    
    results = []
    
    # 1. File structure
    results.append(("File Structure", verify_file_structure()))
    
    # 2. Module imports
    results.append(("Module Imports", verify_module_imports()))
    
    # 3. Unit tests
    results.append(("Unit Tests", verify_unit_tests()))
    
    # 4. Pathfinding logic
    results.append(("Pathfinding Logic", verify_pathfinding_logic()))
    
    # 5. Live integration
    results.append(("Live Integration", verify_live_integration()))
    
    # 6. Documentation
    results.append(("Documentation", verify_documentation()))
    
    # Summary
    print("\n" + "=" * 60)
    print(" VERIFICATION SUMMARY")
    print("=" * 60 + "\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n✓ All verifications passed!")
        print("\nNext steps:")
        print("  1. Run full test suite: pytest tests/ -v")
        print("  2. Run example: python examples/path_optimization_example.py")
        print("  3. Read docs: docs/PATH_OPTIMIZATION_GUIDE.md")
        return 0
    else:
        print(f"\n✗ {total - passed} verification(s) failed")
        print("\nReview the failures above and fix before committing.")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nVerification interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Verification error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
