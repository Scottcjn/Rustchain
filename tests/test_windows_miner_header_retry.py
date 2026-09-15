# SPDX-License-Identifier: MIT
"""Unit tests for Windows miner header submission retry policy and diagnostics (Issue #7368)."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
WIN_MINER_PATH = ROOT / "miners" / "windows" / "rustchain_windows_miner.py"


def _load_win_miner_module():
    spec = importlib.util.spec_from_file_location("rustchain_windows_miner", WIN_MINER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_retryable_header_status_classification():
    mod = _load_win_miner_module()
    # Retryable statuses: 408, 425, 429, and 5xx
    assert mod.RustChainMiner._is_retryable_header_status(408) is True
    assert mod.RustChainMiner._is_retryable_header_status(425) is True
    assert mod.RustChainMiner._is_retryable_header_status(429) is True
    assert mod.RustChainMiner._is_retryable_header_status(500) is True
    assert mod.RustChainMiner._is_retryable_header_status(503) is True

    # Terminal statuses: 400, 401, 403, 404, 422
    assert mod.RustChainMiner._is_retryable_header_status(400) is False
    assert mod.RustChainMiner._is_retryable_header_status(401) is False
    assert mod.RustChainMiner._is_retryable_header_status(403) is False
    assert mod.RustChainMiner._is_retryable_header_status(404) is False
    assert mod.RustChainMiner._is_retryable_header_status(422) is False


def test_format_headless_event_includes_diagnostic_and_class():
    mod = _load_win_miner_module()
    
    # Retryable rejection event
    retry_evt = {
        "type": "share",
        "slot": 42,
        "submitted": 1,
        "accepted": 0,
        "success": False,
        "error": "HTTP 429 error=rate_limited",
        "retryable": True,
        "retry_in_seconds": 15
    }
    line = mod._format_headless_event(retry_evt)
    assert "FAIL" in line
    assert "error=HTTP 429 error=rate_limited" in line
    assert "class=retryable" in line
    assert "retry_in=15s" in line

    # Terminal rejection event
    term_evt = {
        "type": "share",
        "slot": 43,
        "submitted": 2,
        "accepted": 0,
        "success": False,
        "error": "HTTP 403 error=invalid_signature",
        "retryable": False,
        "retry_in_seconds": 0
    }
    line_term = mod._format_headless_event(term_evt)
    assert "class=terminal no_retry" in line_term
    assert "invalid_signature" in line_term
