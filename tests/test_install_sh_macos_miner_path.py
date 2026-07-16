# SPDX-License-Identifier: MIT
"""
Test for issue #7975: install script at rustchain.org has wrong file paths and crashes on macOS.

The root install.sh (served at rustchain.org/install.sh) must reference the current
macOS miner version that exists on disk. Previously it pointed to v2.4 which was
outdated, causing crashes on macOS installations.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = ROOT / "install.sh"


def test_macos_miner_version_matches_disk():
    """install.sh macOS MINER_PATH must match an actual file on disk."""
    script = INSTALL_SH.read_text(encoding="utf-8")

    # Extract the macOS miner path used by install.sh
    assert 'macos/rustchain_mac_miner_v2.5.py' in script, (
        "install.sh should reference rustchain_mac_miner_v2.5.py for macOS "
        "(issue #7975: v2.4 was outdated)"
    )

    # Verify the referenced file actually exists
    macos_miner_path = ROOT / "miners" / "macos" / "rustchain_mac_miner_v2.5.py"
    assert macos_miner_path.exists(), (
        f"Referenced macOS miner file does not exist: {macos_miner_path}"
    )


def test_macos_miner_not_referencing_stale_version():
    """install.sh must NOT reference the stale v2.4 macOS miner."""
    script = INSTALL_SH.read_text(encoding="utf-8")
    # The only miner path references should be v2.5, not v2.4
    assert 'macos/rustchain_mac_miner_v2.4.py' not in script, (
        "install.sh should not reference stale v2.4 macOS miner (issue #7975)"
    )


def test_fingerprint_path_consistent():
    """fingerprint_checks.py path must be consistent in both code paths (dry-run + main)."""
    script = INSTALL_SH.read_text(encoding="utf-8")

    # Both the dry-run block (inside if DRY_RUN) and main block should use same fingerprint path
    fingerprint_refs = [
        line.strip() for line in script.splitlines()
        if 'FINGERPRINT_PATH' in line and 'macos/fingerprint_checks.py' in line
    ]

    assert len(fingerprint_refs) >= 2, (
        f"Expected at least 2 FINGERPRINT_PATH assignments for macOS, found {len(fingerprint_refs)}"
    )
    # All fingerprint refs should be identical
    unique_refs = set(fingerprint_refs)
    assert len(unique_refs) == 1, (
        f"FINGERPRINT_PATH values differ between code paths: {unique_refs}"
    )
