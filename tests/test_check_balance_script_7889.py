"""Offline tests for scripts/check_balance.sh exit codes (Rustchain#7889).

The real bash script is run against a local HTTP stub, so no external
network is required. Skips on hosts without bash or jq (e.g. Windows).
"""

import json
import os
import shutil
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_balance.sh"
WALLET = "AhqbFaPBPLMMiaLDzA9WhQcyvv4hMxiteLhPk3NhG1iG"

pytestmark = pytest.mark.skipif(
    not shutil.which("bash") or not shutil.which("jq"),
    reason="check_balance.sh tests require bash and jq on PATH",
)


class _Handler(BaseHTTPRequestHandler):
    status = 200
    body = b""

    def do_GET(self):
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass


@pytest.fixture
def stub():
    """Local HTTP stub; returns (base_url, configure) for one call site."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def configure(status, body):
        _Handler.status = status
        _Handler.body = body if isinstance(body, bytes) else json.dumps(body).encode()
        return base

    try:
        yield configure
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def closed_port():
    """A port with nothing listening (connection refused, no network needed)."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _run(*args, **env_overrides):
    env = {**os.environ, "RUSTCHAIN_TIMEOUT": "5", **env_overrides}
    return subprocess.run(
        [shutil.which("bash"), str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def test_happy_path_prints_balance_only(stub):
    rpc = stub(200, {"amount_rtc": 12.5, "miner_id": WALLET})
    result = _run(WALLET, RUSTCHAIN_RPC=rpc)
    assert result.returncode == 0
    assert result.stdout.strip() == "12.5"
    assert result.stderr == ""


def test_no_args_usage_exit_1():
    result = _run()
    assert result.returncode == 1
    assert "Usage:" in result.stderr


def test_help_documents_exit_codes():
    result = _run("--help")
    assert result.returncode == 1
    for code_line in ("0  success", "1  usage", "2  network", "3  bad response"):
        assert code_line in result.stderr


def test_invalid_wallet_exit_1():
    result = _run("x", RUSTCHAIN_RPC="http://127.0.0.1:1")
    assert result.returncode == 1
    assert "invalid wallet address" in result.stderr


def test_missing_jq_dependency_exit_1(stub, tmp_path):
    rpc = stub(200, {"amount_rtc": 1.0, "miner_id": WALLET})
    result = _run(WALLET, RUSTCHAIN_RPC=rpc, PATH=str(tmp_path))
    assert result.returncode == 1
    assert "'jq' is not installed" in result.stderr


def test_network_refused_exit_2(closed_port):
    result = _run(WALLET, RUSTCHAIN_RPC=f"http://127.0.0.1:{closed_port}")
    assert result.returncode == 2
    assert "network request failed" in result.stderr
    assert "Balance" not in result.stdout


def test_non_200_exit_3(stub):
    rpc = stub(500, {"error": "boom"})
    result = _run(WALLET, RUSTCHAIN_RPC=rpc)
    assert result.returncode == 3
    assert "HTTP 500" in result.stderr


def test_empty_body_exit_3(stub):
    rpc = stub(200, b"")
    result = _run(WALLET, RUSTCHAIN_RPC=rpc)
    assert result.returncode == 3
    assert "empty response body" in result.stderr


def test_malformed_json_exit_3_distinct_message(stub):
    rpc = stub(200, b"<html>not json {{{")
    result = _run(WALLET, RUSTCHAIN_RPC=rpc)
    assert result.returncode == 3
    assert "malformed JSON" in result.stderr
    # must not be misreported as a missing field
    assert "missing amount_rtc" not in result.stderr


def test_missing_amount_field_exit_3(stub):
    rpc = stub(200, {"foo": 1})
    result = _run(WALLET, RUSTCHAIN_RPC=rpc)
    assert result.returncode == 3
    assert "missing amount_rtc" in result.stderr


def test_non_numeric_amount_exit_3(stub):
    rpc = stub(200, {"amount_rtc": "a lot", "miner_id": WALLET})
    result = _run(WALLET, RUSTCHAIN_RPC=rpc)
    assert result.returncode == 3
    assert "not a valid number" in result.stderr


def test_wallet_mismatch_exit_3(stub):
    rpc = stub(200, {"amount_rtc": 5.0, "miner_id": "OtherWalletAddress1234567890abcdefghij"})
    result = _run(WALLET, RUSTCHAIN_RPC=rpc)
    assert result.returncode == 3
    assert "does not match" in result.stderr
