from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP_SH = ROOT / "setup.sh"


def test_setup_sh_uses_existing_linux_miner_paths():
    script = SETUP_SH.read_text(encoding="utf-8")

    assert 'RC_MINER_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/linux/rustchain_linux_miner.py"' in script
    assert 'RC_FP_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/linux/fingerprint_checks.py"' in script


def test_setup_sh_fails_fast_when_downloads_fail():
    script = SETUP_SH.read_text(encoding="utf-8")

    assert "curl -fsSL --proto '=https' --tlsv1.2" in script
    assert "wget -q --https-only" in script
    assert 'download_file "$RC_MINER_URL"' in script
    assert 'download_file "$RC_FP_URL"' in script
    assert "Downloaded ${label} is empty" in script
