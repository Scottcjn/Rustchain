from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install.sh"
ROOT_INSTALLER = ROOT / "install.sh"


def test_installer_defines_miner_crypto_url_for_macos():
    script = INSTALLER.read_text(encoding="utf-8")
    darwin_block = script.split('if [ "$(uname -s)" = "Darwin" ]; then')[1].split("else")[0]
    assert "MINER_CRYPTO_URL=" in darwin_block


def test_installer_uses_portable_sha256_for_miner_id():
    script = INSTALLER.read_text(encoding="utf-8")
    assert "shasum -a 256" in script
    assert "hashlib.sha256" in script


def test_root_installer_macos_v25_paths_and_bsd_compatibility():
    """Regression test for Rustchain#7975 / bounty #16251 on root install.sh."""
    script = ROOT_INSTALLER.read_text(encoding="utf-8")
    # 1. Correct platform-subdirectory paths (never bare miners/rustchain_linux_miner.py)
    assert 'MINER_PATH="macos/rustchain_mac_miner_v2.5.py"' in script
    assert 'MINER_PATH="linux/rustchain_linux_miner.py"' in script
    assert 'FINGERPRINT_PATH="macos/fingerprint_checks.py"' in script
    assert 'FINGERPRINT_PATH="linux/fingerprint_checks.py"' in script
    # 2. No bash 4+ associative arrays (`declare -A`) or GNU-only `grep -P`
    assert "declare -A" not in script
    assert "grep -P" not in script
    assert "grep -oP" not in script
    # 3. Portable SHA-256 fallback (`shasum -a 256`) and platform-aware Python hint
    assert "shasum -a 256" in script
    assert "brew install python3" in script
    assert 'echo -n' not in script
