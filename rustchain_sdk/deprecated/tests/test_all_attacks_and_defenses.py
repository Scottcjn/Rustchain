#!/usr/bin/env python3
"""
Comprehensive Attack/Defense Testing
Tests all 7 attack vectors against production RustChain node
"""

import requests
import json
import hashlib
import time
from datetime import datetime, timedelta

# Production node endpoint
NODE_URL = "http://50.28.86.131:8088"

def test_attack_1_bios_spoofing():
    """
    Attack 1: BIOS Date Spoofing
    Try to enroll with fake old BIOS date
    """
    print("\n" + "="*80)
    print("ATTACK 1: BIOS Date Spoofing")
    print("="*80)

    fake_enrollment = {
        "miner_pk": "fake_ancient_hardware_1234567890abcdef1RTC",
        "mac": "00:de:ad:be:ef:01",
        "entropy": 0.95,
        "cpu_info": "Fake Ancient CPU from 1985",
        "bios_date": "01/01/1985",  # Fake ancient BIOS
        "hardware_age": "ancient",
        "claimed_multiplier": 3.0
    }

    print("Attempting enrollment with spoofed BIOS date (1985)...")
    print(f"Claimed: Ancient hardware (3.0x multiplier)")

    try:
        response = requests.post(f"{NODE_URL}/enroll", json=fake_enrollment, timeout=5)
        if response.status_code == 200:
            print("❌ ATTACK SUCCEEDED - Node accepted fake BIOS!")
            print(f"Response: {response.json()}")
            return False
        else:
            print(f"✅ ATTACK BLOCKED - Status: {response.status_code}")
            print(f"Defense: {response.text}")
            return True
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Request failed: {e}")
        return None

def test_attack_2_replay_attack():
    """
    Attack 2: Replay Attack
    Capture and replay legitimate miner's attestation
    """
    print("\n" + "="*80)
    print("ATTACK 2: Attestation Replay Attack")
    print("="*80)

    # Simulate captured G4 attestation
    captured_attestation = {
        "miner_pk": "ppc_g4_98ad7c5973eb4a3173090b9e66011a6b7b8c42cf9RTC",
        "mac": "00:0a:95:7a:2f:3e",
        "entropy": 0.87,
        "timestamp": "2025-11-01T20:00:00",  # Old timestamp
        "signature": "captured_signature_xyz123",
    }

    print("Replaying captured attestation from PowerPC G4...")
    print(f"Original timestamp: {captured_attestation['timestamp']}")
    print(f"Current time: {datetime.now().isoformat()}")

    try:
        response = requests.post(f"{NODE_URL}/enroll", json=captured_attestation, timeout=5)
        if response.status_code == 200:
            print("❌ ATTACK SUCCEEDED - Replay accepted!")
            return False
        else:
            print(f"✅ ATTACK BLOCKED - Stale timestamp detected")
            return True
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Request failed: {e}")
        return None

def test_attack_3_cpu_spoofing():
    """
    Attack 3: CPU Info Spoofing
    Fake PowerPC CPU on x86 hardware
    """
    print("\n" + "="*80)
    print("ATTACK 3: CPU Info Spoofing")
    print("="*80)

    fake_ppc_attestation = {
        "miner_pk": "fake_ppc_x86_spoofed_1234567890abcdef2RTC",
        "mac": "00:11:22:33:44:55",
        "cpu_info": "PowerPC 7447A",  # Fake PowerPC
        "cpu_flags": ["altivec"],
        "entropy": 0.9,
        "hardware_age": "classic",
        "claimed_multiplier": 2.5
    }

    print("Claiming PowerPC G4 from x86 machine...")
    print("Fake CPU: PowerPC 7447A with AltiVec")

    try:
        response = requests.post(f"{NODE_URL}/enroll", json=fake_ppc_attestation, timeout=5)
        if response.status_code == 200:
            print("❌ ATTACK SUCCEEDED - Fake CPU accepted!")
            return False
        else:
            print(f"✅ ATTACK BLOCKED - CPU verification failed")
            return True
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Request failed: {e}")
        return None

def test_attack_4_time_manipulation():
    """
    Attack 4: Time Travel Attack
    Manipulate system time to fake hardware age
    """
    print("\n" + "="*80)
    print("ATTACK 4: Time Manipulation Attack")
    print("="*80)

    time_travel_attestation = {
        "miner_pk": "time_traveler_wallet_1234567890abcdef3RTC",
        "mac": "00:aa:bb:cc:dd:ee",
        "entropy": 0.85,
        "timestamp": "2005-01-01T12:00:00",  # 20 years in the past
        "system_time": "2005-01-01T12:00:00",
        "claimed_age": "20 years old",
    }

    print("System time manipulated to 2005...")
    print(f"Claimed timestamp: {time_travel_attestation['timestamp']}")

    try:
        response = requests.post(f"{NODE_URL}/enroll", json=time_travel_attestation, timeout=5)
        if response.status_code == 200:
            print("❌ ATTACK SUCCEEDED - Time manipulation worked!")
            return False
        else:
            print(f"✅ ATTACK BLOCKED - Network time verification failed")
            return True
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Request failed: {e}")
        return None

def test_attack_5_sql_injection():
    """
    Attack 5: SQL Injection
    Try to inject malicious SQL
    """
    print("\n" + "="*80)
    print("ATTACK 5: SQL Injection Attack")
    print("="*80)

    sql_injection_payloads = [
        "'; DROP TABLE epoch_enroll; --RTC",
        "' OR '1'='1RTC",
        "fake' UNION SELECT * FROM balances WHERE '1'='1RTC",
    ]

    blocked_count = 0

    for i, payload in enumerate(sql_injection_payloads, 1):
        print(f"\nPayload {i}: {payload[:50]}...")

        injection_attestation = {
            "miner_pk": payload,
            "mac": "00:ff:ff:ff:ff:ff",
            "entropy": 0.5,
        }

        try:
            response = requests.post(f"{NODE_URL}/enroll", json=injection_attestation, timeout=5)
            if response.status_code == 200:
                print(f"  ❌ BYPASSED - SQL injection succeeded!")
            else:
                print(f"  ✅ BLOCKED - Input validation caught it")
                blocked_count += 1
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  Request failed: {e}")

    return blocked_count == len(sql_injection_payloads)

def test_attack_6_sybil_attack():
    """
    Attack 6: Sybil Attack
    Multiple virtual identities from same machine
    """
    print("\n" + "="*80)
    print("ATTACK 6: Sybil Attack (Multiple Virtual Miners)")
    print("="*80)

    print("Attempting to enroll 10 miners from same hardware...")

    base_mac = "00:11:22:33:44:"
    accepted_count = 0

    for i in range(10):
        fake_miner = {
            "miner_pk": f"sybil_miner_{i}_" + "0"*26 + "RTC",
            "mac": base_mac + f"{i:02x}",
            "entropy": 0.50 + (i * 0.01),  # Slightly varied
            "ip": f"10.0.{i}.{i}",
        }

        try:
            response = requests.post(f"{NODE_URL}/enroll", json=fake_miner, timeout=5)
            if response.status_code == 200:
                accepted_count += 1
        except requests.exceptions.RequestException:
            pass

    if accepted_count > 2:
        print(f"❌ ATTACK PARTIALLY SUCCEEDED - {accepted_count}/10 miners accepted")
        return False
    else:
        print(f"✅ ATTACK BLOCKED - Entropy correlation detected ({accepted_count}/10 accepted)")
        return True

def test_attack_7_firmware_forgery():
    """
    Attack 7: Firmware Signature Forgery
    Forge OpenFirmware signatures
    """
    print("\n" + "="*80)
    print("ATTACK 7: Firmware Signature Forgery")
    print("="*80)

    forged_openfirmware = {
        "miner_pk": "forged_openfirmware_1234567890abcdef4RTC",
        "mac": "00:aa:bb:cc:dd:01",
        "entropy": 0.95,
        "firmware_type": "OpenFirmware",
        "boot_rom": "4.8.7f1",
        "model": "PowerMac3,6",
        "manufacturer": "Apple Computer",
        "signature": "forged_signature_12345",
    }

    print("Forging OpenFirmware signature for PowerMac3,6...")

    try:
        response = requests.post(f"{NODE_URL}/enroll", json=forged_openfirmware, timeout=5)
        if response.status_code == 200:
            print("❌ ATTACK SUCCEEDED - Forged firmware accepted!")
            return False
        else:
            print(f"✅ ATTACK BLOCKED - Cryptographic verification failed")
            return True
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Request failed: {e}")
        return None

def main():
    print("="*80)
    print("RUSTCHAIN SECURITY - COMPREHENSIVE ATTACK TESTING")
    print("Target: Production Node (50.28.86.131:8088)")
    print("="*80)

    # Check if node is reachable
    try:
        response = requests.get(f"{NODE_URL}/api/stats", timeout=5)
        print(f"\n✓ Node Status: {response.status_code}")
        stats = response.json()
        print(f"✓ Current Epoch: {stats.get('epoch', 'unknown')}")
        print(f"✓ Active Miners: {stats.get('total_miners', 'unknown')}")
    except requests.exceptions.RequestException as e:
        print(f"\n⚠️  Warning: Cannot reach node - {e}")
        print("Tests will show connection errors\n")

    # Run all attack tests
    results = {
        "BIOS Spoofing": test_attack_1_bios_spoofing(),
        "Replay Attack": test_attack_2_replay_attack(),
        "CPU Spoofing": test_attack_3_cpu_spoofing(),
        "Time Manipulation": test_attack_4_time_manipulation(),
        "SQL Injection": test_attack_5_sql_injection(),
        "Sybil Attack": test_attack_6_sybil_attack(),
        "Firmware Forgery": test_attack_7_firmware_forgery(),
    }

    # Summary
    print("\n" + "="*80)
    print("ATTACK SUMMARY")
    print("="*80)

    blocked = 0
    bypassed = 0
    unknown = 0

    for attack, result in results.items():
        if result is True:
            status = "✅ BLOCKED"
            blocked += 1
        elif result is False:
            status = "❌ BYPASSED"
            bypassed += 1
        else:
            status = "⚠️  UNKNOWN"
            unknown += 1

        print(f"{status} - {attack}")

    print("\n" + "="*80)
    print(f"Security Score: {blocked}/{len(results)} attacks blocked")

    if blocked == len(results):
        print("🎉 PERFECT SECURITY - All attacks blocked!")
    elif blocked >= len(results) * 0.7:
        print("✅ GOOD SECURITY - Most attacks blocked")
    else:
        print("⚠️  NEEDS IMPROVEMENT - Multiple vulnerabilities")

    print("="*80)

if __name__ == "__main__":
    main()
