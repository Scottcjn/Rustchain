import json
from unittest.mock import AsyncMock, patch
from click.testing import CliRunner
from rustchain_sdk.cli import main

def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "rustchain" in result.output.lower()

@patch("rustchain_sdk.cli.RustChainClient")
def test_node_status_command(mock_client_cls):
    instance = mock_client_cls.return_value
    instance.health = AsyncMock(return_value={"status": "healthy", "version": "1.2.0"})
    runner = CliRunner()
    result = runner.invoke(main, ["node", "status"])
    assert result.exit_code == 0

@patch("rustchain_sdk.cli.RustChainClient")
def test_epoch_info_command(mock_client_cls):
    instance = mock_client_cls.return_value
    instance.epoch = AsyncMock(return_value={"epoch": 142, "slot": 88412})
    runner = CliRunner()
    result = runner.invoke(main, ["epoch", "info"])
    assert result.exit_code == 0