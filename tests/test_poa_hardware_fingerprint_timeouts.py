import importlib.util
from pathlib import Path
import subprocess


def load_hardware_fingerprint():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "rustchain-poa"
        / "validator"
        / "hardware_fingerprint.py"
    )
    spec = importlib.util.spec_from_file_location("poa_hardware_fingerprint", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_darwin_hardware_probe_uses_bounded_command(monkeypatch):
    module = load_hardware_fingerprint()
    calls = []
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")

    def fake_check_output(command, **kwargs):
        calls.append((command, kwargs))
        return b"Hardware UUID: ABC-123\n"

    monkeypatch.setattr(module.subprocess, "check_output", fake_check_output)

    _signature, markers = module.detect_unique_hardware_signature()

    assert markers["hardware_uuid"] == "ABC-123"
    assert calls == [
        (
            ["system_profiler", "SPHardwareDataType"],
            {"stderr": module.subprocess.DEVNULL, "timeout": module.HARDWARE_COMMAND_TIMEOUT},
        )
    ]


def test_linux_hardware_probes_use_bounded_commands(monkeypatch):
    module = load_hardware_fingerprint()
    calls = []
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")

    def fake_check_output(command, **kwargs):
        calls.append((command, kwargs))
        return f"value-for-{command[-1]}\n".encode()

    monkeypatch.setattr(module.subprocess, "check_output", fake_check_output)

    _signature, markers = module.detect_unique_hardware_signature()

    assert markers == {
        "system-serial-number": "value-for-system-serial-number",
        "bios-version": "value-for-bios-version",
        "baseboard-product-name": "value-for-baseboard-product-name",
    }
    assert calls == [
        (
            ["dmidecode", "-s", "system-serial-number"],
            {"stderr": module.subprocess.DEVNULL, "timeout": module.HARDWARE_COMMAND_TIMEOUT},
        ),
        (
            ["dmidecode", "-s", "bios-version"],
            {"stderr": module.subprocess.DEVNULL, "timeout": module.HARDWARE_COMMAND_TIMEOUT},
        ),
        (
            ["dmidecode", "-s", "baseboard-product-name"],
            {"stderr": module.subprocess.DEVNULL, "timeout": module.HARDWARE_COMMAND_TIMEOUT},
        ),
    ]


def test_timeout_preserves_non_crashing_error_marker(monkeypatch):
    module = load_hardware_fingerprint()
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")

    def raise_timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=kwargs["timeout"])

    monkeypatch.setattr(module.subprocess, "check_output", raise_timeout)

    _signature, markers = module.detect_unique_hardware_signature()

    assert "error" in markers
    assert "timed out" in markers["error"]
