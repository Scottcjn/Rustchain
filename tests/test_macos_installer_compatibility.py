from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install.sh"


def test_installer_defines_miner_crypto_url_for_macos():
    script = INSTALLER.read_text(encoding="utf-8")
    darwin_block = script.split('if [ "$(uname -s)" = "Darwin" ]; then')[1].split("else")[0]
    assert "MINER_CRYPTO_URL=" in darwin_block


def test_installer_uses_portable_sha256_for_miner_id():
    script = INSTALLER.read_text(encoding="utf-8")
    assert "shasum -a 256" in script
    assert "hashlib.sha256" in script
