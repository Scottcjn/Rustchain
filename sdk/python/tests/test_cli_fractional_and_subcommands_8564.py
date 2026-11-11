# SPDX-License-Identifier: Apache-2.0
"""Unit tests for fractional RTC amount/fee, node status/epoch info subcommands, and attest --json (#8564, #8565, #8566)."""

import json
import unittest
from click.testing import CliRunner
from rustchain_sdk import cli


class CliFractionalSendAndSubcommandsTest(unittest.TestCase):
    def setUp(self):
        self.trace = []
        self._orig_send = cli._wallet_send
        self._orig_node = cli._node_status
        self._orig_epoch = cli._epoch_info
        self._orig_wallet = cli.RustChainWallet
        self._orig_client = cli.RustChainClient

        trace = self.trace

        async def fake_send(*args):
            trace.append(["send", list(args)])

        async def fake_node(*args):
            trace.append(["node", list(args)])

        async def fake_epoch(*args):
            trace.append(["epoch", list(args)])

        class FakeWallet:
            address = "dummy-address"
            public_key_hex = "dummy-public-key"

            @staticmethod
            def from_seed_phrase(words):
                trace.append(["wallet", words])
                return FakeWallet()

            def sign(self, data):
                trace.append(["sign", data.decode()])
                return b"dummy-signature"

        class FakeClient:
            def __init__(self, **kwargs):
                trace.append(["client", kwargs])

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get_attestation_status(self, key):
                trace.append(["status", key])
                return {"status": "fixture-status"}

            async def attest_challenge(self, key):
                trace.append(["challenge", key])
                return {"challenge": "fixture-challenge"}

            async def attest_submit(self, *args):
                trace.append(["submit", list(args)])
                return {"accepted": True}

        cli._wallet_send = fake_send
        cli._node_status = fake_node
        cli._epoch_info = fake_epoch
        cli.RustChainWallet = FakeWallet
        cli.RustChainClient = FakeClient

    def tearDown(self):
        cli._wallet_send = self._orig_send
        cli._node_status = self._orig_node
        cli._epoch_info = self._orig_epoch
        cli.RustChainWallet = self._orig_wallet
        cli.RustChainClient = self._orig_client

    def test_fractional_rtc_amount_and_fee_accepted(self):
        runner = CliRunner()
        r1 = runner.invoke(
            cli.main, ["wallet", "send", "dummy-from", "dummy-to", "0.5", "--seed", "dummy"]
        )
        self.assertEqual(r1.exit_code, 0, r1.output)
        self.assertEqual(self.trace[-1][1][2], 0.5)
        self.assertEqual(self.trace[-1][1][3], 0)

        r2 = runner.invoke(
            cli.main,
            ["wallet", "send", "dummy-from", "dummy-to", "1", "--fee", "0.01", "--seed", "dummy"],
        )
        self.assertEqual(r2.exit_code, 0, r2.output)
        self.assertEqual(self.trace[-1][1][2], 1)
        self.assertEqual(self.trace[-1][1][3], 0.01)

    def test_node_status_and_epoch_info_aliases(self):
        runner = CliRunner()
        for argv, expected_tag in (
            (["node", "status"], "node"),
            (["node"], "node"),
            (["epoch", "info"], "epoch"),
            (["epoch"], "epoch"),
        ):
            self.trace.clear()
            res = runner.invoke(cli.main, argv)
            self.assertEqual(res.exit_code, 0, res.output)
            self.assertEqual(self.trace[0][0], expected_tag)

    def test_attest_json_executes_full_attestation_flow(self):
        runner = CliRunner()
        res = runner.invoke(
            cli.main,
            ["attest", "dummy-address", "--seed", "dummy", "--node", "https://invalid.test", "--json"],
        )
        self.assertEqual(res.exit_code, 0, res.output)
        self.assertEqual(
            [t[0] for t in self.trace],
            ["wallet", "client", "status", "challenge", "sign", "submit"],
        )
        parsed = json.loads(res.output)
        self.assertEqual(parsed["challenge"], "fixture-challenge")
        self.assertEqual(parsed["submission"], {"accepted": True})


if __name__ == "__main__":
    unittest.main()
