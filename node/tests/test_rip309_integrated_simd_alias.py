# SPDX-License-Identifier: MIT
import importlib.util
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"


def _load_module():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["RUSTCHAIN_DB_PATH"] = db_path
    os.environ.setdefault("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
    if str(NODE_DIR) not in sys.path:
        sys.path.insert(0, str(NODE_DIR))
    spec = importlib.util.spec_from_file_location(
        "rustchain_rip309_simd_alias_test",
        MODULE_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, db_path


def test_rip309_accepts_miner_simd_identity_for_simd_bias_rotation():
    mod, db_path = _load_module()
    try:
        fingerprint = {
            "checks": {
                "clock_drift": {"passed": True, "data": {"cv": 0.04}},
                "cache_timing": {"passed": True, "data": {"L1": 2.1, "L2": 8.4}},
                "simd_identity": {"passed": True, "data": {"simd_type": "neon"}},
                "thermal_drift": {"passed": True, "data": {"thermal_drift_pct": 2.0}},
                "instruction_jitter": {"passed": True, "data": {"cv": 0.03}},
                "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
            }
        }

        # FIX 2026-07-25 (rotation unification): the canonical active-check
        # name is now "simd_identity" (matching the miner payloads and the
        # settlement/reward path); "simd_bias" was the legacy RIP-309 issue
        # wording. The alias must keep working in BOTH directions.
        with sqlite3.connect(":memory:") as conn:
            rotation = mod.get_epoch_fingerprint_rotation(conn, 0)
            assert "simd_identity" in rotation["active_checks"]
            assert "simd_bias" not in rotation["active_checks"]
            result = mod.evaluate_rotating_fingerprint_checks(conn, 0, fingerprint)

        assert result["active_ratio"] == 1.0
        assert result["failed_active_checks"] == []
        assert result["active_results"]["simd_identity"] is True

        # Reverse alias: a payload keyed "simd_bias" (RIP-309 issue wording)
        # must still satisfy the canonical "simd_identity" active check.
        fingerprint_bias = {
            "checks": dict(
                fingerprint["checks"],
                simd_bias=fingerprint["checks"].pop("simd_identity"),
            )
        }
        with sqlite3.connect(":memory:") as conn:
            result_bias = mod.evaluate_rotating_fingerprint_checks(conn, 0, fingerprint_bias)
        assert result_bias["active_ratio"] == 1.0
        assert result_bias["active_results"]["simd_identity"] is True
    finally:
        os.unlink(db_path)
