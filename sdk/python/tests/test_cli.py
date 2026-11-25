import pytest
from click.testing import CliRunner
import json
from unittest.mock import patch

# Assuming the CLI entrypoint is named `cli` in rustchain_sdk.cli
from rustchain_sdk.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

# --- 1. Basic Command Coverage & Help ---

@pytest.mark.parametrize("command", [
    [],
    ["wallet"],
    ["wallet", "create"],
    ["wallet", "balance"],
    ["wallet", "send"],
    ["node"],
    ["epoch"],
    ["miners"],
    ["miners", "list"],
    ["attest"]
])
def test_help_commands(runner, command):
    result = runner.invoke(cli, command + ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output

# --- 2. Error Paths ---

def test_node_unreachable(runner):
    with patch("rustchain_sdk.cli.requests.get") as mock_get:
        mock_get.side_effect = Exception("Connection refused")
        result = runner.invoke(cli, ["node"])
        assert result.exit_code != 0
        assert "Error" in result.output or "Connection refused" in result.output

def test_bad_address(runner):
    result = runner.invoke(cli, ["wallet", "balance", "--address", "invalid_address_format"])
    assert result.exit_code != 0

def test_bad_amount_string(runner):
    result = runner.invoke(cli, ["wallet", "send", "--amount", "abc", "--to", "some_address"])
    assert result.exit_code != 0

def test_bad_amount_negative(runner):
    result = runner.invoke(cli, ["wallet", "send", "--amount", "-5", "--to", "some_address"])
    assert result.exit_code != 0

def test_bad_amount_zero(runner):
    result = runner.invoke(cli, ["wallet", "send", "--amount", "0", "--to", "some_address"])
    assert result.exit_code != 0

# --- 3. Regression Tests ---

@pytest.mark.xfail(strict=True, reason="Rustchain#8564: fractional amounts rejected")
def test_regression_8564_fractional_amounts(runner):
    # This should fail until #8564 is merged
    with patch("rustchain_sdk.cli.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"txid": "12345"}
        result = runner.invoke(cli, ["wallet", "send", "--amount", "1.5", "--to", "addr123"])
        assert result.exit_code == 0

@pytest.mark.xfail(strict=True, reason="Rustchain#8565: README commands that the parser rejects")
def test_regression_8565_readme_commands(runner):
    # Simulating a command from README that currently fails
    result = runner.invoke(cli, ["miners", "list", "--active-only"])
    assert result.exit_code == 0

@pytest.mark.xfail(strict=True, reason="Rustchain#8566: attest --json not attesting")
def test_regression_8566_attest_json(runner):
    with patch("rustchain_sdk.cli.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"status": "attested"}
        result = runner.invoke(cli, ["attest", "--json"])
        assert result.exit_code == 0
        assert '"status": "attested"' in result.output

@pytest.mark.xfail(strict=True, reason="Rustchain#8580: balance printing 0 RTC for canonical responses")
def test_regression_8580_canonical_balance(runner):
    with patch("rustchain_sdk.cli.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        # Simulating a canonical response that currently prints 0
        mock_get.return_value.json.return_value = {"balance": 1000000} 
        result = runner.invoke(cli, ["wallet", "balance", "--address", "addr123"])
        assert result.exit_code == 0
        assert "0 RTC" not in result.output

# --- 4. No Float Money Assertion (#8618) ---

@pytest.mark.xfail(strict=True, reason="Rustchain#8618: float money serialization")
def test_no_float_money_serialization(runner):
    with patch("rustchain_sdk.cli.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"txid": "123"}
        result = runner.invoke(cli, ["wallet", "send", "--amount", "0.1", "--to", "addr123"])
        assert result.exit_code == 0
        
        # Verify the exact JSON payload sent in the request
        mock_post.assert_called_once()
        kwargs = mock_post.call_args.kwargs
        data = kwargs.get("json", {})
        # The amount should be serialized as an exact string or integer (e.g., minor units), not a float
        assert not isinstance(data.get("amount"), float)
