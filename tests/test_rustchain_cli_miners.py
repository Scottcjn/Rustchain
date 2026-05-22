# SPDX-License-Identifier: MIT
"""Regression tests for the standalone RustChain miners CLI command."""

from argparse import Namespace
import os
import sys
from unittest.mock import patch


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "cli"))

import rustchain_cli


def test_miners_command_formats_current_enveloped_api_shape(capsys):
    payload = {
        "miners": [
            {
                "miner": "RTC1234567890abcdef",
                "device_arch": "POWER8",
                "last_attest": 1779490467,
            }
        ],
        "pagination": {"count": 1, "limit": 100, "offset": 0, "total": 1},
    }

    with patch.object(rustchain_cli, "fetch_api", return_value=payload):
        rustchain_cli.cmd_miners(Namespace(count=False, json=False))

    output = capsys.readouterr().out
    assert "Active Miners (1 total, showing 20)" in output
    assert "RTC1234567890abcdef" in output
    assert "POWER8" in output


def test_miners_count_uses_enveloped_miner_rows(capsys):
    payload = {
        "miners": [{"miner": "RTC1"}, {"miner": "RTC2"}],
        "pagination": {"count": 2, "limit": 100, "offset": 0, "total": 2},
    }

    with patch.object(rustchain_cli, "fetch_api", return_value=payload):
        rustchain_cli.cmd_miners(Namespace(count=True, json=False))

    assert capsys.readouterr().out.strip() == "Active miners: 2"
