#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Windows Miner Bundle (#179): HTTPS node URL migration, /health probe, and SHA256 sync."""

import hashlib
import importlib.util
import pathlib
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
WIN_MINER_PATH = ROOT / "miners" / "windows" / "rustchain_windows_miner.py"
INST_MINER_PATH = ROOT / "miners" / "windows" / "installer" / "src" / "rustchain_windows_miner.py"
SETUP_BAT_PATH = ROOT / "miners" / "windows" / "rustchain_miner_setup.bat"


def _load_miner(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    with mock.patch("time.sleep", return_value=None):
        spec.loader.exec_module(mod)
    return mod


class WindowsMinerBundle179Test(unittest.TestCase):
    def test_legacy_port_8088_auto_upgrades_to_https_mainnet(self):
        for idx, path in enumerate((WIN_MINER_PATH, INST_MINER_PATH)):
            mod = _load_miner(f"win_miner_179_{idx}", path)
            self.assertEqual(mod.RUSTCHAIN_API, "https://50.28.86.131")
            self.assertEqual(mod._normalize_node_url("http://50.28.86.131:8088"), "https://50.28.86.131")
            self.assertEqual(mod._normalize_node_url(None), "https://50.28.86.131")

    def test_check_node_health_parses_live_node_response(self):
        mod = _load_miner("win_miner_health_179", INST_MINER_PATH)
        with mock.patch.object(mod.RustChainMiner, "_run_fingerprint_checks", return_value=None):
            miner = mod.RustChainMiner("RTCfe0ac752b80e543048c0d91e7dddd1277678b8a5", "http://50.28.86.131:8088")
        self.assertEqual(miner.node_url, "https://50.28.86.131")

        fake_resp = mock.Mock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {"ok": True, "db_rw": True, "tip_age_slots": 0, "version": "2.2.1-rip200"}
        with mock.patch.object(mod.requests, "get", return_value=fake_resp) as m_get:
            health = miner.check_node_health()
        self.assertTrue(health["ok"])
        self.assertEqual(health["data"]["version"], "2.2.1-rip200")
        m_get.assert_called_once_with("https://50.28.86.131/health", timeout=10, verify=miner.tls_verify)

    def test_setup_bat_sha256_matches_windows_miner(self):
        expected_sha = hashlib.sha256(WIN_MINER_PATH.read_bytes()).hexdigest()
        bat_text = SETUP_BAT_PATH.read_text(encoding="utf-8")
        self.assertIn(f'set "MINER_SHA256={expected_sha}"', bat_text)


if __name__ == "__main__":
    unittest.main()
