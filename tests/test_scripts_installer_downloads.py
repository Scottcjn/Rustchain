from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install.sh"


def test_scripts_installer_uses_existing_linux_miner_paths():
    script = INSTALLER.read_text(encoding="utf-8")

    assert 'MINER_URL="${REPO_RAW}/miners/linux/rustchain_linux_miner.py"' in script
    assert 'FINGERPRINT_URL="${REPO_RAW}/miners/linux/fingerprint_checks.py"' in script


def test_scripts_installer_fails_on_http_download_errors():
    script = INSTALLER.read_text(encoding="utf-8")

    assert "curl -fsSL --proto '=https' --tlsv1.2" in script
    assert 'download_file "${MINER_URL}"' in script
    assert 'download_file "${FINGERPRINT_URL}"' in script
    assert '[ ! -s "${INSTALL_DIR}/fingerprint_checks.py" ]' in script
