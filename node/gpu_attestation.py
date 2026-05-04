import hashlib
import json
import os
import subprocess
from typing import Dict, Tuple

def validate_gpu_fingerprint(fingerprint_data: Dict) -> Tuple[bool, str]:
    """
    Server-side validation of GPU fingerprint data (RIP-0308).
    
    Checks for:
    1. Silicon identity consistency (Compute Capability vs VRAM vs Arch)
    2. Physical property variance (Jitter, Thermal Ramp, Latency Spread)
    3. Cross-channel correlation (Fabric ratio for iGPUs)
    """
    try:
        # 1. Identity Consistency Check
        gpu_name = fingerprint_data.get("gpu_name", "").lower()
        vram = fingerprint_data.get("vram_mb", 0)
        cap = fingerprint_data.get("compute_capability", "0.0")
        
        # known H100 SXM5 signature
        if "h100" in gpu_name and "sxm" in gpu_name:
            if cap != "9.0" or vram < 80000:
                return False, "identity_mismatch: H100 SXM requires sm_9.0 and 80GB VRAM"
        
        # 2. Channel 8c: Warp Jitter (Scheduling Variance)
        # Real hardware has jitter (CV > 0.005). Perfect 0 is a sign of emulation.
        ch8c = next((ch for ch in fingerprint_data.get("channels", []) if "8c" in ch["name"]), None)
        if ch8c:
            cv = ch8c.get("data", {}).get("cv", 0)
            if cv < 0.005:
                return False, "synthetic_timing: Warp jitter too low (likely emulated)"
            if cv > 0.8:
                return False, "high_latency_noise: Warp jitter too high (likely high-overhead VM)"

        # 3. Channel 8b: Compute Asymmetry (FP16:FP32 Ratio)
        # Physical ALU layout determines this ratio. It's generation-specific.
        ch8b = next((ch for ch in fingerprint_data.get("channels", []) if "8b" in ch["name"]), None)
        if ch8b:
            ratios = ch8b.get("data", {}).get("asymmetry_ratios", {})
            fp16_ratio = ratios.get("fp16_to_fp32", 0)
            # Ampere/Ada Tensor Core ratio is typically > 2.0
            if "rtx" in gpu_name and fp16_ratio < 1.1:
                 return False, "alu_mismatch: Tensor core throughput not detected"

        # 4. Channel 8i: iGPU Coherence (if applicable)
        ch8i = next((ch for ch in fingerprint_data.get("channels", []) if "8i" in ch["name"]), None)
        if ch8i:
            fabric_ratio = ch8i.get("data", {}).get("fabric_ratio", 0)
            # iGPUs have low fabric ratio (shared bus). dGPUs over PCIe would be much higher.
            if fabric_ratio > 50:
                return False, "fabric_latency_too_high: Likely discrete GPU masquerading as iGPU"

        return True, "valid"
    except Exception as e:
        return False, "validation_error"

def get_gpu_attestation_payload(device_index=0) -> Dict:
    """
    Run appropriate GPU fingerprinting and return the structured payload.
    """
    import torch
    from miners.gpu_fingerprint import run_gpu_fingerprint
    from miners.tensor_core_fingerprint import run_tensor_core_fingerprint
    
    # Run main multi-channel fingerprint
    fp = run_gpu_fingerprint(device_index=device_index)
    payload = fp.to_dict()
    
    # Add Channel 8f (Tensor Core LSB Signature) for deep silicon identity
    try:
        if fp.compute_capability >= "7.0":
            tc_fp = run_tensor_core_fingerprint(device_index=device_index)
            payload["channels"].append({
                "name": "8f: Tensor Core Precision Drift",
                "passed": tc_fp.all_passed,
                "data": {
                    "precision_hash": tc_fp.precision_hash,
                    "lsb_signature": tc_fp.precision_hash # Use LSB composite
                }
            })
    except Exception:
        pass
        
    return payload
