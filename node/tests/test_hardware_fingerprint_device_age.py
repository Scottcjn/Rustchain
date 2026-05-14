# SPDX-License-Identifier: MIT

import io
import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import hardware_fingerprint  # noqa: E402


def test_collect_device_oracle_uses_current_year_for_estimated_age(monkeypatch):
    cpuinfo = "model name\t: PowerPC G4 7447A\n"

    def fake_open(path, *args, **kwargs):
        if path == "/proc/cpuinfo":
            return io.StringIO(cpuinfo)
        raise FileNotFoundError(path)

    monkeypatch.setattr(hardware_fingerprint, "_current_utc_year", lambda: 2026)
    monkeypatch.setattr(hardware_fingerprint.platform, "system", lambda: "Linux")
    monkeypatch.setattr(hardware_fingerprint.platform, "machine", lambda: "ppc")
    monkeypatch.setattr(hardware_fingerprint.platform, "processor", lambda: "PowerPC G4")
    monkeypatch.setattr(hardware_fingerprint.platform, "release", lambda: "test-release")
    monkeypatch.setattr(hardware_fingerprint.platform, "python_version", lambda: "3.test")
    monkeypatch.setattr("builtins.open", fake_open)

    oracle = hardware_fingerprint.HardwareFingerprint.collect_device_oracle()

    assert oracle["estimated_release_year"] == 2003
    assert oracle["estimated_age_years"] == 23
