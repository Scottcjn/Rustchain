import hashlib
import re
from pathlib import Path

import setup_miner


ROOT = Path(__file__).resolve().parents[1]
WINDOWS_BOOTSTRAP = ROOT / "miners" / "windows" / "rustchain_miner_setup.bat"


def test_setup_miner_pins_current_miner_artifacts():
    expected_files = {
        "Linux": ROOT / "miners" / "linux" / "rustchain_linux_miner.py",
        "Darwin": ROOT / "miners" / "macos" / "rustchain_mac_miner_v2.5.py",
        "Windows": ROOT / "miners" / "windows" / "rustchain_windows_miner.py",
    }

    for platform, artifact in setup_miner.MINER_ARTIFACTS.items():
        assert artifact["url"].startswith("https://raw.githubusercontent.com/Scottcjn/Rustchain/main/")
        assert artifact["sha256"] == hashlib.sha256(expected_files[platform].read_bytes()).hexdigest()


def test_windows_bootstrap_pins_current_miner_script():
    content = WINDOWS_BOOTSTRAP.read_text(encoding="utf-8")
    match = re.search(r'^set "MINER_SHA256=([0-9a-fA-F]{64})"$', content, re.MULTILINE)
    assert match is not None
    expected = hashlib.sha256((ROOT / "miners" / "windows" / "rustchain_windows_miner.py").read_bytes()).hexdigest()
    assert match.group(1).lower() == expected


def test_setup_miner_pins_current_macos_artifact():
    expected_file = ROOT / "miners" / "macos" / "rustchain_mac_miner_v2.5.py"
    artifact = setup_miner.MINER_ARTIFACTS["Darwin"]

    assert artifact["sha256"] == hashlib.sha256(expected_file.read_bytes()).hexdigest()


def test_setup_miner_downloads_current_verified_artifact():
    source = Path(setup_miner.__file__).read_text(encoding="utf-8")

    assert "RustChain/miner/main/rustchain_universal_miner.py" not in source
    assert "rustchain.io/downloads/rustchain_universal_miner.py" not in source
    assert "urlparse(miner_url)" in source
    assert "hashlib.sha256(content).hexdigest()" in source
    assert "create_local_miner(miner_file)" not in source
