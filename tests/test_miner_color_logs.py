from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
COLOR_LOG_MODULES = [
    REPO_ROOT / "miners" / "color_logs.py",
    REPO_ROOT / "miners" / "linux" / "color_logs.py",
    REPO_ROOT / "miners" / "macos" / "color_logs.py",
    REPO_ROOT / "miners" / "windows" / "color_logs.py",
]


@pytest.fixture(params=COLOR_LOG_MODULES, ids=lambda path: str(path.relative_to(REPO_ROOT)))
def color_logs(request):
    module_path = request.param
    module_name = "test_" + "_".join(module_path.relative_to(REPO_ROOT).with_suffix("").parts)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_should_color_respects_no_color(color_logs, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert color_logs.should_color() is True

    monkeypatch.setenv("NO_COLOR", "1")
    assert color_logs.should_color() is False


def test_colorize_wraps_known_colors(color_logs, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)

    assert color_logs.colorize("ready", "green") == "\033[32mready\033[0m"


def test_colorize_leaves_unknown_or_disabled_output_plain(color_logs, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert color_logs.colorize("ready", "unknown") == "ready"

    monkeypatch.setenv("NO_COLOR", "1")
    assert color_logs.colorize("ready", "green") == "ready"


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        ("info", "\033[36mevent\033[0m"),
        ("warning", "\033[33mevent\033[0m"),
        ("error", "\033[31mevent\033[0m"),
        ("success", "\033[32mevent\033[0m"),
        ("debug", "\033[90mevent\033[0m"),
        ("trace", "event"),
    ],
)
def test_colorize_level_maps_known_levels(color_logs, monkeypatch, level, expected):
    monkeypatch.delenv("NO_COLOR", raising=False)

    assert color_logs.colorize_level("event", level) == expected


@pytest.mark.parametrize(
    ("helper", "expected"),
    [
        ("info", "\033[36mmessage\033[0m"),
        ("warning", "\033[33mmessage\033[0m"),
        ("error", "\033[31mmessage\033[0m"),
        ("success", "\033[32mmessage\033[0m"),
        ("debug", "\033[90mmessage\033[0m"),
    ],
)
def test_convenience_helpers_apply_expected_colors(color_logs, monkeypatch, helper, expected):
    monkeypatch.delenv("NO_COLOR", raising=False)

    assert getattr(color_logs, helper)("message") == expected


def test_print_colored_uses_level_and_kwargs(color_logs, monkeypatch, capsys):
    monkeypatch.delenv("NO_COLOR", raising=False)

    color_logs.print_colored("hello", level="error", end="!")

    assert capsys.readouterr().out == "\033[31mhello\033[0m!"


def test_print_colored_plain_without_level(color_logs, capsys):
    color_logs.print_colored("hello")

    assert capsys.readouterr().out == "hello\n"
