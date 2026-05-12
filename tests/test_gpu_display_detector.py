# SPDX-License-Identifier: MIT
import importlib.util
import json
from pathlib import Path


def load_detector_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "gpu_display_detector.py"
    spec = importlib.util.spec_from_file_location("gpu_display_detector", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gpu_probe_uses_argument_list(monkeypatch):
    detector = load_detector_module()
    calls = []

    def fake_check_output(args, **kwargs):
        calls.append((args, kwargs))
        return b"VGA compatible controller: 3Dfx Voodoo SLI\n"

    monkeypatch.setattr(detector.subprocess, "check_output", fake_check_output)

    output = detector._read_lspci_output()

    assert "voodoo sli" in output
    assert calls == [(["lspci"], {"stderr": detector.subprocess.DEVNULL, "timeout": 10})]


def test_gpu_badge_detection_writes_expected_badges(monkeypatch, tmp_path):
    detector = load_detector_module()

    def fake_check_output(args, **kwargs):
        return b"VGA compatible controller: Matrox VGA compatible controller\n"

    monkeypatch.setattr(detector.subprocess, "check_output", fake_check_output)
    monkeypatch.chdir(tmp_path)

    detector.detect_gpu_and_display()

    badge_file = tmp_path / "unlocked_badges.json"
    payload = json.loads(badge_file.read_text())

    assert [badge["badge_id"] for badge in payload["badges"]] == [
        "badge_matrox_ghost",
        "badge_vga_ancestor",
    ]
