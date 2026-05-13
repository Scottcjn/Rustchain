import importlib.util
import os
import sys
# SPDX-License-Identifier: MIT

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import mock_open, patch


ROOT = Path(__file__).resolve().parents[1]
NODE_DIR = ROOT / "node"
INTEGRATED_MODULE = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"

if str(NODE_DIR) not in sys.path:
    sys.path.insert(0, str(NODE_DIR))


def _load_integrated_module(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "0" * 32)
    spec = importlib.util.spec_from_file_location(
        "rustchain_integrated_current_year_test",
        INTEGRATED_MODULE,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_integrated_hall_score_uses_current_utc_year(monkeypatch):
    integrated = _load_integrated_module(monkeypatch)
    monkeypatch.setattr(integrated.time, "gmtime", lambda: SimpleNamespace(tm_year=2026))

    score = integrated.calculate_rust_score_inline(
        mfg_year=2001,
        arch="modern",
        attestations=0,
        machine_id=999,
    )

    assert score == 250


def test_hardware_fingerprint_age_oracle_uses_current_utc_year(monkeypatch):
    import hardware_fingerprint

    monkeypatch.setattr(hardware_fingerprint.time, "gmtime", lambda: SimpleNamespace(tm_year=2026))
    monkeypatch.setattr(hardware_fingerprint.platform, "system", lambda: "Linux")

    cpuinfo = "processor\t: 0\nmodel name\t: PowerPC 7447A\n"
    with patch("builtins.open", mock_open(read_data=cpuinfo)):
        oracle = hardware_fingerprint.HardwareFingerprint.collect_device_oracle()

    assert oracle["estimated_release_year"] == 2003
    assert oracle["estimated_age_years"] == 23
