from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP_SH = ROOT / "setup.sh"


def test_setup_sh_uses_platform_specific_miner_paths():
    script = SETUP_SH.read_text(encoding="utf-8")

    assert 'RC_BASE_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/${RC_REPO_REF}"' in script
    assert 'RC_MINER_PATH="miners/linux/rustchain_linux_miner.py"' in script
    assert 'RC_FP_PATH="miners/linux/fingerprint_checks.py"' in script
    assert 'RC_MINER_PATH="miners/macos/rustchain_mac_miner_v2.5.py"' in script
    assert 'RC_FP_PATH="miners/macos/fingerprint_checks.py"' in script
    assert 'RC_MINER_URL="${RC_BASE_URL}/${RC_MINER_PATH}"' in script
    assert 'RC_FP_URL="${RC_BASE_URL}/${RC_FP_PATH}"' in script


def test_setup_sh_fails_fast_when_downloads_fail():
    script = SETUP_SH.read_text(encoding="utf-8")

    assert "curl -fsSL --proto '=https' --tlsv1.2" in script
    assert "wget -q --https-only" in script
    assert 'download_file "$RC_MINER_URL" "$INSTALL_DIR/$MINER_SCRIPT" "miner"' in script
    assert 'download_file "$RC_FP_URL" "$INSTALL_DIR/fingerprint_checks.py"' in script
    assert 'rustchain_linux_miner.py --wallet' not in script
    assert '$MINER_SCRIPT --wallet' in script
    assert "Downloaded ${label} is empty" in script
