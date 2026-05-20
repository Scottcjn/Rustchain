import hashlib
from pathlib import Path

import setup_miner


ROOT = Path(__file__).resolve().parents[1]


def test_setup_miner_pins_current_miner_artifacts():
    expected_files = {
        "Linux": ROOT / "miners" / "linux" / "rustchain_linux_miner.py",
        "Darwin": ROOT / "miners" / "macos" / "rustchain_mac_miner_v2.5.py",
        "Windows": ROOT / "miners" / "windows" / "rustchain_windows_miner.py",
    }

    for platform, artifact in setup_miner.MINER_ARTIFACTS.items():
        assert artifact["url"].startswith("https://raw.githubusercontent.com/Scottcjn/Rustchain/main/")
        assert artifact["sha256"] == hashlib.sha256(expected_files[platform].read_bytes()).hexdigest()


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


def test_setup_miner_help_exits_before_setup(monkeypatch, capsys):
    calls = []

    for name in (
        "check_requirements",
        "detect_hardware",
        "create_directories",
        "download_miner",
        "create_config",
        "create_start_script",
        "install_service",
    ):
        monkeypatch.setattr(setup_miner.MinerSetup, name, lambda self, _name=name: calls.append(_name))

    monkeypatch.setattr(setup_miner.sys, "argv", ["setup_miner.py", "--help"])

    assert setup_miner.main() == 0
    assert calls == []
    assert "RustChain Miner Setup" in capsys.readouterr().out
