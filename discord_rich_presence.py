#!/usr/bin/env python3
"""
RustChain Discord Rich Presence

Shows mining status in Discord profile:
- Current hashrate/attestations
- RTC earned today
- Miner uptime
- Hardware type (G4/G5/POWER8/etc)

Usage:
    python3 discord_rich_presence.py --miner-id YOUR_MINER_ID [--client-id DISCORD_CLIENT_ID]

Requirements:
    pip install pypresence requests
"""

import os
import sys
import time
import json
from typing import Any, Dict, List, Optional

import requests
from datetime import datetime, timedelta
from pypresence import Presence

# RustChain API endpoint (self-signed cert requires verification=False)
RUSTCHAIN_API: str = "https://rustchain.org"

# Local state file for tracking earnings
STATE_FILE: str = os.path.expanduser("~/.rustchain_discord_state.json")

# Default update interval (seconds)
UPDATE_INTERVAL: int = 60


def load_state() -> Dict[str, Any]:
    """Load previous state from file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)  # type: ignore[no-any-return]
        except Exception:
            pass
    return {}


def save_state(state: Dict[str, Any]) -> None:
    """Save current state to file."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def get_miner_info(miner_id: str) -> Optional[Dict[str, Any]]:
    """Get miner information from RustChain API."""
    try:
        response = requests.get(
            f"{RUSTCHAIN_API}/wallet/balance",
            params={"miner_id": miner_id},
            verify=False,  # Self-signed cert
            timeout=10
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]
    except Exception as e:
        print(f"Error getting balance: {e}")
        return None


def get_miners_list() -> List[Dict[str, Any]]:
    """Get list of all active miners."""
    try:
        response = requests.get(
            f"{RUSTCHAIN_API}/api/miners",
            verify=False,
            timeout=10
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]
    except Exception as e:
        print(f"Error getting miners list: {e}")
        return []


def get_epoch_info() -> Optional[Dict[str, Any]]:
    """Get current epoch information."""
    try:
        response = requests.get(
            f"{RUSTCHAIN_API}/epoch",
            verify=False,
            timeout=10
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]
    except Exception as e:
        print(f"Error getting epoch info: {e}")
        return None


def get_node_health() -> Optional[Dict[str, Any]]:
    """Get node health information."""
    try:
        response = requests.get(
            f"{RUSTCHAIN_API}/health",
            verify=False,
            timeout=10
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]
    except Exception as e:
        print(f"Error getting health: {e}")
        return None


def calculate_rtc_earned_today(current_balance: float, state: Dict[str, Any]) -> float:
    """Calculate RTC earned since last state update."""
    if not state:
        return 0.0

    previous_balance = state.get('last_balance', 0.0)
    earned = current_balance - previous_balance

    # Don't show negative earnings (withdrawals)
    return max(0.0, earned)


def calculate_miner_uptime(last_attest_timestamp: Optional[float], state: Dict[str, Any]) -> str:
    """Calculate miner uptime based on last attestation."""
    if not last_attest_timestamp:
        return "Unknown"

    last_attest = datetime.fromtimestamp(last_attest_timestamp)
    now = datetime.now()

    # Time since last attestation
    time_since = now - last_attest

    # If last attestation was recent (within 2 epochs), consider online
    if time_since < timedelta(hours=2):
        return "Online"
    elif time_since < timedelta(hours=24):
        return f"{int(time_since.total_seconds() // 3600)}h ago"
    else:
        return "Offline"


def get_hardware_display(hardware_type: str) -> str:
    """Get a short display string for hardware type."""
    if "G4" in hardware_type:
        return "🍎 PowerPC G4"
    elif "G5" in hardware_type:
        return "🍎 PowerPC G5"
    elif "POWER8" in hardware_type:
        return "⚡ POWER8"
    elif "x86_64" in hardware_type:
        return "💻 Modern PC"
    elif "M1" in hardware_type or "M2" in hardware_type:
        return "🍎 Apple Silicon"
    else:
        return "💻 " + hardware_type.split()[0]


def format_presence_data(
    miner_data: Dict[str, Any],
    balance_data: Optional[Dict[str, Any]],
    epoch_data: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Format data for Discord Rich Presence."""
    hardware_type = miner_data.get('hardware_type', 'Unknown')
    antiquity_multiplier = miner_data.get('antiquity_multiplier', 1.0)
    last_attest = miner_data.get('last_attest', 0)

    # Current balance
    balance = balance_data.get('amount_rtc', 0.0) if balance_data else 0.0

    # Hardware icon and short name
    hw_display = get_hardware_display(hardware_type)

    # Multiplier badge
    multiplier_badge = f"{antiquity_multiplier}x"

    # Uptime status
    uptime = calculate_miner_uptime(last_attest, {})

    # Epoch info
    epoch_num = epoch_data.get('epoch', 0) if epoch_data else 0
    slot = epoch_data.get('slot', 0) if epoch_data else 0
    epoch_progress = f"E{epoch_num} · S{slot}"

    # Discord state (top line)
    state_text = f"{hw_display} {multiplier_badge} · {uptime}"

    # Discord details (bottom line)
    details_text = f"Balance: {balance:.2f} RTC"

    # Large image text
    large_text = f"{hardware_type} ({antiquity_multiplier}x reward)"

    # Small image text
    small_text = epoch_progress

    return {
        'state': state_text,
        'details': details_text,
        'large_text': large_text,
        'small_text': small_text,
        'balance': balance,
        'uptime': uptime
    }

def main() -> None:
    """Main loop for Discord Rich Presence."""
    import argparse

    parser = argparse.ArgumentParser(description='RustChain Discord Rich Presence')
    parser.add_argument('--miner-id', required=True, help='Your miner ID (wallet address)')
    parser.add_argument('--client-id', help='Discord application client ID (optional)')
    parser.add_argument('--interval', type=int, default=UPDATE_INTERVAL, help='Update interval in seconds')
    args = parser.parse_args()

    miner_id: str = args.miner_id
    client_id: Optional[str] = args.client_id

    print(f"🍎 RustChain Discord Rich Presence")
    print(f"Miner ID: {miner_id}")
    print(f"Update interval: {args.interval}s")
    print()

    # If no client_id provided, use default RustChain app ID (placeholder)
    # In production, create your own Discord app at https://discord.com/developers/applications
    if not client_id:
        print("⚠️  No --client-id provided.")
        print("Create a Discord app at https://discord.com/developers/applications")
        print("Enable Rich Presence and use your Application ID as --client-id")
        print("Continuing without Discord connection (data only)...\n")
        client_id = None

    # Initialize Discord Presence
    rpc: Optional[Presence] = None
    if client_id:
        try:
            rpc = Presence(client_id)
            rpc.connect()
            print(f"✅ Connected to Discord Rich Presence")
        except Exception as e:
            print(f"⚠️  Failed to connect to Discord: {e}")
            print("Continuing without Discord connection...\n")
            rpc = None

    # Load previous state
    state: Dict[str, Any] = load_state()

    # Main loop
    try:
        while True:
            # Get miner info from list to find hardware type
            miners_list = get_miners_list()
            miner_data: Optional[Dict[str, Any]] = None
            for m in miners_list:
                if m.get('miner') == miner_id:
                    miner_data = m
                    break

            if not miner_data:
                print(f"⚠️  Miner {miner_id} not found in active miners list")
                print("Make sure your miner is running and enrolled.\n")

                # Show basic data if available
                balance_data = get_miner_info(miner_id)
                if balance_data:
                    print(f"Balance: {balance_data.get('amount_rtc', 0):.2f} RTC")

                time.sleep(args.interval)
                continue

            # Get balance
            balance_data = get_miner_info(miner_id)

            # Get epoch info
            epoch_data = get_epoch_info()

            # Get node health
            health_data = get_node_health()

            # Calculate earnings today
            if balance_data:
                balance = balance_data.get('amount_rtc', 0.0)
                earned_today = calculate_rtc_earned_today(balance, state)

                # Save current balance
                state['last_balance'] = balance
                state['last_update'] = datetime.now().isoformat()
                save_state(state)
            else:
                balance = 0.0
                earned_today = 0.0

            # Format data for Discord
            presence_data = format_presence_data(miner_data, balance_data, epoch_data)

            # Print status
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {presence_data['state']}")
            print(f"    {presence_data['details']}")
            if earned_today > 0:
                print(f"    +{earned_today:.4f} RTC today")
            if health_data:
                print(f"    Node: {health_data.get('version', 'Unknown')} (uptime: {health_data.get('uptime_s', 0) // 3600}h)")
            print()

            # Update Discord presence
            if rpc:
                try:
                    rpc.update(
                        state=presence_data['state'],
                        details=presence_data['details'],
                        large_image="rustchain",
                        large_text=presence_data['large_text'],
                        small_image="epoch",
                        small_text=presence_data['small_text'],
                        start=int(time.time())
                    )
                except Exception as e:
                    print(f"⚠️  Discord update failed: {e}")
                    # Try to reconnect
                    try:
                        rpc.connect()
                    except Exception:
                        pass

            # Wait for next update
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n👋 Shutting down RustChain Discord Rich Presence")
        if rpc:
            rpc.close()
        sys.exit(0)

if __name__ == '__main__':
    main()
