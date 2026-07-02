"""Regression tests for hardware_fingerprint PATH-hijack hardening.

RustChain's Proof-of-Antiquity treats the node operator as the adversary: an
operator on a VM/emulator wants to pass as authentic physical hardware. The
hardware-attestation tools (`dmidecode`, `wmic`, `system_profiler`) must be
resolved only from trusted, root-owned system directories so an operator cannot
shadow them with an attacker-planted binary earlier on PATH.
"""
import importlib.util
from pathlib import Path


def load_hardware_fingerprint():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "rustchain-poa"
        / "validator"
        / "hardware_fingerprint.py"
    )
    spec = importlib.util.spec_from_file_location(
        "poa_hardware_fingerprint", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_trusted_ignores_ambient_path(monkeypatch, tmp_path):
    """A planted binary on PATH must not be resolved: only trusted dirs count."""
    module = load_hardware_fingerprint()

    planted = tmp_path / "dmidecode"
    planted.write_text("#!/bin/sh\necho spoofed\n")
    planted.chmod(0o755)
    # Attacker controls PATH and points it at their planted binary.
    monkeypatch.setenv("PATH", str(tmp_path))

    # Trusted dirs do not contain the tool in this test env, so it must resolve
    # to None rather than to the planted binary.
    monkeypatch.setattr(module, "_TRUSTED_BIN_DIRS", ("/nonexistent-trusted",))

    assert module._resolve_trusted("dmidecode") is None


def test_resolve_trusted_finds_tool_in_trusted_dir(monkeypatch, tmp_path):
    """A tool present in a trusted dir resolves to its absolute path there."""
    module = load_hardware_fingerprint()

    trusted = tmp_path / "trusted"
    trusted.mkdir()
    real = trusted / "dmidecode"
    real.write_text("#!/bin/sh\necho ok\n")
    real.chmod(0o755)

    # Even with an empty/hostile ambient PATH, the trusted dir wins.
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(module, "_TRUSTED_BIN_DIRS", (str(trusted),))

    assert module._resolve_trusted("dmidecode") == str(real)


def test_linux_skips_dmidecode_when_untrusted(monkeypatch, tmp_path):
    """If dmidecode is only reachable via PATH, it is skipped, not executed.

    This proves an operator cannot inject spoofed DMI markers by planting a fake
    dmidecode: no attacker output ever reaches the signature.
    """
    module = load_hardware_fingerprint()

    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(module, "_resolve_trusted", lambda name: None)

    def _fail(*args, **kwargs):  # must never run
        raise AssertionError("subprocess must not be invoked for untrusted tool")

    monkeypatch.setattr(module.subprocess, "check_output", _fail)

    signature, markers = module.detect_unique_hardware_signature()

    # No attacker-controlled markers were collected.
    assert "system-serial-number" not in markers
    assert "error" not in markers
    assert len(signature) == 64  # SHA256 hexdigest still produced


def test_linux_uses_resolved_dmidecode(monkeypatch):
    """When dmidecode resolves in a trusted dir, its output is collected."""
    module = load_hardware_fingerprint()

    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        module, "_resolve_trusted", lambda name: "/usr/sbin/dmidecode"
    )

    def _fake_check_output(command):
        assert command[0] == "/usr/sbin/dmidecode"
        tag = command[-1]
        return ("value-for-" + tag + "\n").encode()

    monkeypatch.setattr(module.subprocess, "check_output", _fake_check_output)

    signature, markers = module.detect_unique_hardware_signature()

    assert markers["system-serial-number"] == "value-for-system-serial-number"
    assert markers["bios-version"] == "value-for-bios-version"
    assert markers["baseboard-product-name"] == "value-for-baseboard-product-name"
    assert len(signature) == 64
