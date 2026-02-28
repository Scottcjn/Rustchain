#!/usr/bin/env python3
"""
Discord Rich Presence for RustChain Miners

Shows mining status in your Discord profile using Discord RPC.
- Current hashrate/attestations
- RTC earned today
- Miner uptime
- Hardware type (G4/G5/POWER8/etc)

Requirements:
    pip install pypresence requests

Usage:
    python discord_rpc.py --wallet YOUR_WALLET --client-id YOUR_DISCORD_CLIENT_ID

Or set environment variables:
    export RUSTCHAIN_WALLET=your_wallet
    export DISCORD_CLIENT_ID=your_client_id
    python discord_rpc.py
"""

import os
import sys
import time
import argparse
import requests
from datetime import datetime, timedelta
from pypresence import Presence

# Configuration
NODE_URL = os.environ.get("NODE_URL", "https://50.28.86.131")
UPDATE_INTERVAL = 60  # seconds

# Discord RPC Client ID (you need to create your own at https://discord.com/developers/applications)
DEFAULT_CLIENT_ID = "123456789012345678"  # Replace with your client ID


def get_miner_info(wallet: str) -> dict:
    """Fetch miner information from RustChain node."""
    try:
        # Get balance
        balance_resp = requests.get(
            f"{NODE_URL}/wallet/balance",
            params={"miner_id": wallet},
            timeout=10
        )
        
        # Get miners list
        miners_resp = requests.get(
            f"{NODE_URL}/api/miners",
            timeout=10
        )
        
        # Get epoch
        epoch_resp = requests.get(
            f"{NODE_URL}/epoch",
            timeout=10
        )
        
        result = {
            "balance": 0,
            "miners_count": 0,
            "epoch": 0,
            "hardware": "Unknown"
        }
        
        if balance_resp.status_code == 200:
            data = balance_resp.json()
            result["balance"] = data.get("balance", 0)
            result["today_earnings"] = data.get("today_earnings", 0)
        
        if miners_resp.status_code == 200:
            data = miners_resp.json()
            result["miners_count"] = len(data.get("miners", []))
            # Find this wallet's miner
            for miner in data.get("miners", []):
                if miner.get("miner_id") == wallet:
                    result["hashrate"] = miner.get("hashrate", 0)
                    result["attestations"] = miner.get("attestations", 0)
                    result["uptime"] = miner.get("uptime", 0)
                    result["hardware"] = miner.get("hardware", "Unknown")
                    break
        
        if epoch_resp.status_code == 200:
            data = epoch_resp.json()
            result["epoch"] = data.get("epoch", 0)
            result["epoch_progress"] = data.get("progress", 0)
        
        return result
        
    except Exception as e:
        print(f"Error fetching miner info: {e}")
        return None


def format_uptime(seconds: int) -> str:
    """Format uptime in human-readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    elif seconds < 86400:
        return f"{seconds // 3600}h"
    else:
        return f"{seconds // 86400}d"


def main():
    parser = argparse.ArgumentParser(description="Discord Rich Presence for RustChain Miners")
    parser.add_argument(
        "--wallet",
        type=str,
        default=os.environ.get("RUSTCHAIN_WALLET"),
        help="Your RustChain wallet/miner ID"
    )
    parser.add_argument(
        "--client-id",
        type=str,
        default=os.environ.get("DISCORD_CLIENT_ID", DEFAULT_CLIENT_ID),
        help="Discord application client ID"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=UPDATE_INTERVAL,
        help="Update interval in seconds"
    )
    args = parser.parse_args()
    
    if not args.wallet:
        print("Error: Wallet required!")
        print("Set RUSTCHAIN_WALLET env var or use --wallet")
        sys.exit(1)
    
    print(f"🤖 Starting Discord Rich Presence for wallet: {args.wallet}")
    
    # Initialize Discord RPC
    try:
        RPC = Presence(args.client_id)
        RPC.connect()
        print("✅ Connected to Discord")
    except Exception as e:
        print(f"⚠️  Discord RPC connection failed: {e}")
        print("   Make sure Discord is running and you have a valid client ID")
        sys.exit(1)
    
    # Main loop
    while True:
        info = get_miner_info(args.wallet)
        
        if info:
            # Build presence state
            state_parts = []
            
            if "hashrate" in info:
                state_parts.append(f"⛏️ {info.get('hashrate', 0)} H/s")
            
            if "attestations" in info:
                state_parts.append(f"📝 {info.get('attestations', 0)} attestations")
            
            if "uptime" in info:
                state_parts.append(f"⏱️ {format_uptime(info.get('uptime', 0))}")
            
            state = " | ".join(state_parts) if state_parts else "Mining..."
            
            # Build presence details
            details = f"💰 {info.get('balance', 0):.2f} RTC"
            
            if "hardware" in info:
                details += f" | {info.get('hardware', 'Unknown')}"
            
            # Update presence
            try:
                RPC.update(
                    details=details,
                    state=state,
                    large_image="rustchain_logo",
                    large_text=f"Epoch {info.get('epoch', 0)}",
                    start=time.time()
                )
                print(f"✅ Updated: {details} | {state}")
            except Exception as e:
                print(f"⚠️  Update failed: {e}")
        
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
