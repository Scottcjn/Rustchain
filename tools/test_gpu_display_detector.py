# SPDX-License-Identifier: MIT
import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent / "gpu_display_detector.py"
spec = importlib.util.spec_from_file_location("gpu_display_detector", MODULE_PATH)
gpu_display_detector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gpu_display_detector)


class FixedDateTime:
    @staticmethod
    def utcnow():
        class FixedNow:
            @staticmethod
            def isoformat():
                return "2026-05-12T02:00:00"

        return FixedNow()


def test_detect_gpu_and_display_uses_safe_lspci_probe(tmp_path, monkeypatch):
    calls = []

    def fake_check_output(command, **kwargs):
        calls.append((command, kwargs))
        return b"ATI Rage VGA compatible controller"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gpu_display_detector.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(gpu_display_detector, "datetime", FixedDateTime)

    gpu_display_detector.detect_gpu_and_display()

    assert calls == [
        (
            ["lspci"],
            {
                "stderr": gpu_display_detector.subprocess.DEVNULL,
                "timeout": 5,
            },
        )
    ]
    payload = json.loads((tmp_path / "unlocked_badges.json").read_text(encoding="utf-8"))
    assert payload == {
        "badges": [
            {
                "badge_id": "badge_ati_rage_pro",
                "awarded_at": "2026-05-12T02:00:00Z",
            },
            {
                "badge_id": "badge_vga_ancestor",
                "awarded_at": "2026-05-12T02:00:00Z",
            },
        ]
    }
