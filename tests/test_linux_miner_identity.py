# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MINER_PATH = REPO_ROOT / "miners" / "linux" / "rustchain_linux_miner.py"


def load_miner_module():
    spec = importlib.util.spec_from_file_location("linux_miner_under_test", MINER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_miner_id_uses_detected_arch_and_hostname():
    miner = load_miner_module()

    miner_id = miner._miner_id_from_hw(
        {
            "arch": "aarch64",
            "hostname": "Lab ARM Box",
        }
    )

    assert miner_id == "aarch64-lab-arm-box"
    assert "ryzen" not in miner_id


def test_linux_miner_adds_binding_aliases_to_fingerprint():
    miner = load_miner_module()
    from node.hardware_binding_v2 import extract_entropy_profile

    fingerprint = {
        "checks": {
            "cache_timing": {
                "passed": True,
                "data": {"l1_ns": 4.2, "l2_ns": 8.4, "l3_ns": 22.0},
            },
            "thermal_drift": {
                "passed": True,
                "data": {"drift_ratio": 1.034},
            },
            "instruction_jitter": {
                "passed": True,
                "data": {
                    "int_avg_ns": 1000,
                    "int_stdev": 50,
                    "fp_avg_ns": 2000,
                    "fp_stdev": 160,
                    "branch_avg_ns": 1500,
                    "branch_stdev": 90,
                },
            },
        }
    }

    normalized = miner._normalize_fingerprint_for_binding(fingerprint)

    cache = normalized["checks"]["cache_timing"]["data"]
    thermal = normalized["checks"]["thermal_drift"]["data"]
    jitter = normalized["checks"]["instruction_jitter"]["data"]

    assert cache["L1"] == 4.2
    assert cache["L2"] == 8.4
    assert thermal["ratio"] == 1.034
    assert jitter["cv"] > 0
    assert "l1_ns" in cache
    assert "drift_ratio" in thermal

    profile = extract_entropy_profile(normalized)
    assert profile["cache_l1"] == 4.2
    assert profile["cache_l2"] == 8.4
    assert profile["thermal_ratio"] == 1.034
    assert profile["jitter_cv"] > 0


def test_linux_miner_source_does_not_hardcode_victus_identity():
    source = MINER_PATH.read_text(encoding="utf-8")

    assert "HP Victus" not in source
    assert "ryzen5-" not in source
    assert "RustChain Local Linux Miner" in source
