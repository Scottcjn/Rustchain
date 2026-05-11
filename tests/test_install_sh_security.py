from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = ROOT / "install.sh"


def test_installer_pins_miner_download_hashes():
    script = INSTALL_SH.read_text(encoding="utf-8")

    assert 'LINUX_MINER_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/linux/rustchain_linux_miner.py"' in script
    assert 'MACOS_MINER_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/macos/rustchain_mac_miner_v2.5.py"' in script
    assert 'FINGERPRINT_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/linux/fingerprint_checks.py"' in script
    assert 'LINUX_MINER_SHA256="9475fe15d149ef7b3824c0009453c55e17fb6d1d411ea37e9f24f58c6313871c"' in script
    assert 'MACOS_MINER_SHA256="e50cea51a24c8c0337e340287a05e6431f6d95883ab913a1a79c19e99bc03dd8"' in script
    assert 'FINGERPRINT_SHA256="cdfca6e63ecd24f53b30140dd44df42415a3254c68aad95b1fca3c1557e15f7b"' in script
    assert 'verify_download "$INSTALL_DIR/rustchain_miner.py" "$MINER_SHA256"' in script
    assert 'verify_download "$INSTALL_DIR/fingerprint_checks.py" "$FINGERPRINT_SHA256"' in script


def test_installer_does_not_bypass_tls_verification():
    script = INSTALL_SH.read_text(encoding="utf-8")

    assert "--insecure" not in script
    assert "--no-check-certificate" not in script
    assert "--proto '=https' --tlsv1.2" in script
    assert "wget -q --https-only" in script
    assert "require_https_url" in script
