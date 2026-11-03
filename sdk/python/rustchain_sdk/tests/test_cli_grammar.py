# SPDX-License-Identifier: MIT
"""
Regression tests for #8565: the documented ``node status`` / ``epoch info``
invocations must parse and run.

The real CLI is imported and only the node/epoch seams are replaced with
recording fakes, so no network requests or funds movement happen.
"""

import pytest
from click.testing import CliRunner

from rustchain_sdk import cli


@pytest.fixture
def recording_seams(monkeypatch):
    """Replace the CLI's node/epoch seams with recording fakes."""
    trace = []

    async def fake_node_status(node, as_json):
        trace.append(("node", node, as_json))

    async def fake_epoch_info(node, as_json):
        trace.append(("epoch", node, as_json))

    monkeypatch.setattr(cli, "_node_status", fake_node_status)
    monkeypatch.setattr(cli, "_epoch_info", fake_epoch_info)
    return trace


class TestNodeAndEpochGrammar:
    """#8565 — both the bare command and the documented subcommand must work."""

    def test_node_status_subcommand(self, recording_seams):
        result = CliRunner().invoke(cli.main, ["node", "status"])
        assert result.exit_code == 0, result.output
        assert recording_seams[0][0] == "node"

    def test_node_bare_command(self, recording_seams):
        result = CliRunner().invoke(cli.main, ["node"])
        assert result.exit_code == 0, result.output
        assert recording_seams[0][0] == "node"

    def test_epoch_info_subcommand(self, recording_seams):
        result = CliRunner().invoke(cli.main, ["epoch", "info"])
        assert result.exit_code == 0, result.output
        assert recording_seams[0][0] == "epoch"

    def test_epoch_bare_command(self, recording_seams):
        result = CliRunner().invoke(cli.main, ["epoch"])
        assert result.exit_code == 0, result.output
        assert recording_seams[0][0] == "epoch"
