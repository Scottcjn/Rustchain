import shutil
import subprocess
from pathlib import Path

import pytest

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


def test_installer_fails_loudly_on_unsupported_os():
    script = INSTALLER.read_text(encoding="utf-8")
    assert "Unsupported OS" in script
    assert "supports Linux and macOS only" in script
    # The gate must run before any download/install work happens.
    gate_pos = script.index("Unsupported OS")
    download_pos = script.index("Downloading miner files")
    assert gate_pos < download_pos


def test_installer_creates_install_dir_with_sudo_for_non_root_users():
    # /opt is root-owned on Linux and macOS: a bare mkdir -p dies mid-install
    # on a non-root Mac (Scottcjn/Rustchain#7975 follow-up).
    script = INSTALLER.read_text(encoding="utf-8")
    assert 'sudo mkdir -p "${INSTALL_DIR}"' in script
    assert 'if [ "$(id -u)" -ne 0 ] && command -v sudo &>/dev/null; then' in script


def test_installer_download_fallbacks_point_at_repo_paths_not_site_root():
    # rustchain.org serves no per-file .py copies, so every
    # https://rustchain.org/<file>.py fallback 404'd (Scottcjn/Rustchain#7975).
    script = INSTALLER.read_text(encoding="utf-8")
    for dead in (
        "https://rustchain.org/rustchain_linux_miner.py",
        "https://rustchain.org/fingerprint_checks.py",
        "https://rustchain.org/color_logs.py",
        "https://rustchain.org/miner_crypto.py",
    ):
        assert dead not in script
    assert 'MIRROR_RAW="https://cdn.jsdelivr.net/gh/Scottcjn/Rustchain@main"' in script
    assert "${MIRROR_RAW}/miners/" in script


def test_installer_avoids_gnu_only_and_bash4_constructs():
    # macOS ships bash 3.2 and BSD userland: no associative arrays, no GNU flags.
    script = INSTALLER.read_text(encoding="utf-8")
    for construct in (
        "declare -A",
        "sed -i ",
        "readlink -f",
        "grep -P",
        "grep -oP",
        "mapfile",
        "readarray",
        "stat -c",
        "date -d ",
    ):
        assert construct not in script, f"non-portable construct: {construct!r}"


def test_python_probes_return_only_the_interpreter_path_on_stdout():
    # Callers do `py=$(ensure_python)`: any status line printed to stdout
    # lands inside $py and breaks every later "$py" invocation plus the
    # systemd/launchd unit's ProgramArguments (macOS miner never starts).
    script = INSTALLER.read_text(encoding="utf-8")
    for name in ("ensure_python", "ensure_pip_deps"):
        body = script.split(f"{name}() {{")[1].split("\n}")[0]
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith(("ok ", "info ", "warn ")) and not stripped.startswith("#"):
                assert stripped.endswith(">&2"), (
                    f"{name}: status message leaks into $() capture: {stripped!r}"
                )


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck not installed")
def test_installer_is_shellcheck_clean():
    result = subprocess.run(
        ["shellcheck", str(INSTALLER)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout
