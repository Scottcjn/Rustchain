# SPDX-License-Identifier: MIT
"""Focused tests for the dependency-light RustChain Agno integration."""

import json
import unittest
from unittest.mock import patch

from integrations.rustchain_agno import RustChainAgnoTools


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class RustChainAgnoToolsTest(unittest.TestCase):
    def setUp(self):
        self.tools = RustChainAgnoTools(timeout=1)

    @patch("integrations.rustchain_agno.rustchain_agno_tool.urlopen")
    def test_check_balance_wraps_public_response(self, mocked):
        mocked.return_value = FakeResponse({"amount_rtc": 25})
        result = self.tools.check_balance("agent wallet")
        self.assertTrue(result["ok"])
        self.assertEqual(result["balance"]["amount_rtc"], 25)
        self.assertIn("miner_id=agent+wallet", mocked.call_args.args[0].full_url)

    @patch("integrations.rustchain_agno.rustchain_agno_tool.urlopen")
    def test_list_bounties_filters_pull_requests_and_clamps_limit(self, mocked):
        mocked.return_value = FakeResponse([
            {"number": 1, "title": "Bounty", "html_url": "https://example/1"},
            {"number": 2, "title": "PR", "pull_request": {}, "html_url": "https://example/2"},
        ])
        result = self.tools.list_bounties(500)
        self.assertEqual(result["count"], 1)
        self.assertIn("per_page=50", mocked.call_args.args[0].full_url)

    def test_list_bounties_rejects_invalid_limit_without_http(self):
        result = self.tools.list_bounties("many")
        self.assertFalse(result["ok"])
        self.assertIn("limit must be an integer", result["error"])

    @patch("integrations.rustchain_agno.rustchain_agno_tool.urlopen")
    def test_health_falls_back_to_explorer_stats(self, mocked):
        mocked.side_effect = [
            FakeResponse({"ok": False, "error": "unhealthy"}),
            FakeResponse({"epoch": 191, "chain_id": "rustchain-mainnet-v2"}),
        ]
        result = self.tools.get_node_health()
        self.assertTrue(result["ok"])
        self.assertEqual(
            mocked.call_args.args[0].full_url,
            "https://explorer.rustchain.org/api/stats",
        )

    @patch("integrations.rustchain_agno.rustchain_agno_tool.urlopen")
    def test_epoch_is_extracted_from_response(self, mocked):
        mocked.return_value = FakeResponse({"current_epoch": 192})
        self.assertEqual(self.tools.get_current_epoch()["epoch"], 192)

    def test_empty_wallet_is_rejected_without_http(self):
        self.assertFalse(self.tools.check_balance(" ")["ok"])

    def test_agno_dependency_has_clear_error(self):
        with patch.dict("sys.modules", {"agno": None, "agno.tools": None, "phi": None, "phi.tools": None}):
            with self.assertRaisesRegex(RuntimeError, "pip install agno"):
                self.tools.as_agno_toolkit()


if __name__ == "__main__":
    unittest.main()
