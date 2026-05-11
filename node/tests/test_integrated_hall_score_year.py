# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "rustchain_v2_integrated_v2.2.1_rip200.py"


def _load_integrated_node(monkeypatch, tmp_path):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-key-000000000000000000")
    monkeypatch.setenv("RUSTCHAIN_DB_PATH", str(tmp_path / "rustchain.db"))
    spec = importlib.util.spec_from_file_location("integrated_hall_score_year_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inline_rust_score_uses_current_year_for_age_bonus(monkeypatch, tmp_path):
    module = _load_integrated_node(monkeypatch, tmp_path)
    monkeypatch.setattr(module, "current_utc_year", lambda: 2026)

    score = module.calculate_rust_score_inline(2001, "modern", 0, 999)

    assert score == 250
