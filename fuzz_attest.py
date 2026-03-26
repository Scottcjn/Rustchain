
import requests
import json
import random
import string
import time

# Configuration
TARGET_URL = "http://localhost:8080/attest/submit" # Default local, change to testnet if authorized

def generate_random_string(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def fuzz_payloads():
    payloads = [
        # 1. Empty Payload
        {},
        # 2. Missing Fields
        {"device_id": "123"},
        # 3. Invalid Types
        {"device_id": 123, "proof": 456},
        # 4. Large Payload (Buffer Overflow attempt)
        {"device_id": "A" * 10000, "proof": "B" * 10000},
        # 5. SQL Injection Attempt
        {"device_id": "' OR 1=1 --", "proof": "valid"},
        # 6. XSS Attempt
        {"device_id": "<script>alert(1)</script>", "proof": "valid"},
        # 7. JSON Injection
        {"device_id": "valid", "proof": "valid", "extra_field": "should_be_ignored"}
    ]
    return payloads

def run_fuzzer():
    print(f"🔥 Starting Fuzzer against {TARGET_URL}...")
    payloads = fuzz_payloads()

    for i, payload in enumerate(payloads):
        print(f"   Testing payload {i+1}/{len(payloads)}...")
        try:
            # We assume authorized testing context
            resp = requests.post(TARGET_URL, json=payload, timeout=2)
            print(f"   Status: {resp.status_code}")
            if resp.status_code == 500:
                print("   🚨 POTENTIAL CRASH DETECTED (500 Error)")
        except requests.exceptions.ConnectionError:
            print("   ⚠️ Connection refused (Target might be down or unreachable)")
        except Exception as e:
            print(f"   Error: {e}")

        time.sleep(0.1)

if __name__ == "__main__":
    print("Darwin Security Fuzzer v0.1")
    run_fuzzer()
