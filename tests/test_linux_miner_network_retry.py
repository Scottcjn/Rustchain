import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MINER_PATH = PROJECT_ROOT / "miners" / "linux" / "rustchain_linux_miner.py"


def load_linux_miner():
    module_name = "rustchain_linux_miner_network_retry_test"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, MINER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_request_with_network_retry_reports_bootstrap_failure(capsys):
    miner_mod = load_linux_miner()
    request = Mock(side_effect=requests.exceptions.ConnectionError("refused"))
    sleeps = []

    response = miner_mod._request_with_network_retry(
        request,
        "https://node.invalid/health",
        "checking bootstrap connectivity",
        retries=3,
        base_delay=1,
        sleep_func=sleeps.append,
    )

    assert response is None
    assert request.call_count == 3
    assert sleeps == [1, 2]
    output = capsys.readouterr().out
    assert "Cannot connect to bootstrap node" in output
    assert "Check network connectivity" in output


def test_mine_exits_nonzero_when_bootstrap_unreachable(monkeypatch):
    miner_mod = load_linux_miner()
    monkeypatch.setattr(miner_mod, "FINGERPRINT_AVAILABLE", False)
    monkeypatch.setattr(miner_mod, "get_linux_serial", lambda: "test-serial")

    miner = miner_mod.LocalMiner(wallet="RTC-test-wallet")
    monkeypatch.setattr(miner, "check_node_connectivity", lambda: False)

    assert miner.mine() == 1


def test_attest_returns_false_after_challenge_retries(monkeypatch, capsys):
    miner_mod = load_linux_miner()
    monkeypatch.setattr(miner_mod, "FINGERPRINT_AVAILABLE", False)
    monkeypatch.setattr(miner_mod, "get_linux_serial", lambda: "test-serial")
    monkeypatch.setattr(miner_mod.time, "sleep", lambda _: None)
    post = Mock(side_effect=requests.exceptions.Timeout("timed out"))
    monkeypatch.setattr(miner_mod.requests, "post", post)

    miner = miner_mod.LocalMiner(wallet="RTC-test-wallet")
    monkeypatch.setattr(miner, "_get_hw_info", lambda: {})

    assert miner.attest() is False
    assert post.call_count == 3
    assert "Cannot connect to bootstrap node" in capsys.readouterr().out
