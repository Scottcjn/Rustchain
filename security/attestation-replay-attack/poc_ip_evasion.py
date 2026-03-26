#!/usr/bin/env python3
"""
Proof of Concept: IP-Based Hardware Binding Evasion

Demonstrates that _compute_hardware_id() includes source_ip as a primary
component, meaning the same physical hardware appears as different machines
when attesting from different IP addresses (e.g., via VPN or proxy).

Bounty: rustchain-bounties#2296 (200 RTC)
"""

import hashlib


def compute_hardware_id(device: dict, signals: dict = None, source_ip: str = None) -> str:
    """
    Replicated from node/rustchain_v2_integrated_v2.2.1_rip200.py line ~2470.
    Shows how IP changes create different hardware IDs for same hardware.
    """
    signals = signals or {}
    model = device.get('device_model', 'unknown')
    arch = device.get('device_arch', 'modern')
    family = device.get('device_family', 'unknown')
    cores = str(device.get('cores', 1))
    cpu_serial = device.get('cpu_serial', '')
    ip_component = source_ip or 'unknown_ip'
    macs = signals.get('macs', [])
    mac_str = ','.join(sorted(macs)) if macs else ''

    hw_fields = [ip_component, model, arch, family, cores, mac_str, cpu_serial]
    hw_id = hashlib.sha256('|'.join(str(f) for f in hw_fields).encode()).hexdigest()[:32]
    return hw_id


def demonstrate_ip_evasion():
    """Show that same hardware gets different IDs from different IPs."""
    device = {
        "device_arch": "g4",
        "device_family": "PowerBook",
        "device_model": "PowerBook5,8",
        "cores": 1,
        "cpu_serial": "XB435TREAL"
    }
    signals = {
        "macs": ["00:11:22:33:44:55"],
    }

    # Same hardware, different IPs (VPN/proxy)
    ips = [
        "50.28.86.100",    # Direct connection to Node 1
        "185.220.101.42",  # VPN endpoint for Node 2
        "104.244.76.13",   # Tor exit node for Node 3
    ]

    print("=" * 60)
    print("IP-Based Hardware Binding Evasion — PoC")
    print("=" * 60)
    print(f"\nHardware: {device['device_model']} ({device['device_arch']})")
    print(f"CPU Serial: {device['cpu_serial']}")
    print(f"MACs: {signals['macs']}")
    print(f"\nSame hardware, different source IPs:\n")

    hw_ids = []
    for ip in ips:
        hw_id = compute_hardware_id(device, signals, source_ip=ip)
        hw_ids.append(hw_id)
        print(f"  IP: {ip:20s} → hw_id: {hw_id}")

    # Verify all IDs are different
    unique_ids = len(set(hw_ids))
    print(f"\n  Unique hardware IDs: {unique_ids}/{len(hw_ids)}")
    print(f"  All different: {'YES ⚠️  VULNERABLE' if unique_ids == len(hw_ids) else 'NO (safe)'}")

    # Explain
    print(f"\n[Analysis]")
    print(f"  The hardware_id hash includes source_ip as PRIMARY component.")
    print(f"  This means:")
    print(f"  - VPN hop → different hardware_id → new binding allowed")
    print(f"  - Proxy chain → different hardware_id → new binding allowed")
    print(f"  - Tor exit node → different hardware_id → new binding allowed")
    print(f"")
    print(f"  Code reference: _compute_hardware_id() in")
    print(f"  node/rustchain_v2_integrated_v2.2.1_rip200.py, line ~2478:")
    print(f"    ip_component = source_ip or 'unknown_ip'")
    print(f"    hw_fields = [ip_component, model, arch, family, cores, mac_str, cpu_serial]")

    # Without IP (what the fix should look like)
    print(f"\n[Fixed version — IP excluded]:")
    for ip in ips:
        fixed_id = compute_hardware_id(device, signals, source_ip=None)
        print(f"  IP: {ip:20s} → hw_id: {fixed_id}  (same!)")

    return unique_ids == len(hw_ids)


if __name__ == "__main__":
    demonstrate_ip_evasion()
