#!/usr/bin/env python3
"""
RustChain Health Check CLI
Queries all 3 attestation nodes and displays health status.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests

# Attestation nodes
NODES = [
    {"host": "50.28.86.131", "port": 8099, "name": "Node 1"},
    {"host": "50.28.86.153", "port": 8099, "name": "Node 2"},
    {"host": "76.8.228.245", "port": 8099, "name": "Node 3"},
]


def query_node(host: str, port: int) -> Optional[Dict]:
    """Query a node for health status."""
    url = f"http://{host}:{port}/health"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        pass
    
    # Try alternate endpoint
    try:
        url = f"http://{host}:{port}/api/health"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    
    return None


def format_uptime(seconds: int) -> str:
    """Format uptime in human readable format."""
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
    """Format tip age in human readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"


def print_table(health_data: List[Dict]):
    """Print health status in table format."""
    print("\n" + "=" * 80)
    print("RustChain Node Health Status")
    print(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)
    
    # Table header
    print(f"{'Node':<12} {'Version':<10} {'Uptime':<12} {'DB RW':<10} {'Tip Age':<12} {'Status':<10}")
    print("-" * 80)
    
    for node_info in health_data:
        name = node_info.get("name", "Unknown")
        if node_info.get("online"):
            version = node_info.get("version", "N/A")
            uptime = format_uptime(node_info.get("uptime", 0))
            db_rw = "RW" if node_info.get("db_rw") else "RO"
            tip_age = format_tip_age(node_info.get("tip_age", 0))
            status = "✓ ONLINE"
        else:
            version = "N/A"
            uptime = "N/A"
            db_rw = "N/A"
            tip_age = "N/A"
            status = "✗ OFFLINE"
        
        print(f"{name:<12} {version:<10} {uptime:<12} {db_rw:<10} {tip_age:<12} {status:<10}")
    
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="RustChain Health Check CLI")
    parser.add_argument("-j", "--json", action="store_true", help="Output in JSON format")
    parser.add_argument("-w", "--watch", action="store_true", help="Watch mode (continuous monitoring)")
    parser.add_argument("-i", "--interval", type=int, default=10, help="Watch interval in seconds")
    args = parser.parse_args()
    
    health_data = []
    
    for node in NODES:
        result = {"name": node["name"], "host": node["host"], "online": False}
        
        data = query_node(node["host"], node["port"])
        if data:
            result["online"] = True
            result["version"] = data.get("version", data.get("version", "unknown"))
            result["uptime"] = data.get("uptime", 0)
            result["db_rw"] = data.get("db_rw", True)
            result["tip_age"] = data.get("tip_age", data.get("tipHeightAge", 0))
        
        health_data.append(result)
    
    if args.json:
        print(json.dumps(health_data, indent=2))
    else:
        print_table(health_data)
    
    # Watch mode
    if args.watch:
        try:
            while True:
                time.sleep(args.interval)
                health_data = []
                for node in NODES:
                    result = {"name": node["name"], "host": node["host"], "online": False}
                    data = query_node(node["host"], node["port"])
                    if data:
                        result["online"] = True
                        result["version"] = data.get("version", "unknown")
                        result["uptime"] = data.get("uptime", 0)
                        result["db_rw"] = data.get("db_rw", True)
                        result["tip_age"] = data.get("tip_age", data.get("tipHeightAge", 0))
                    health_data.append(result)
                
                # Clear screen and print
                print("\033[2J\033[H", end="")  # Clear screen
                if args.json:
                    print(json.dumps(health_data, indent=2))
                else:
                    print_table(health_data)
        except KeyboardInterrupt:
            print("\nStopped.")
            sys.exit(0)


if __name__ == "__main__":
    main()
