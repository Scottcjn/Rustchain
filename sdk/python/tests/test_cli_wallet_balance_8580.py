# SPDX-License-Identifier: Apache-2.0
"""Unit tests for canonical /wallet/balance CLI rendering (Scottcjn/Rustchain#8580)."""

import unittest
import httpx
from click.testing import CliRunner
from rustchain_sdk import cli
from rustchain_sdk.client import RustChainClient


class WalletBalanceCliCanonicalFieldTest(unittest.TestCase):
    def _invoke_balance(self, payload: dict) -> str:
        client = RustChainClient(base_url="https://example.invalid", verify=True)
        client._client = httpx.AsyncClient(
            base_url="https://example.invalid",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=payload, request=request)
            ),
        )
        original = cli.RustChainClient

        class FixedClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                await client.close()

            async def get_balance(self, address):
                return await client.get_balance(address)

        cli.RustChainClient = lambda **kwargs: FixedClient()
        try:
            res = CliRunner().invoke(cli.main, ["wallet", "balance", "local-fixture"])
            self.assertEqual(res.exit_code, 0, res.output)
            return res.output.strip()
        finally:
            cli.RustChainClient = original

    def test_canonical_amount_rtc_payload_displays_balance(self):
        out = self._invoke_balance(
            {"amount_i64": 21000000, "amount_rtc": 21, "miner_id": "local-fixture"}
        )
        self.assertIn("Address:  local-fixture", out)
        self.assertIn("Balance:  21 RTC", out)

    def test_legacy_balance_alias_still_supported(self):
        out = self._invoke_balance(
            {"balance": 42, "nonce": 3, "miner_id": "local-fixture"}
        )
        self.assertIn("Balance:  42 RTC", out)
        self.assertIn("Nonce:    3", out)

    def test_amount_i64_fallback_when_amount_rtc_omitted(self):
        out = self._invoke_balance({"amount_i64": 15500000, "miner_id": "local-fixture"})
        self.assertIn("Balance:  15.5 RTC", out)

    def test_missing_balance_fields_prints_unavailable_not_zero(self):
        out = self._invoke_balance({"miner_id": "local-fixture"})
        self.assertIn("Balance:  unavailable", out)
        self.assertNotIn("Balance:  0 RTC", out)


if __name__ == "__main__":
    unittest.main()
