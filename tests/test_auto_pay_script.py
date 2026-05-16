#!/usr/bin/env python3
"""Regression tests for scripts/auto-pay.py."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "auto-pay.py"


def load_auto_pay_module(env: dict[str, str] | None = None):
    """Load scripts/auto-pay.py as a module with optional env overrides."""
    spec = importlib.util.spec_from_file_location("auto_pay_test_module", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    env = env or {}
    with patch.dict(os.environ, env, clear=False):
        spec.loader.exec_module(module)
    return module


class TestAutoPayTransferPort(unittest.TestCase):
    def test_transfer_uses_default_8099_port(self):
        mod = load_auto_pay_module()
        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            captured["timeout"] = timeout
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"ok": True})

        with patch.object(mod.requests, "post", side_effect=fake_post):
            result = mod.transfer_rtc("50.28.86.131", "admin-key", "alice", 7.5, "memo")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(captured["url"], "http://50.28.86.131:8099/wallet/transfer")
        self.assertEqual(captured["json"]["amount_rtc"], 7.5)

    def test_transfer_honors_rtc_vps_port_override(self):
        mod = load_auto_pay_module({"RTC_VPS_PORT": "8088"})
        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"ok": True})

        with patch.object(mod.requests, "post", side_effect=fake_post):
            mod.transfer_rtc("50.28.86.131", "admin-key", "alice", 7.5, "memo")

        self.assertEqual(captured["url"], "http://50.28.86.131:8088/wallet/transfer")

    def test_transfer_retries_after_connection_error(self):
        mod = load_auto_pay_module()
        fake_response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"ok": True})

        with patch.object(mod.requests, "post", side_effect=[mod.requests.exceptions.ConnectionError("refused"), fake_response]) as mock_post:
            with patch.object(mod.time, "sleep") as mock_sleep:
                result = mod.transfer_rtc("50.28.86.131", "admin-key", "alice", 7.5, "memo")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
