#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
from __future__ import annotations

import os
import sys
from typing import Any, Optional, Tuple

import requests

BASE_URL: str = os.getenv("GPU_RENDER_BASE_URL", "https://localhost:8099")
# Keep compatibility with local self-signed TLS / non-TLS test setups.
VERIFY_TLS: bool = os.getenv("GPU_RENDER_VERIFY_TLS", "0") == "1"


def _post(path: str, payload: dict[str, Any]) -> requests.Response:
    """Send POST request to GPU render API endpoint.
    
    Args:
        path: API endpoint path (e.g., "/api/gpu/attest")
        payload: JSON payload to send
        
    Returns:
        requests.Response object from the API call
    """
    return requests.post(
        f"{BASE_URL}{path}",
        json=payload,
        timeout=10,
        verify=VERIFY_TLS,
    )


def test_gpu_attest() -> None:
    """Test GPU attestation endpoint with sample data."""
    print("[*] Testing GPU Attestation...")
    payload: dict[str, Any] = {
        "miner_id": "test_gpu_node",
        "gpu_model": "RTX 4090",
        "vram_gb": 24,
        "cuda_version": "12.1",
        "supports_render": True,
        "supports_llm": True,
    }
    resp: requests.Response = _post("/api/gpu/attest", payload)
    print(f"[+] Response: {resp.status_code} {resp.text}")


def test_gpu_escrow() -> Tuple[Optional[str], Optional[str]]:
    """Test GPU escrow endpoint and return job credentials.
    
    Returns:
        Tuple of (job_id, escrow_secret) if successful, (None, None) otherwise
    """
    print("[*] Testing GPU Escrow...")
    payload: dict[str, Any] = {
        "job_type": "render",
        "from_wallet": "scott",
        "to_wallet": "test_gpu_node",
        "amount_rtc": 5.0,
    }
    resp: requests.Response = _post("/api/gpu/escrow", payload)
    print(f"[+] Response: {resp.status_code} {resp.text}")
    if resp.status_code == 200:
        body: dict[str, Any] = resp.json()
        return body.get("job_id"), body.get("escrow_secret")
    return None, None


def test_gpu_release(job_id: str, escrow_secret: str) -> None:
    """Test GPU release endpoint to finalize a job.
    
    Args:
        job_id: Job identifier from escrow creation
        escrow_secret: Secret key from escrow creation
    """
    print(f"[*] Testing GPU Release for {job_id}...")
    payload: dict[str, Any] = {
        "job_id": job_id,
        "actor_wallet": "scott",
        "escrow_secret": escrow_secret,
    }
    resp: requests.Response = _post("/api/gpu/release", payload)
    print(f"[+] Response: {resp.status_code} {resp.text}")


def main() -> None:
    """Main entry point for GPU render test script."""
    global BASE_URL
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]

    test_gpu_attest()
    job_id, escrow_secret = test_gpu_escrow()
    if job_id and escrow_secret:
        test_gpu_release(job_id, escrow_secret)


if __name__ == "__main__":
    main()
