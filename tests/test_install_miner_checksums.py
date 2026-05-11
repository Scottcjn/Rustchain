import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _installer_paths():
    return (
        ROOT / "install-miner.sh",
        ROOT / "miners" / "windows" / "install-miner.sh",
    )


def test_install_miners_verify_fingerprint_helper_checksum():
    for installer in _installer_paths():
        text = installer.read_text()
        assert 'FINGERPRINT_FILE="linux/fingerprint_checks.py"' in text
        assert 'run_cmd curl -sSL "$REPO_BASE/$FINGERPRINT_FILE" -o fingerprint_checks.py' in text
        assert '"$FINGERPRINT_FILE:fingerprint_checks.py"' in text
        assert 'verify_sum "$local_path" "$SUM"' in text


def test_install_miners_require_manifest_entries_before_verification():
    for installer in _installer_paths():
        text = installer.read_text()
        checksum_block = text.partition('curl -sSL "$CHECKSUM_URL" -o sums')[2].partition("fi")[0]
        assert 'curl -sSL "$CHECKSUM_URL" -o sums' in text
        assert 'Missing checksum for: $manifest_path' in text
        assert 'grep "$(basename $FILE)"' not in text
        assert "|| true" not in checksum_block


def test_checksum_manifest_covers_installer_downloads():
    manifest = (ROOT / "miners" / "checksums.sha256").read_text()
    assert "linux/fingerprint_checks.py" in manifest
    for installer in _installer_paths():
        for miner_path in re.findall(r'\)\s+FILE="([^"]+)"\s+;;', installer.read_text()):
            assert miner_path in manifest
