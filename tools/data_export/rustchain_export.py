#!/usr/bin/env python3
"""
RustChain Data Export Pipeline

Export RustChain attestation and reward data to CSV, JSON, or JSONL.

Usage:
    python rustchain_export.py --format csv --output data/
    python rustchain_export.py --format json --output data/ --from 2025-12-01 --to 2026-02-01
"""

import os
import sys
import json
import csv
import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Configuration
NODE_URL = os.environ.get("NODE_URL", "https://50.28.86.131")


def get_miners() -> List[Dict]:
    """Fetch all miners."""
    try:
        resp = requests.get(f"{NODE_URL}/api/miners", timeout=30)
        if resp.status_code == 200:
            return resp.json().get("miners", [])
        return []
    except Exception as e:
        print(f"Error fetching miners: {e}")
        return []


def get_epoch() -> Dict:
    """Fetch current epoch info."""
    try:
        resp = requests.get(f"{NODE_URL}/epoch", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return {}
    except Exception:
        return {}


def get_balance(miner_id: str) -> Dict:
    """Fetch balance for a specific miner."""
    try:
        resp = requests.get(
            f"{NODE_URL}/wallet/balance",
            params={"miner_id": miner_id},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
        return {}
    except Exception:
        return {}


def export_miners(miners: List[Dict], output_dir: Path, format: str):
    """Export miners data."""
    if not miners:
        print("No miners data to export")
        return
    
    filename = output_dir / f"miners.{format}"
    
    if format == "csv":
        with open(filename, "w", newline="") as f:
            if miners:
                writer = csv.DictWriter(f, fieldnames=miners[0].keys())
                writer.writeheader()
                writer.writerows(miners)
    elif format == "json":
        with open(filename, "w") as f:
            json.dump(miners, f, indent=2)
    elif format == "jsonl":
        with open(filename, "w") as f:
            for m in miners:
                f.write(json.dumps(m) + "\n")
    
    print(f"Exported {len(miners)} miners to {filename}")


def export_balances(miners: List[Dict], output_dir: Path, format: str):
    """Export balances data."""
    filename = output_dir / f"balances.{format}"
    
    balances = []
    for m in miners:
        miner_id = m.get("miner_id")
        balance_info = get_balance(miner_id)
        if balance_info:
            balance_info["miner_id"] = miner_id
            balances.append(balance_info)
    
    if format == "csv":
        if balances:
            with open(filename, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=balances[0].keys())
                writer.writeheader()
                writer.writerows(balances)
    elif format == "json":
        with open(filename, "w") as f:
            json.dump(balances, f, indent=2)
    elif format == "jsonl":
        with open(filename, "w") as f:
            for b in balances:
                f.write(json.dumps(b) + "\n")
    
    print(f"Exported {len(balances)} balances to {filename}")


def export_epochs(output_dir: Path, format: str):
    """Export epoch data."""
    filename = output_dir / f"epochs.{format}"
    epoch = get_epoch()
    
    epochs = [epoch] if epoch else []
    
    if format == "csv":
        if epochs:
            with open(filename, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=epochs[0].keys())
                writer.writeheader()
                writer.writerows(epochs)
    elif format == "json":
        with open(filename, "w") as f:
            json.dump(epochs, f, indent=2)
    elif format == "jsonl":
        with open(filename, "w") as f:
            for e in epochs:
                f.write(json.dumps(e) + "\n")
    
    print(f"Exported epoch data to {filename}")


def export_network_stats(miners: List[Dict], output_dir: Path, format: str):
    """Export network statistics."""
    filename = output_dir / f"network_stats.{format}"
    
    # Calculate stats
    total_miners = len(miners)
    total_balance = sum(m.get("balance", 0) for m in miners)
    
    # Architecture breakdown
    arch_counts = {}
    for m in miners:
        hw = m.get("hardware", "Unknown")
        arch = "Unknown"
        if "G4" in hw:
            arch = "PowerPC G4"
        elif "G5" in hw:
            arch = "PowerPC G5"
        elif "M1" in hw or "M2" in hw or "M3" in hw or "M4" in hw:
            arch = "Apple Silicon"
        elif "POWER8" in hw:
            arch = "IBM POWER8"
        elif "Intel" in hw or "Core" in hw:
            arch = "Modern x86"
        arch_counts[arch] = arch_counts.get(arch, 0) + 1
    
    stats = {
        "export_timestamp": datetime.now().isoformat(),
        "total_miners": total_miners,
        "total_balance_rtc": total_balance,
        "architecture_distribution": arch_counts
    }
    
    if format == "json":
        with open(filename, "w") as f:
            json.dump(stats, f, indent=2)
    elif format == "jsonl":
        with open(filename, "w") as f:
            f.write(json.dumps(stats) + "\n")
    
    print(f"Exported network stats to {filename}")


def main():
    parser = argparse.ArgumentParser(description="RustChain Data Export Pipeline")
    parser.add_argument(
        "--format",
        type=str,
        choices=["csv", "json", "jsonl"],
        default="csv",
        help="Export format"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data",
        help="Output directory"
    )
    parser.add_argument(
        "--from",
        type=str,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--to",
        type=str,
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--node-url",
        type=str,
        default=NODE_URL,
        help="RustChain node URL"
    )
    parser.add_argument(
        "--miners-only",
        action="store_true",
        help="Export miners only (skip balances)"
    )
    
    args = parser.parse_args()
    
    global NODE_URL
    NODE_URL = args.node_url
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📦 Exporting RustChain data to {output_dir}/{args.format}...")
    
    # Export data
    miners = get_miners()
    export_miners(miners, output_dir, args.format)
    export_epochs(output_dir, args.format)
    export_network_stats(miners, output_dir, args.format)
    
    if not args.miners_only:
        print("Fetching balances (this may take a while)...")
        export_balances(miners, output_dir, args.format)
    
    print("✅ Export complete!")


if __name__ == "__main__":
    main()
