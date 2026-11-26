# SPDX-License-Identifier: MIT
"""Guard tests for the NetBSD miner port (bounty #12788).

These mirror tests/test_freebsd_installer_artifacts.py and additionally pin
the honest-attestation contract for the NetBSD client:

* the installer only fetches artifacts that actually exist in the repo and
  verifies their SHA-256 against the published manifest
* the netbsd client is present in the manifest with a hash that matches the
  committed file
* the netbsd client probes hardware via NetBSD sysctl keys
* the netbsd client refuses to run on non-NetBSD systems
* the platform README leads with the verify-before-trust commands

All checks are text/artifact based so they run on any CI OS (the miner
itself only runs on NetBSD, by design).
"""
import ast
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install-miner-netbsd.sh"
NETBSD_MINER = ROOT / "miners" / "netbsd" / "rustchain_netbsd_miner.py"
NETBSD_README = ROOT / "miners" / "netbsd" / "README.md"
MANIFEST = ROOT / "miners" / "checksums.sha256"
REPO_BASE_RE = re.compile(r"\$\{REPO_BASE\}/([A-Za-z0-9_./-]+)")


def test_netbsd_installer_exists():
    assert INSTALLER.is_file(), "install-miner-netbsd.sh missing"


def test_netbsd_installer_downloads_existing_artifacts():
    script = INSTALLER.read_text(encoding="utf-8")
    referenced = set(REPO_BASE_RE.findall(script))
    assert referenced, "installer references no ${REPO_BASE} artifacts"
    for rel in referenced:
        if rel == "checksums.sha256":
            assert (ROOT / "miners" / rel).is_file()
            continue
        assert (ROOT / "miners" / rel).is_file(), f"installer fetches missing miners/{rel}"
    # The dead-path regression from the FreeBSD port must not come back.
    assert "miners/rustchain_miner.py" not in script
    # The installer must fetch the NetBSD-native client, not only the Linux one.
    assert "netbsd/rustchain_netbsd_miner.py" in referenced


def test_netbsd_installer_verifies_checksums():
    script = INSTALLER.read_text(encoding="utf-8")
    assert "checksums.sha256" in script
    assert "verify_sum" in script
    # NetBSD base sha256 tool is cksum -a sha256, not FreeBSD's sha256 -q.
    assert "cksum -a sha256" in script


def test_netbsd_installer_refuses_non_netbsd():
    script = INSTALLER.read_text(encoding="utf-8")
    assert 'kern.ostype' in script
    assert '!= "NetBSD"' in script


def test_netbsd_installer_offers_verify_before_trust_modes():
    script = INSTALLER.read_text(encoding="utf-8")
    for mode in ("--dry-run", "--show-payload", "--test-only"):
        assert f'"{mode}"' in script, f"installer is missing {mode}"


def test_netbsd_miner_exists_and_parses():
    source = NETBSD_MINER.read_text(encoding="utf-8")
    ast.parse(source)  # syntax gate: the client must be importable Python


def test_netbsd_miner_probes_sysctl_keys():
    source = NETBSD_MINER.read_text(encoding="utf-8")
    for key in ("machdep.cpu_model", "hw.machine", "hw.ncpuonline", "hw.physmem64"):
        assert key in source, f"netbsd miner missing sysctl probe for {key}"
    # The Linux miner's fabricated-default probes must not be used silently:
    # check for actual command invocations, not docstring mentions.
    assert '"lscpu"' not in source
    assert "'nproc'" not in source


def test_netbsd_miner_refuses_non_netbsd():
    source = NETBSD_MINER.read_text(encoding="utf-8")
    assert "assert_netbsd_platform" in source
    assert '!= "NetBSD"' in source
    assert "fabricate" in source.lower()


def test_netbsd_miner_listed_in_manifest_with_matching_hash():
    """The installer-verified manifest entry must match the committed file.

    Hash comparison is newline-normalized so the test is correct both on
    LF checkouts (CI) and CRLF checkouts (some developer machines).
    """
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    m = re.search(r"^([0-9a-f]{64})\s+netbsd/rustchain_netbsd_miner\.py$", manifest_text, re.M)
    assert m, "netbsd/rustchain_netbsd_miner.py missing from miners/checksums.sha256"
    raw = NETBSD_MINER.read_bytes().replace(b"\r\n", b"\n")
    actual = hashlib.sha256(raw).hexdigest()
    assert actual == m.group(1), (
        "miners/checksums.sha256 is stale for netbsd/rustchain_netbsd_miner.py "
        f"(manifest {m.group(1)} != file {actual})"
    )


def test_netbsd_readme_leads_with_verify_before_trust():
    text = NETBSD_README.read_text(encoding="utf-8")
    # The first section after the title must be the verification guide.
    first_section = text.split("## ", 2)[1]
    assert first_section.lower().startswith("verify before trust")
    for mode in ("--dry-run", "--show-payload", "--test-only"):
        assert mode in text, f"README does not document {mode}"
