import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
WALLET_DIR = REPO_ROOT / "wallet"
MODULE_PATH = WALLET_DIR / "__main__.py"


def load_wallet_main(monkeypatch):
    monkeypatch.syspath_prepend(str(WALLET_DIR))
    spec = importlib.util.spec_from_file_location("wallet_entrypoint", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_coinbase_link_arguments_dispatch_to_coinbase_handler(monkeypatch):
    wallet_main = load_wallet_main(monkeypatch)
    dispatch = Mock()
    monkeypatch.setattr(wallet_main, "cmd_coinbase", dispatch)
    base_address = "0x" + ("a" * 40)
    monkeypatch.setattr(
        sys,
        "argv",
        ["clawrtc", "coinbase", "link", base_address],
    )

    wallet_main.main()

    dispatch.assert_called_once()
    args = dispatch.call_args.args[0]
    assert args.wallet_command == "coinbase"
    assert args.coinbase_action == "link"
    assert args.base_address == base_address


def test_coinbase_without_action_still_dispatches_for_default_show(monkeypatch):
    wallet_main = load_wallet_main(monkeypatch)
    dispatch = Mock()
    monkeypatch.setattr(wallet_main, "cmd_coinbase", dispatch)
    monkeypatch.setattr(sys, "argv", ["clawrtc", "coinbase"])

    wallet_main.main()

    dispatch.assert_called_once()
    args = dispatch.call_args.args[0]
    assert args.wallet_command == "coinbase"
    assert args.coinbase_action is None


def test_missing_wallet_command_prints_help_and_exits(monkeypatch, capsys):
    wallet_main = load_wallet_main(monkeypatch)
    dispatch = Mock()
    monkeypatch.setattr(wallet_main, "cmd_coinbase", dispatch)
    monkeypatch.setattr(sys, "argv", ["clawrtc"])

    with pytest.raises(SystemExit) as exc_info:
        wallet_main.main()

    assert exc_info.value.code == 1
    assert "Wallet commands" in capsys.readouterr().out
    dispatch.assert_not_called()
