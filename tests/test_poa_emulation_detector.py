import importlib.util
from pathlib import Path
from subprocess import CalledProcessError


def load_emulation_detector():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "rustchain-poa"
        / "validator"
        / "emulation_detector.py"
    )
    spec = importlib.util.spec_from_file_location("poa_emulation_detector", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_detect_emulation_flags_linux_virtualization(monkeypatch):
    module = load_emulation_detector()
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        module.subprocess,
        "check_output",
        lambda command: b"docker\n",
    )

    result = module.detect_emulation()

    assert result == {
        "flags": ["Detected virtualization: docker"],
        "score": 50,
        "likely_emulated": True,
    }


def test_detect_emulation_treats_none_as_physical_linux(monkeypatch):
    module = load_emulation_detector()
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        module.subprocess,
        "check_output",
        lambda command: b"none\n",
    )

    assert module.detect_emulation() == {
        "flags": [],
        "score": 0,
        "likely_emulated": False,
    }


def test_detect_emulation_ignores_failed_detection_command(monkeypatch):
    module = load_emulation_detector()
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")

    def raise_error(command):
        raise CalledProcessError(returncode=1, cmd=command)

    monkeypatch.setattr(module.subprocess, "check_output", raise_error)

    assert module.detect_emulation() == {
        "flags": [],
        "score": 0,
        "likely_emulated": False,
    }


def test_detect_emulation_skips_virtualization_command_off_linux(monkeypatch):
    module = load_emulation_detector()
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")

    def fail_if_called(command):
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(module.subprocess, "check_output", fail_if_called)

    assert module.detect_emulation() == {
        "flags": [],
        "score": 0,
        "likely_emulated": False,
    }
