# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path


def load_detector_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "bios_pawpaw_detector.py"
    spec = importlib.util.spec_from_file_location("bios_pawpaw_detector", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_windows_bios_query_uses_argument_list(monkeypatch):
    detector = load_detector_module()
    calls = []

    def fake_check_output(args, **kwargs):
        calls.append((args, kwargs))
        return b"ReleaseDate\r\n19890304000000.000000+000\r\n"

    monkeypatch.setattr(detector.platform, "system", lambda: "Windows")
    monkeypatch.setattr(detector.subprocess, "check_output", fake_check_output)

    bios_date = detector.get_bios_date()

    assert bios_date.year == 1989
    assert calls == [(["wmic", "bios", "get", "releasedate"], {"stderr": detector.subprocess.DEVNULL, "timeout": 10})]


def test_linux_bios_query_uses_argument_list(monkeypatch):
    detector = load_detector_module()
    calls = []

    def fake_check_output(args, **kwargs):
        calls.append((args, kwargs))
        return b"BIOS Information\n\tRelease Date: 03/15/2011\n"

    monkeypatch.setattr(detector.platform, "system", lambda: "Linux")
    monkeypatch.setattr(detector.subprocess, "check_output", fake_check_output)

    bios_date = detector.get_bios_date()

    assert bios_date.year == 2011
    assert calls == [(["dmidecode", "-t", "bios"], {"stderr": detector.subprocess.DEVNULL, "timeout": 10})]


def test_bios_query_failure_returns_none(monkeypatch):
    detector = load_detector_module()

    def fake_check_output(args, **kwargs):
        raise FileNotFoundError(args[0])

    monkeypatch.setattr(detector.platform, "system", lambda: "Linux")
    monkeypatch.setattr(detector.subprocess, "check_output", fake_check_output)

    assert detector.get_bios_date() is None
