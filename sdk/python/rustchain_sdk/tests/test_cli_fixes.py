# SPDX-License-Identifier: MIT
"""
Regression tests for the Python SDK CLI fixes.

Covers:
- #8564: `wallet send` must accept fractional RTC amount and fee.
- #8565: documented `node status` / `epoch info` invocations must parse.

The real CLI is imported and only the wallet/client seams are replaced with
recording fakes, so no network, signing, or funds movement happens.
"""

import asyncio

import pytest
from click.testing import CliRunner

from rustchain_sdk import cli


@pytest.fixture
def recording_seams(monkeypatch):
    """Replace the CLI's wallet/client seams with recording fakes."""
    trace = []

    async def fake_wallet_send(from_address, to_address, amount, fee, words, node, as_json):
        trace.append(("send", from_address, to_address, amount, fee))

    async def fake_node_status(node, as_json):
        trace.append(("node", node, as_json))

    async def fake_epoch_info(node, as_json):
        trace.append(("epoch", node, as_json))

    monkeypatch.setattr(cli, "_wallet_send", fake_wallet_send)
    monkeypatch.setattr(cli, "_node_status", fake_node_status)
    monkeypatch.setattr(cli, "_epoch_info", fake_epoch_info)
    return trace


class TestWalletSendFractionalAmount:
    """#8564 — fractional RTC amount and fee must parse and reach the transfer."""

    def test_fractional_amount_is_accepted(self, recording_seams):
        result = CliRunner().invoke(
            cli.main,
            ["wallet", "send", "dummy-from", "dummy-to", "0.5", "--seed", "dummy"],
        )
        assert result.exit_code == 0, result.output
        assert recording_seams == [("send", "dummy-from", "dummy-to", 0.5, 0)]

    def test_fractional_fee_is_accepted(self, recording_seams):
        result = CliRunner().invoke(
            cli.main,
            ["wallet", "send", "dummy-from", "dummy-to", "1", "--fee", "0.01", "--seed", "dummy"],
        )
        assert result.exit_code == 0, result.output
        assert recording_seams == [("send", "dummy-from", "dummy-to", 1.0, 0.01)]

    def test_integer_amount_and_fee_still_work(self, recording_seams):
        result = CliRunner().invoke(
            cli.main,
            ["wallet", "send", "dummy-from", "dummy-to", "1", "--fee", "1", "--seed", "dummy"],
        )
        assert result.exit_code == 0, result.output
        assert recording_seams == [("send", "dummy-from", "dummy-to", 1.0, 1.0)]
