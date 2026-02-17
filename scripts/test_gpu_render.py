#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
import os
import sys

import requests

BASE_URL = os.getenv("GPU_RENDER_BASE_URL", "https://localhost:8099")
# Keep compatibility with local self-signed TLS / non-TLS test setups.
VERIFY_TLS = os.getenv("GPU_RENDER_VERIFY_TLS", "0") == "1"


def _post(path, payload):
    return requests.post(
        f"{BASE_URL}{path}",
        json=payload,
        timeout=10,
        verify=VERIFY_TLS,
    )


def test_gpu_attest():
    print("[*] Testing GPU Attestation...")
    payload = {
        "miner_id": "test_gpu_node",
        "gpu_model": "RTX 4090",
        "vram_gb": 24,
        "cuda_version": "12.1",
        "supports_render": True,
        "supports_llm": True,
    }
    resp = _post("/api/gpu/attest", payload)
    print(f"[+] Response: {resp.status_code} {resp.text}")


def test_gpu_escrow():
    print("[*] Testing GPU Escrow...")
    payload = {
        "job_type": "render",
        "from_wallet": "scott",
        "to_wallet": "test_gpu_node",
        "amount_rtc": 5.0,
    }
    resp = _post("/api/gpu/escrow", payload)
    print(f"[+] Response: {resp.status_code} {resp.text}")
    if resp.status_code == 200:
        body = resp.json()
        return body.get("job_id"), body.get("escrow_secret")
    return None, None


def test_gpu_release(job_id, escrow_secret):
    print(f"[*] Testing GPU Release for {job_id}...")
    payload = {
        "job_id": job_id,
        "actor_wallet": "scott",
        "escrow_secret": escrow_secret,
    }
    resp = _post("/api/gpu/release", payload)
    print(f"[+] Response: {resp.status_code} {resp.text}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]

    test_gpu_attest()
    job_id, escrow_secret = test_gpu_escrow()
    if job_id and escrow_secret:
        test_gpu_release(job_id, escrow_secret)
