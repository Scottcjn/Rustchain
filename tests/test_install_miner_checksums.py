import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKSUMS = ROOT / "miners" / "checksums.sha256"
INSTALLERS = [
    ROOT / "install-miner.sh",
    ROOT / "miners" / "windows" / "install-miner.sh",
]


def _checksum_entries():
    entries = {}
    for line in CHECKSUMS.read_text(encoding="utf-8").splitlines():
        digest, artifact = line.split(maxsplit=1)
        entries[artifact] = digest
    return entries


def test_checksum_manifest_matches_installer_download_artifacts():
    entries = _checksum_entries()

    for artifact in [
        "linux/rustchain_linux_miner.py",
        "linux/fingerprint_checks.py",
        "macos/rustchain_mac_miner_v2.4.py",
        "macos/rustchain_mac_miner_v2.5.py",
    ]:
        expected = hashlib.sha256((ROOT / "miners" / artifact).read_bytes()).hexdigest()
        assert entries[artifact] == expected


def test_installers_verify_fingerprint_helper_checksum():
    for installer in INSTALLERS:
        script = installer.read_text(encoding="utf-8")

        assert 'MINER_SUM=$(checksum_for "$FILE")' in script
        assert 'FINGERPRINT_SUM=$(checksum_for "linux/fingerprint_checks.py")' in script
        assert 'verify_sum "rustchain_miner.py" "$MINER_SUM"' in script
        assert 'verify_sum "fingerprint_checks.py" "$FINGERPRINT_SUM"' in script
        assert 'curl -fsSL "$CHECKSUM_URL" -o sums' in script
        assert 'grep "$(basename $FILE)"' not in script
        assert 'curl -sSL "$CHECKSUM_URL" -o sums 2>/dev/null || true' not in script
