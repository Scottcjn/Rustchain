#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
import requests
import json
import time
import sys

BASE_URL = "http://localhost:8099"
ADMIN_KEY = "rustchain_admin_key_2025_secure64"

def test_gpu_attest():
    print("[*] Testing GPU Attestation...")
    payload = {
        "miner_id": "test_gpu_node",
        "gpu_model": "RTX 4090",
        "vram_gb": 24,
        "cuda_version": "12.1",
        "supports_render": True,
        "supports_llm": True
    }
    resp = requests.post(f"{BASE_URL}/api/gpu/attest", json=payload)
    print(f"[+] Response: {resp.status_code} {resp.text}")

def test_gpu_escrow():
    print("[*] Testing GPU Escrow...")
    payload = {
        "job_type": "render",
        "from_wallet": "scott",
        "to_wallet": "test_gpu_node",
        "amount_rtc": 5.0
    }
    resp = requests.post(f"{BASE_URL}/api/gpu/escrow", json=payload)
    print(f"[+] Response: {resp.status_code} {resp.text}")
    if resp.status_code == 200:
        return resp.json().get("job_id")
    return None

def test_gpu_release(job_id):
    print(f"[*] Testing GPU Release for {job_id}...")
    payload = {"job_id": job_id}
    resp = requests.post(f"{BASE_URL}/api/gpu/release", json=payload)
    print(f"[+] Response: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
        
    test_gpu_attest()
    job_id = test_gpu_escrow()
    if job_id:
        test_gpu_release(job_id)
