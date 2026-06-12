# SPDX-License-Identifier: MIT
"""Focused tests for the dependency-light RustChain smolagents integration."""

import json
import sys
import types
import unittest
from unittest.mock import patch

from integrations.rustchain_smolagents import RustChainSmolagentsTools


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class RustChainSmolagentsToolsTest(unittest.TestCase):
    def setUp(self):
        self.tools = RustChainSmolagentsTools(timeout=1)

    @patch("integrations.rustchain_smolagents.rustchain_smolagents_tool.urlopen")
    def test_check_balance_wraps_public_response(self, mocked):
        mocked.return_value = FakeResponse({"amount_rtc": 12.5})
        result = self.tools.check_balance("wallet name")
        self.assertTrue(result["ok"])
        self.assertEqual(result["balance"]["amount_rtc"], 12.5)
        self.assertIn("miner_id=wallet+name", mocked.call_args.args[0].full_url)

    @patch("integrations.rustchain_smolagents.rustchain_smolagents_tool.urlopen")
    def test_list_bounties_filters_pull_requests(self, mocked):
        mocked.return_value = FakeResponse([
            {"number": 1, "title": "Bounty", "html_url": "https://example/1"},
            {"number": 2, "title": "PR", "pull_request": {}, "html_url": "https://example/2"},
        ])
        result = self.tools.list_bounties(999)
        self.assertEqual(result["count"], 1)
        self.assertIn("per_page=50", mocked.call_args.args[0].full_url)

    def test_list_bounties_rejects_invalid_limit_without_http(self):
        result = self.tools.list_bounties("many")
        self.assertFalse(result["ok"])
        self.assertIn("limit must be an integer", result["error"])

    @patch("integrations.rustchain_smolagents.rustchain_smolagents_tool.urlopen")
    def test_health_falls_back_to_live_explorer_stats(self, mocked):
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

    @patch("integrations.rustchain_smolagents.rustchain_smolagents_tool.urlopen")
    def test_epoch_is_extracted_from_stats(self, mocked):
        mocked.return_value = FakeResponse({"epoch": 191, "chain_id": "rustchain-mainnet-v2"})
        self.assertEqual(self.tools.get_current_epoch()["epoch"], 191)

    def test_empty_wallet_is_rejected_without_http(self):
        self.assertFalse(self.tools.check_balance(" ")["ok"])

    def test_smolagents_dependency_has_clear_error(self):
        with patch.dict("sys.modules", {"smolagents": None}):
            with self.assertRaisesRegex(RuntimeError, "pip install smolagents"):
                self.tools.as_smolagents_tools()

    def test_as_smolagents_tools_returns_four_tool_instances(self):
        fake_module = types.ModuleType("smolagents")

        class FakeTool:
            def __init__(self, *args, **kwargs):
                pass

        fake_module.Tool = FakeTool

        with patch.dict(sys.modules, {"smolagents": fake_module}):
            tool_instances = self.tools.as_smolagents_tools()

        self.assertEqual([tool.name for tool in tool_instances], [
            "check_balance",
            "list_bounties",
            "get_node_health",
            "get_current_epoch",
        ])
        self.assertEqual(tool_instances[0].forward("wallet-1")["wallet_id"], "wallet-1")


if __name__ == "__main__":
    unittest.main()
