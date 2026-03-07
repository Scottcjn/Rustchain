#!/usr/bin/env python3
"""
RustChain Health Check CLI Tool
Queries all 3 attestation nodes and displays health status.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Optional

import requests


NODES = [
    {"name": "Node 1", "host": "50.28.86.131", "port": 8099},
    {"name": "Node 2", "host": "50.28.86.153", "port": 8099},
    {"name": "Node 3", "host": "76.8.228.245", "port": 8099},
]


def get_node_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def query_node(host: str, port: int, endpoint: str, timeout: int = 5) -> Optional[dict]:
    """Query a node endpoint and return JSON response."""
    url = f"{get_node_url(host, port)}{endpoint}"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def get_node_health(host: str, port: int) -> dict:
    """Get health status of a node."""
    result = {"host": host, "port": port, "online": False}
    
    # Try to get node info
    info = query_node(host, port, "/info")
    if info and "error" not in info:
        result["online"] = True
        result["version"] = info.get("version", "unknown")
        result["chain_id"] = info.get("chainId", info.get("chain_id", "unknown"))
    
    # Try to get status
    status = query_node(host, port, "/status")
    if status and "error" not in status:
        result["online"] = True
        result["uptime"] = status.get("uptime", "unknown")
        result["db_rw"] = status.get("db_rw", status.get("dbReadWrite", "unknown"))
        result["tip_age"] = status.get("tip", {}).get("age", status.get("tip_age", "unknown"))
        result["block_number"] = status.get("tip", {}).get("number", status.get("block_number", "unknown"))
    
    return result


def format_uptime(seconds: int) -> str:
    """Format uptime seconds to human readable."""
    if not isinstance(seconds, int):
        return str(seconds)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def format_tip_age(seconds: int) -> str:
    """Format tip age seconds to human readable."""
    if not isinstance(seconds, int):
        return str(seconds)
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    elif seconds < 86400:
        return f"{seconds // 3600}h"
    else:
        return f"{seconds // 86400}d"


def print_health_table(results: list):
    """Print health status in table format."""
    # Header
    print("\n" + "=" * 100)
    print(f"RustChain Attestation Nodes Health Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 100)
    print()
    print(f"{'Node':<20} {'Host':<20} {'Port':<8} {'Online':<8} {'Version':<12} {'Uptime':<12} {'DB RW':<10} {'Tip Age':<10} {'Block':<10}")
    print("-" * 100)
    
    # Rows
    for result in results:
        name = result.get("name", "Unknown")
        host = result.get("host", "")
        port = result.get("port", "")
        online = "✓ Online" if result.get("online") else "✗ Offline"
        version = result.get("version", "-")
        uptime = format_uptime(result.get("uptime", 0)) if result.get("online") else "-"
        db_rw = str(result.get("db_rw", "-"))
        tip_age = format_tip_age(result.get("tip_age", 0)) if result.get("online") else "-"
        block = str(result.get("block_number", "-")) if result.get("online") else "-"
        
        print(f"{name:<20} {host:<20} {port:<8} {online:<8} {version:<12} {uptime:<12} {db_rw:<10} {tip_age:<10} {block:<10}")
    
    print("-" * 100)
    
    # Summary
    online_count = sum(1 for r in results if r.get("online"))
    total_count = len(results)
    print(f"\nSummary: {online_count}/{total_count} nodes online")
    print()


def print_json_output(results: list):
    """Print results as JSON."""
    output = {
        "timestamp": datetime.now().isoformat(),
        "nodes": results
    }
    print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="RustChain Health Check CLI - Query attestation nodes and display health status"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON instead of table"
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=5,
        help="Request timeout in seconds (default: 5)"
    )
    parser.add_argument(
        "--node", "-n",
        type=int,
        choices=[1, 2, 3],
        help="Query specific node (1, 2, or 3)"
    )
    
    args = parser.parse_args()
    
    # Determine which nodes to query
    if args.node:
        nodes_to_query = [NODES[args.node - 1]]
    else:
        nodes_to_query = NODES
    
    # Query all nodes
    results = []
    for node in nodes_to_query:
        print(f"Checking {node['name']} ({node['host']}:{node['port']})...", end=" ", flush=True)
        health = get_node_health(node["host"], node["port"])
        health["name"] = node["name"]
        results.append(health)
        status = "Online" if health.get("online") else "Offline"
        print(status)
    
    # Output results
    if args.json:
        print_json_output(results)
    else:
        print_health_table(results)
    
    # Exit code: 0 if all nodes online, 1 otherwise
    online_count = sum(1 for r in results if r.get("online"))
    sys.exit(0 if online_count == len(results) else 1)


if __name__ == "__main__":
    main()
