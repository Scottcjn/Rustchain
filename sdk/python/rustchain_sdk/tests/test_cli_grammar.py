# SPDX-License-Identifier: MIT
"""Unit tests for RustChain SDK CLI grammar and options.

Validates fixes for:
- #8564: Fractional amounts and fees in `rustchain wallet send`
- #8565: Documented `rustchain node status` and `rustchain epoch info` commands
- #8566: Full attestation pipeline execution when `--json` flag is supplied
"""

import json
import unittest
from click.testing import CliRunner
from rustchain_sdk import cli


class TestCliGrammarAndOptions(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.trace = []

        async def fake_send(*args):
            self.trace.append(['send', list(args)])

        async def fake_node(*args):
            self.trace.append(['node', list(args)])

        async def fake_epoch(*args):
            self.trace.append(['epoch', list(args)])

        self.orig_send = cli._wallet_send
        self.orig_node = cli._node_status
        self.orig_epoch = cli._epoch_info
        self.orig_wallet = cli.RustChainWallet
        self.orig_client = cli.RustChainClient

        cli._wallet_send = fake_send
        cli._node_status = fake_node
        cli._epoch_info = fake_epoch

        trace = self.trace

        class FakeWallet:
            address = 'dummy-address'
            public_key_hex = 'dummy-public-key'

            @staticmethod
            def from_seed_phrase(words):
                trace.append(['wallet', words])
                return FakeWallet()

            def sign(self, data):
                trace.append(['sign', data.decode()])
                return b'dummy-signature'

        class FakeClient:
            def __init__(self, **kwargs):
                trace.append(['client', kwargs])

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get_attestation_status(self, key):
                trace.append(['status', key])
                return {'status': 'fixture-status'}

            async def attest_challenge(self, key):
                trace.append(['challenge', key])
                return {'challenge': 'fixture-challenge'}

            async def attest_submit(self, *args):
                trace.append(['submit', list(args)])
                return {'accepted': True}

        cli.RustChainWallet = FakeWallet
        cli.RustChainClient = FakeClient

    def tearDown(self):
        cli._wallet_send = self.orig_send
        cli._node_status = self.orig_node
        cli._epoch_info = self.orig_epoch
        cli.RustChainWallet = self.orig_wallet
        cli.RustChainClient = self.orig_client

    def test_fractional_wallet_send(self):
        """#8564: Ensure fractional RTC amount and fee are accepted by Click parser."""
        self.trace.clear()
        res = self.runner.invoke(
            cli.main,
            ['wallet', 'send', 'dummy-from', 'dummy-to', '0.5', '--fee', '0.01', '--seed', 'word1 word2']
        )
        self.assertEqual(res.exit_code, 0, f"Command failed: {res.output}")
        self.assertEqual(self.trace[0][0], 'send')
        self.assertEqual(self.trace[0][1][2], 0.5)
        self.assertEqual(self.trace[0][1][3], 0.01)

    def test_node_commands_grammar(self):
        """#8565: Ensure both 'rustchain node status' and 'rustchain node' invoke node status."""
        self.trace.clear()
        res_sub = self.runner.invoke(cli.main, ['node', 'status'])
        self.assertEqual(res_sub.exit_code, 0, f"node status failed: {res_sub.output}")
        self.assertEqual(self.trace[0][0], 'node')

        self.trace.clear()
        res_leaf = self.runner.invoke(cli.main, ['node'])
        self.assertEqual(res_leaf.exit_code, 0, f"node failed: {res_leaf.output}")
        self.assertEqual(self.trace[0][0], 'node')

    def test_epoch_commands_grammar(self):
        """#8565: Ensure both 'rustchain epoch info' and 'rustchain epoch' invoke epoch info."""
        self.trace.clear()
        res_sub = self.runner.invoke(cli.main, ['epoch', 'info'])
        self.assertEqual(res_sub.exit_code, 0, f"epoch info failed: {res_sub.output}")
        self.assertEqual(self.trace[0][0], 'epoch')

        self.trace.clear()
        res_leaf = self.runner.invoke(cli.main, ['epoch'])
        self.assertEqual(res_leaf.exit_code, 0, f"epoch failed: {res_leaf.output}")
        self.assertEqual(self.trace[0][0], 'epoch')

    def test_attest_json_runs_full_pipeline(self):
        """#8566: Ensure attest --json executes the full challenge-sign-submit pipeline."""
        self.trace.clear()
        res = self.runner.invoke(
            cli.main,
            ['attest', 'dummy-address', '--seed', 'dummy', '--node', 'https://invalid.test', '--json']
        )
        self.assertEqual(res.exit_code, 0, f"attest --json failed: {res.output}")
        ops = [t[0] for t in self.trace]
        self.assertEqual(ops, ['wallet', 'client', 'status', 'challenge', 'sign', 'submit'])
        self.assertEqual(json.loads(res.output), {'accepted': True})


if __name__ == '__main__':
    unittest.main()
