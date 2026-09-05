# SPDX-License-Identifier: MIT
"""Regression guard for issue #5713.

`miners/linux/rustchain_linux_miner.py` takes the wallet only from the
``--wallet`` CLI argument and falls back to ``LocalMiner._gen_wallet()`` when it
is absent.  A generated service that merely exports ``WALLET_NAME`` /
``RUSTCHAIN_WALLET`` into the environment therefore mines under a throwaway
wallet, so rewards and balance checks never line up with the wallet the user
entered during setup.

The templates in ``setup.sh`` and ``scripts/install.sh`` were corrected in
PR #5711 to pass the wallet explicitly.  These tests lock that in for all four
generated units (systemd + launchd, in both scripts) so the environment-only
form cannot come back.
"""

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SETUP_SH = REPO_ROOT / "setup.sh"
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"

# Substrings that identify an invocation of the miner entry point inside a
# generated unit, independent of the shell variable names used by each script.
MINER_INVOCATION_HINTS = ("MINER_SCRIPT", "MINER_FILENAME", "rustchain_linux_miner.py")


def _miner_exec_start_lines(script: str) -> list[str]:
    """systemd ``ExecStart=`` lines that launch the miner entry point."""
    return [
        line.strip()
        for line in script.splitlines()
        if line.strip().startswith("ExecStart=")
        and any(hint in line for hint in MINER_INVOCATION_HINTS)
    ]


def _launchd_program_arguments(script: str) -> list[str]:
    """Bodies of every ``<array>`` that follows a ``ProgramArguments`` key."""
    pattern = re.compile(
        r"<key>ProgramArguments</key>\s*<array>(.*?)</array>", re.DOTALL
    )
    return [match.group(1) for match in pattern.finditer(script)]


def _plist_strings(array_body: str) -> list[str]:
    return re.findall(r"<string>(.*?)</string>", array_body, re.DOTALL)


def _assert_systemd_passes_wallet(path: Path) -> None:
    script = path.read_text(encoding="utf-8")
    exec_starts = _miner_exec_start_lines(script)
    assert exec_starts, f"{path.name} no longer generates a systemd ExecStart for the miner"
    for line in exec_starts:
        assert "--wallet" in line, (
            f"{path.name} systemd ExecStart does not pass the configured wallet "
            f"(issue #5713): {line}"
        )


def _assert_launchd_passes_wallet(path: Path) -> None:
    script = path.read_text(encoding="utf-8")
    arrays = _launchd_program_arguments(script)
    assert arrays, f"{path.name} no longer generates a launchd ProgramArguments array"
    for body in arrays:
        args = _plist_strings(body)
        assert "--wallet" in args, (
            f"{path.name} launchd ProgramArguments does not pass the configured "
            f"wallet (issue #5713): {args}"
        )
        wallet_value = args[args.index("--wallet") + 1]
        assert wallet_value.strip(), (
            f"{path.name} launchd ProgramArguments passes an empty --wallet value"
        )


def test_setup_sh_systemd_unit_passes_wallet():
    _assert_systemd_passes_wallet(SETUP_SH)


def test_setup_sh_launchd_plist_passes_wallet():
    _assert_launchd_passes_wallet(SETUP_SH)


def test_install_sh_systemd_unit_passes_wallet():
    _assert_systemd_passes_wallet(INSTALL_SH)


def test_install_sh_launchd_plist_passes_wallet():
    _assert_launchd_passes_wallet(INSTALL_SH)


def test_miner_wallet_is_not_supplied_by_environment_alone():
    """Exporting the wallet without ``--wallet`` is the exact #5713 regression."""
    for path in (SETUP_SH, INSTALL_SH):
        script = path.read_text(encoding="utf-8")
        exports_wallet_env = bool(
            re.search(r'Environment="(?:WALLET_NAME|RUSTCHAIN_WALLET)=', script)
        )
        if not exports_wallet_env:
            continue
        assert "--wallet" in script, (
            f"{path.name} exports a wallet environment variable but never passes "
            f"--wallet; the miner would fall back to a generated wallet (#5713)"
        )
