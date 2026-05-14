# SPDX-License-Identifier: MIT
"""Unit tests for the relic GPU/display badge detector."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "gpu_display_detector.py"


class FixedDateTime:
    @staticmethod
    def utcnow():
        class Stamp:
            @staticmethod
            def isoformat():
                return "2026-05-14T01:25:00"

        return Stamp()


def load_module():
    spec = importlib.util.spec_from_file_location("gpu_display_detector_tool", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_detect_gpu_and_display_writes_matching_badges(tmp_path, monkeypatch, capsys):
    module = load_module()
    monkeypatch.chdir(tmp_path)
    lspci_output = b"3dfx voodoo graphics\nVGA compatible controller: Matrox MGA\n"

    with (
        patch.object(module.subprocess, "check_output", return_value=lspci_output),
        patch.object(module, "datetime", FixedDateTime),
    ):
        module.detect_gpu_and_display()

    payload = json.loads((tmp_path / "unlocked_badges.json").read_text(encoding="utf-8"))
    assert payload == {
        "badges": [
            {"badge_id": "badge_voodoo_fx_g", "awarded_at": "2026-05-14T01:25:00Z"},
            {"badge_id": "badge_matrox_ghost", "awarded_at": "2026-05-14T01:25:00Z"},
            {"badge_id": "badge_vga_ancestor", "awarded_at": "2026-05-14T01:25:00Z"},
        ]
    }
    assert "Unlocked 3 badge(s)" in capsys.readouterr().out


def test_detect_gpu_and_display_does_not_write_when_no_badges(tmp_path, monkeypatch, capsys):
    module = load_module()
    monkeypatch.chdir(tmp_path)

    with patch.object(module.subprocess, "check_output", return_value=b"ethernet controller\n"):
        module.detect_gpu_and_display()

    assert not (tmp_path / "unlocked_badges.json").exists()
    assert "No relic badges detected." in capsys.readouterr().out


def test_detect_gpu_and_display_handles_missing_lspci(tmp_path, monkeypatch, capsys):
    module = load_module()
    monkeypatch.chdir(tmp_path)

    with patch.object(module.subprocess, "check_output", side_effect=FileNotFoundError):
        module.detect_gpu_and_display()

    assert not (tmp_path / "unlocked_badges.json").exists()
    assert "No relic badges detected." in capsys.readouterr().out


def test_detect_gpu_and_display_matches_all_known_relic_terms(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.chdir(tmp_path)
    all_terms = (
        b"voodoo sli ati rage matrox powervr amiga "
        b"hercules cga xga vga compatible"
    )

    with (
        patch.object(module.subprocess, "check_output", return_value=all_terms),
        patch.object(module, "datetime", FixedDateTime),
    ):
        module.detect_gpu_and_display()

    payload = json.loads((tmp_path / "unlocked_badges.json").read_text(encoding="utf-8"))
    assert [entry["badge_id"] for entry in payload["badges"]] == [
        "badge_voodoo_fx_g",
        "badge_voodoo_sli",
        "badge_ati_rage_pro",
        "badge_matrox_ghost",
        "badge_powertile_prophet",
        "badge_amiga_warrior",
        "badge_hercules_monochrome",
        "badge_cga_experiment",
        "badge_xga_rebel",
        "badge_vga_ancestor",
    ]


def test_detect_gpu_and_display_invokes_lspci_without_touching_hardware(tmp_path, monkeypatch):
    module = load_module()
    calls = []
    monkeypatch.chdir(tmp_path)

    def fake_check_output(*args, **kwargs):
        calls.append((args, kwargs))
        return b"matrox powervr"

    with (
        patch.object(module.subprocess, "check_output", side_effect=fake_check_output),
        patch.object(module, "datetime", FixedDateTime),
    ):
        module.detect_gpu_and_display()

    assert calls == [((["lspci"],), {"stderr": module.subprocess.DEVNULL})]
    payload = json.loads((tmp_path / "unlocked_badges.json").read_text(encoding="utf-8"))
    assert [entry["badge_id"] for entry in payload["badges"]] == [
        "badge_matrox_ghost",
        "badge_powertile_prophet",
    ]
