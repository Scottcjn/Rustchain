# SPDX-License-Identifier: MIT
"""Guard: the FreeBSD installer must reference miner artifacts that actually
exist in the repo and verify them. The original installer fetched a
non-existent miners/rustchain_miner.py (HTTP 404), silently breaking the port.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install-miner-freebsd.sh"
REPO_BASE_RE = re.compile(r'\$\{REPO_BASE\}/([A-Za-z0-9_./-]+)')


def test_freebsd_installer_exists():
    assert INSTALLER.is_file(), "install-miner-freebsd.sh missing"


def test_freebsd_installer_downloads_existing_artifacts():
    script = INSTALLER.read_text(encoding="utf-8")

    # The dead path that used to 404 must not come back.
    assert "miners/rustchain_miner.py" not in script

    # Every ${REPO_BASE}/<path> the installer curls (except the checksum
    # manifest, which lives at miners/checksums.sha256) must exist under miners/.
    referenced = set(REPO_BASE_RE.findall(script))
    assert referenced, "installer references no ${REPO_BASE} artifacts"
    for rel in referenced:
        if rel == "checksums.sha256":
            assert (ROOT / "miners" / rel).is_file()
            continue
        assert (ROOT / "miners" / rel).is_file(), f"installer fetches missing miners/{rel}"


def test_freebsd_installer_verifies_checksums():
    script = INSTALLER.read_text(encoding="utf-8")
    # Verify-before-trust: it must pull the manifest and check hashes.
    assert "checksums.sha256" in script
    assert "verify_sum" in script
