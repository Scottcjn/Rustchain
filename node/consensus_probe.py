#!/usr/bin/env python3
"""
Cross-node consistency probe for RustChain.

This is a read-only operational tool that compares public API snapshots across
multiple nodes and emits a machine-readable report with a non-zero exit code
on divergence.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from typing import Callable, List, Optional
from urllib.request import urlopen


Fetcher = Callable[..., dict]


@dataclass
class NodeSnapshot:
    node: str
    ok: bool
    version: Optional[str]
    enrolled_miners: Optional[int]
    miners_count: Optional[int]
    total_balance: Optional[float]
    error: Optional[str]


def _default_fetcher(url: str, timeout: int) -> dict:
    """
    Default HTTP fetcher using urllib.
    
    Args:
        url: URL to fetch JSON from
        timeout: Request timeout in seconds
        
    Returns:
        dict: Parsed JSON response
        
    Raises:
        urllib.error.URLError: On network errors
        json.JSONDecodeError: On invalid JSON response
    """
    with urlopen(url, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _fetch_json(node_url: str, endpoint: str, timeout_s: int, fetcher: Fetcher):
    """
    Fetch JSON from a node endpoint.
    
    Args:
        node_url: Base URL of the node (e.g., "http://localhost:8088")
        endpoint: API endpoint path (e.g., "/health", "/epoch")
        timeout_s: Request timeout in seconds
        fetcher: Callable to perform the HTTP request
        
    Returns:
        dict: Parsed JSON response from the endpoint
    """
    url = f"{node_url.rstrip('/')}{endpoint}"
    return fetcher(url, timeout=timeout_s)


def collect_snapshot(node_url: str, timeout_s: int = 8, fetcher: Fetcher = _default_fetcher) -> NodeSnapshot:
    """
    Collect a snapshot of node state from multiple API endpoints.
    
    Fetches health, epoch, stats, and miners data from a node and packages
    it into a NodeSnapshot for comparison with other nodes.
    
    Args:
        node_url: Base URL of the node to probe
        timeout_s: HTTP request timeout in seconds (default: 8)
        fetcher: Optional custom fetcher function (default: _default_fetcher)
        
    Returns:
        NodeSnapshot: Snapshot containing node state or error information
        
    Note:
        Returns a snapshot with ok=False and error set if any endpoint fails
    """
    try:
        health = _fetch_json(node_url, "/health", timeout_s, fetcher)
        epoch = _fetch_json(node_url, "/epoch", timeout_s, fetcher)
        stats = _fetch_json(node_url, "/api/stats", timeout_s, fetcher)
        miners = _fetch_json(node_url, "/api/miners", timeout_s, fetcher)

        miners_count = len(miners) if isinstance(miners, list) else 0

        return NodeSnapshot(
            node=node_url,
            ok=bool(health.get("ok", False)),
            version=health.get("version"),
            enrolled_miners=epoch.get("enrolled_miners"),
            miners_count=miners_count,
            total_balance=stats.get("total_balance"),
            error=None,
        )
    except Exception as exc:
        return NodeSnapshot(
            node=node_url,
            ok=False,
            version=None,
            enrolled_miners=None,
            miners_count=None,
            total_balance=None,
            error=str(exc),
        )


def _span(values: List[float]) -> float:
    """
    Calculate the span (range) of a list of values.
    
    Args:
        values: List of numeric values
        
    Returns:
        float: Difference between max and min, or 0.0 if empty list
        
    Use case:
        Used to detect divergence in numeric metrics across nodes
    """
    return max(values) - min(values) if values else 0.0


def detect_divergence(snapshots: List[NodeSnapshot], balance_tolerance: float = 1e-6) -> List[str]:
    """
    Detect divergence across node snapshots.
    
    Compares multiple node snapshots and identifies inconsistencies:
    - Unreachable nodes
    - Version mismatches
    - Divergence in enrolled miners count
    - Divergence in miners count
    - Divergence in total balance (within tolerance)
    
    Args:
        snapshots: List of NodeSnapshot objects from different nodes
        balance_tolerance: Allowed delta for total_balance comparison (default: 1e-6)
        
    Returns:
        List[str]: List of issue strings, empty if no divergence detected
        
    Issue formats:
        - "unreachable_nodes:node1,node2,..."
        - "insufficient_healthy_nodes"
        - "version_mismatch:v1,v2,..."
        - "divergence_enrolled_miners"
        - "divergence_miners_count"
        - "divergence_total_balance"
    """
    issues: List[str] = []

    failed = [s.node for s in snapshots if s.error]
    if failed:
        issues.append(f"unreachable_nodes:{','.join(failed)}")

    healthy = [s for s in snapshots if not s.error]
    if len(healthy) < 2:
        issues.append("insufficient_healthy_nodes")
        return issues

    versions = sorted({s.version for s in healthy if s.version})
    if len(versions) > 1:
        issues.append(f"version_mismatch:{','.join(versions)}")

    enrolled = [float(s.enrolled_miners) for s in healthy if s.enrolled_miners is not None]
    if enrolled and _span(enrolled) > 0:
        issues.append("divergence_enrolled_miners")

    miner_counts = [float(s.miners_count) for s in healthy if s.miners_count is not None]
    if miner_counts and _span(miner_counts) > 0:
        issues.append("divergence_miners_count")

    balances = [float(s.total_balance) for s in healthy if s.total_balance is not None]
    if balances and _span(balances) > balance_tolerance:
        issues.append("divergence_total_balance")

    return issues


def run_probe(nodes: List[str], timeout_s: int = 8, balance_tolerance: float = 1e-6):
    """
    Run the cross-node consistency probe.
    
    Collects snapshots from all specified nodes and detects any divergence.
    
    Args:
        nodes: List of node base URLs to compare (e.g., ["http://node1:8088", "http://node2:8088"])
        timeout_s: HTTP request timeout in seconds (default: 8)
        balance_tolerance: Allowed delta for total_balance comparison (default: 1e-6)
        
    Returns:
        Tuple[int, dict]: (exit_code, report)
            - exit_code: 0 (no issues), 1 (minor issues), 2 (divergence detected)
            - report: Dictionary with timestamp, nodes, and issues
    """
    snapshots = [collect_snapshot(node, timeout_s=timeout_s) for node in nodes]
    issues = detect_divergence(snapshots, balance_tolerance=balance_tolerance)

    report = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": [asdict(s) for s in snapshots],
        "issues": issues,
    }

    if issues:
        if any(i.startswith("divergence") or i.startswith("version_mismatch") for i in issues):
            return 2, report
        return 1, report
    return 0, report


def parse_args():
    """
    Parse command-line arguments for the probe.
    
    Returns:
        argparse.Namespace: Parsed arguments with attributes:
            - nodes: List of node URLs to compare
            - timeout: HTTP timeout in seconds
            - balance_tolerance: Allowed balance delta
            - pretty: Whether to pretty-print JSON output
    """
    parser = argparse.ArgumentParser(description="RustChain cross-node consistency probe")
    parser.add_argument("--nodes", nargs="+", required=True, help="Node base URLs to compare")
    parser.add_argument("--timeout", type=int, default=8, help="HTTP timeout in seconds")
    parser.add_argument(
        "--balance-tolerance",
        type=float,
        default=1e-6,
        help="Allowed max delta for total_balance before flagging divergence",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the consensus probe CLI.
    
    Parses arguments, runs the probe, prints the report, and returns exit code.
    
    Returns:
        int: Exit code (0=no issues, 1=minor issues, 2=divergence detected)
        
    Usage:
        python consensus_probe.py --nodes http://node1:8088 http://node2:8088 --pretty
    """
    args = parse_args()
    code, report = run_probe(args.nodes, timeout_s=args.timeout, balance_tolerance=args.balance_tolerance)
    if args.pretty:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
