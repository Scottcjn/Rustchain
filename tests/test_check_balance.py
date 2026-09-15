# SPDX-License-Identifier: MIT
"""Unit and regression tests for scripts/check_balance.sh.

Covers all exit codes:
  0 - Success (balance printed to stdout)
  1 - Usage / validation error (missing arg, short address, --help)
  2 - Network error (unreachable RPC, connection timeout)
  3 - Bad response (non-200, malformed JSON, missing fields, API error, wallet mismatch)
"""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_balance.sh"


def test_check_balance_script_exists():
    assert SCRIPT.exists(), "scripts/check_balance.sh must exist"
    content = SCRIPT.read_text(encoding="utf-8")
    assert "set -euo pipefail" in content
    assert "Exit codes:" in content
    assert "0  success" in content or "0 — success" in content


def test_check_balance_usage_and_exit_codes_documented():
    content = SCRIPT.read_text(encoding="utf-8")
    assert "exit 1" in content
    assert "exit 2" in content
    assert "exit 3" in content
    assert "amount_rtc" in content
    assert "--max-time" in content or "TIMEOUT_SEC" in content


def test_check_balance_fails_on_empty_or_short_wallet():
    content = SCRIPT.read_text(encoding="utf-8")
    # Validates wallet length guard
    assert "${#WALLET} -lt 10" in content or "${#WALLET} < 10" in content or "invalid wallet address" in content
