import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "node" / "gpu_attestation.py"


def load_gpu_attestation():
    spec = importlib.util.spec_from_file_location("gpu_attestation_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_validate_gpu_fingerprint_accepts_consistent_h100_sxm_payload():
    module = load_gpu_attestation()

    ok, reason = module.validate_gpu_fingerprint(
        {
            "gpu_name": "NVIDIA H100 SXM5",
            "vram_mb": 81920,
            "compute_capability": "9.0",
            "channels": [
                {"name": "8c: Warp Jitter", "data": {"cv": 0.02}},
            ],
        }
    )

    assert ok is True
    assert reason == "valid"


def test_validate_gpu_fingerprint_rejects_h100_identity_mismatch():
    module = load_gpu_attestation()

    ok, reason = module.validate_gpu_fingerprint(
        {
            "gpu_name": "NVIDIA H100 SXM5",
            "vram_mb": 40960,
            "compute_capability": "8.0",
            "channels": [],
        }
    )

    assert ok is False
    assert reason == "identity_mismatch: H100 SXM requires sm_9.0 and 80GB VRAM"


def test_validate_gpu_fingerprint_rejects_synthetic_or_noisy_warp_jitter():
    module = load_gpu_attestation()

    low_ok, low_reason = module.validate_gpu_fingerprint(
        {
            "gpu_name": "generic gpu",
            "channels": [{"name": "8c: Warp Jitter", "data": {"cv": 0.0}}],
        }
    )
    high_ok, high_reason = module.validate_gpu_fingerprint(
        {
            "gpu_name": "generic gpu",
            "channels": [{"name": "8c: Warp Jitter", "data": {"cv": 0.81}}],
        }
    )

    assert low_ok is False
    assert low_reason.startswith("synthetic_timing:")
    assert high_ok is False
    assert high_reason.startswith("high_latency_noise:")


def test_validate_gpu_fingerprint_checks_rtx_tensor_and_igpu_fabric_signals():
    module = load_gpu_attestation()

    tensor_ok, tensor_reason = module.validate_gpu_fingerprint(
        {
            "gpu_name": "RTX 4090",
            "channels": [
                {
                    "name": "8b: Compute Asymmetry",
                    "data": {"asymmetry_ratios": {"fp16_to_fp32": 1.0}},
                }
            ],
        }
    )
    fabric_ok, fabric_reason = module.validate_gpu_fingerprint(
        {
            "gpu_name": "integrated gpu",
            "channels": [
                {
                    "name": "8i: iGPU Coherence",
                    "data": {"fabric_ratio": 51},
                }
            ],
        }
    )

    assert tensor_ok is False
    assert tensor_reason == "alu_mismatch: Tensor core throughput not detected"
    assert fabric_ok is False
    assert fabric_reason == "fabric_latency_too_high: Likely discrete GPU masquerading as iGPU"


def test_get_gpu_attestation_payload_appends_tensor_core_channel(monkeypatch):
    module = load_gpu_attestation()

    class FakeFingerprint:
        compute_capability = "8.9"

        def to_dict(self):
            return {"channels": [{"name": "8c: Warp Jitter", "data": {"cv": 0.03}}]}

    def fake_run_gpu_fingerprint(device_index=0):
        assert device_index == 2
        return FakeFingerprint()

    def fake_run_tensor_core_fingerprint(device_index=0):
        assert device_index == 2
        return SimpleNamespace(all_passed=True, precision_hash="hash-123")

    miners_module = ModuleType("miners")
    gpu_module = ModuleType("miners.gpu_fingerprint")
    tensor_module = ModuleType("miners.tensor_core_fingerprint")
    gpu_module.run_gpu_fingerprint = fake_run_gpu_fingerprint
    tensor_module.run_tensor_core_fingerprint = fake_run_tensor_core_fingerprint

    monkeypatch.setitem(sys.modules, "torch", ModuleType("torch"))
    monkeypatch.setitem(sys.modules, "miners", miners_module)
    monkeypatch.setitem(sys.modules, "miners.gpu_fingerprint", gpu_module)
    monkeypatch.setitem(sys.modules, "miners.tensor_core_fingerprint", tensor_module)

    payload = module.get_gpu_attestation_payload(device_index=2)

    assert payload["channels"][-1] == {
        "name": "8f: Tensor Core Precision Drift",
        "passed": True,
        "data": {
            "precision_hash": "hash-123",
            "lsb_signature": "hash-123",
        },
    }
