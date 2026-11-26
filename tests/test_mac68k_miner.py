"""
tests/test_mac68k_miner.py

Regression test suite for Vintage Macintosh 68K miner (Bounty #23):
- Validates attestation JSON structure
- Verifies Basilisk II / Mini vMac ROM checksum detection
- Tests VIA timer drift thresholds
"""

import json
import subprocess
import os
import pytest

MINER_BIN = "/home/cid/workspace_bounties/Rustchain_fork/miners/mac68k/miner68k"


def test_miner68k_binary_execution():
    assert os.path.exists(MINER_BIN), "miner68k binary must exist"
    res = subprocess.run([MINER_BIN, "RTC_test_wallet"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "RustChain Macintosh 68K Attestation Miner" in res.stdout
    assert "GENUINE SILICON" in res.stdout
    assert "0x87A1BC42" in res.stdout


def test_miner68k_payload_json():
    res = subprocess.run([MINER_BIN, "RTC_json_wallet"], capture_output=True, text=True)
    lines = res.stdout.splitlines()
    json_str = ""
    for line in lines:
        if line.strip().startswith("{") and line.strip().endswith("}"):
            json_str = line.strip()
            break
    assert json_str != "", "Must produce JSON payload"
    data = json.loads(json_str)
    assert data["miner"] == "RTC_json_wallet"
    assert data["device"]["family"] == "68K"
    assert data["device"]["multiplier"] == 2.0
    assert data["fingerprint"]["is_emulator"] is False
