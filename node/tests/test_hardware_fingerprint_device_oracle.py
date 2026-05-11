# SPDX-License-Identifier: MIT

import builtins
import os
import sys
from unittest import mock


try:
    import hardware_fingerprint
except ModuleNotFoundError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import hardware_fingerprint


def test_device_oracle_uses_current_year_for_estimated_age():
    cpuinfo = "model name\t: PowerPC G4 7447A\n"

    def fake_open(path, *args, **kwargs):
        if path == "/proc/cpuinfo":
            return mock.mock_open(read_data=cpuinfo)()
        return builtins.open(path, *args, **kwargs)

    with mock.patch.object(hardware_fingerprint.platform, "system", return_value="Linux"), mock.patch.object(
        hardware_fingerprint, "current_utc_year", return_value=2026
    ), mock.patch.object(builtins, "open", side_effect=fake_open):
        oracle = hardware_fingerprint.HardwareFingerprint.collect_device_oracle()

    assert oracle["estimated_release_year"] == 2003
    assert oracle["estimated_age_years"] == 23
