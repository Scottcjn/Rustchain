import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "miners" / "windows" / "rustchain_miner_setup.bat"
MINER = ROOT / "miners" / "windows" / "rustchain_windows_miner.py"


def test_windows_bootstrap_pins_current_miner_hash():
    script = BOOTSTRAP.read_text(encoding="utf-8")
    match = re.search(r'set "MINER_SHA256=([a-f0-9]{64})"', script)

    assert match, "Windows bootstrap must pin a SHA-256 for the downloaded miner"
    assert match.group(1) == hashlib.sha256(MINER.read_bytes()).hexdigest()


def test_windows_bootstrap_verifies_downloaded_miner():
    script = BOOTSTRAP.read_text(encoding="utf-8")

    assert "Get-FileHash -Algorithm SHA256" in script
    assert "$actual -ne '%MINER_SHA256%'" in script
    assert "Remove-Item -LiteralPath '%MINER_SCRIPT%'" in script
    assert "if errorlevel 1 exit /b 1" in script


def test_windows_bootstrap_runs_powershell_verification_outside_else_block():
    script = BOOTSTRAP.read_text(encoding="utf-8")

    else_block = script.split('if exist "%MINER_SCRIPT%" (', 1)[1].split("echo.", 1)[0]
    assert "call :download_miner" in else_block
    assert "Get-FileHash" not in else_block
    assert ":download_miner" in script


def test_windows_bootstrap_existing_file_message_does_not_close_if_block():
    script = BOOTSTRAP.read_text(encoding="utf-8")

    existing_branch = script.split('if exist "%MINER_SCRIPT%" (', 1)[1].split(") else (", 1)[0]
    assert "Keeping existing miner script:" in existing_branch
    assert "(%MINER_SCRIPT%)" not in existing_branch
