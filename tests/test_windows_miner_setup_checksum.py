# SPDX-License-Identifier: MIT
import ast
import hashlib
import re
from pathlib import Path, PureWindowsPath


ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = ROOT / "miners" / "windows" / "rustchain_miner_setup.bat"
MINER_SCRIPT = ROOT / "miners" / "windows" / "rustchain_windows_miner.py"
SPEC_FILE = ROOT / "miners" / "windows" / "rustchain_windows_miner.spec"


def _setup_text():
    return SETUP_SCRIPT.read_text(encoding="utf-8", errors="replace")


def _analysis_scripts():
    tree = ast.parse(SPEC_FILE.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        if getattr(node.value.func, "id", "") != "Analysis":
            continue
        scripts = node.value.args[0]
        assert isinstance(scripts, ast.List)
        return [item.value for item in scripts.elts if isinstance(item, ast.Constant)]
    raise AssertionError("PyInstaller Analysis() call not found")


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


def test_windows_miner_spec_uses_checkout_relative_script():
    scripts = _analysis_scripts()

    assert scripts == ["rustchain_windows_miner.py"]
    for script in scripts:
        assert not Path(script).is_absolute()
        assert not PureWindowsPath(script).is_absolute()
