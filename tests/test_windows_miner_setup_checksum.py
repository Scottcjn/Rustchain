# SPDX-License-Identifier: MIT
import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = ROOT / "miners" / "windows" / "rustchain_miner_setup.bat"
MINER_SCRIPT = ROOT / "miners" / "windows" / "rustchain_windows_miner.py"


def _setup_text():
    return SETUP_SCRIPT.read_text(encoding="utf-8", errors="replace")


def test_windows_miner_setup_pins_current_miner_hash():
    text = _setup_text()

    match = re.search(r'set "MINER_SHA256=([0-9a-f]{64})"', text, re.IGNORECASE)

    assert match is not None
    assert match.group(1).lower() == hashlib.sha256(MINER_SCRIPT.read_bytes()).hexdigest()


def test_windows_miner_setup_verifies_miner_before_run_instructions():
    text = _setup_text()

    assert "call :verify_miner" in text
    assert text.index("call :verify_miner") < text.index("Miner is ready. Run:")
    assert "Get-FileHash -Algorithm SHA256" in text
    assert "Hash.ToLowerInvariant()" in text
    assert 'if /I not "!ACTUAL_MINER_SHA256!"=="%MINER_SHA256%"' in text
    assert 'del /f /q "%MINER_SCRIPT%"' in text
    assert "Miner script SHA-256 mismatch." in text


def test_windows_miner_setup_echo_inside_if_block_has_no_unescaped_closing_parenthesis():
    text = _setup_text()

    assert "Keeping existing miner script:" in text
    assert "Keeping existing miner script (%MINER_SCRIPT%)." not in text
