#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Example: AI Agent Booking a Relic Machine

Demonstrates how an AI agent can book vintage compute
using the Relic Market SDK.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from relic_market_sdk import RelicMarketClient, RelicComputeSession
import hashlib
import time


def main():
    # Configuration
    API_URL = "http://localhost:5000"
    AGENT_ID = "example-ai-agent-001"
    
    print("=" * 60)
    print("Rent-a-Relic Market - Agent Booking Example")
    print("=" * 60)
    
    # Initialize client
    client = RelicMarketClient(base_url=API_URL)
    
    # Check API health
    print("\n1. Checking API health...")
    health = client.health_check()
    print(f"   Status: {'OK' if health.get('ok') else 'ERROR'}")
    print(f"   Machines registered: {health.get('machines_registered', 0)}")
    
    # List available machines
    print("\n2. Available Machines:")
    print("-" * 60)
    machines = client.list_machines()
    
    for i, machine in enumerate(machines, 1):
        print(f"\n   [{i}] {machine['name']}")
        print(f"       Architecture: {machine['architecture']}")
        print(f"       CPU: {machine['cpu_model']} @ {machine['cpu_speed_ghz']}GHz")
        print(f"       RAM: {machine['ram_gb']}GB")
        print(f"       Rate: {machine['hourly_rate_rtc']} RTC/hour")
    
    # Select machine (POWER8 for this example)
    selected_machine = machines[0]  # POWER8 Beast
    print(f"\n3. Selected: {selected_machine['name']}")
    
    # Book the machine
    print("\n4. Booking machine...")
    session = RelicComputeSession(client, AGENT_ID)
    
    success, error = session.book(
        machine_id=selected_machine['machine_id'],
        duration_hours=1,
        payment_rtc=selected_machine['hourly_rate_rtc']
    )
    
    if not success:
        print(f"   ERROR: {error}")
        return 1
    
    print(f"   Reservation ID: {session.reservation['reservation_id']}")
    print(f"   Cost: {session.reservation['total_cost_rtc']} RTC")
    print(f"   Escrow TX: {session.reservation['escrow_tx_hash'][:16]}...")
    
    # Start session
    print("\n5. Starting session...")
    success, access, error = session.start()
    
    if not success:
        print(f"   ERROR: {error}")
        return 1
    
    print(f"   Status: ACTIVE")
    print(f"   SSH Host: {access['ssh']['host']}")
    print(f"   SSH Port: {access['ssh']['port']}")
    print(f"   SSH User: {access['ssh']['username']}")
    print(f"   API Key: {access['api_key'][:16]}...")
    print(f"   Expires: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session.reservation['end_time']))}")
    
    # Simulate compute work
    print("\n6. Running compute workload...")
    print("   (Simulating LLM inference on POWER8)")
    time.sleep(1)
    
    # Generate fake compute output
    compute_output = b"LLM inference result from POWER8 - tokens generated: 1000"
    compute_hash = hashlib.sha256(compute_output).hexdigest()
    print(f"   Compute hash: {compute_hash[:16]}...")
    
    # Complete session
    print("\n7. Completing session...")
    hardware_attestation = {
        "cpu_type": selected_machine['architecture'],
        "cpu_model": selected_machine['cpu_model'],
        "verified": True,
        "timestamp": time.time()
    }
    
    success, receipt, error = session.complete(compute_output, hardware_attestation)
    
    if not success:
        print(f"   ERROR: {error}")
        return 1
    
    print(f"   Receipt ID: {receipt['receipt_id']}")
    print(f"   Duration: {receipt['duration_seconds']} seconds")
    print(f"   Signature: {receipt['signature'][:32]}...")
    print(f"   Signature Algorithm: {receipt['signature_algorithm']}")
    
    # Verify receipt
    print("\n8. Verifying receipt...")
    receipt_data = client.get_receipt(session.reservation['reservation_id'])
    
    if receipt_data:
        print(f"   Signature Valid: {receipt_data.get('signature_valid', False)}")
        print(f"   Machine Passport: {receipt_data['receipt']['machine_passport_id']}")
    
    # Get BoTTube badge (if applicable)
    print("\n9. BoTTube Badge:")
    badge = client.get_botube_badge(session.reservation['reservation_id'])
    if badge:
        print(f"   Badge Type: {badge.get('badge_type', 'N/A')}")
        print(f"   Machine: {badge.get('machine_name', 'N/A')}")
        print(f"   Architecture: {badge.get('machine_architecture', 'N/A')}")
    
    # Show leaderboard
    print("\n10. Current Leaderboard:")
    leaderboard = client.get_leaderboard(limit=5)
    for i, entry in enumerate(leaderboard, 1):
        print(f"    #{i} {entry['name']}: {entry['total_reservations']} rentals")
    
    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
