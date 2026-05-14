# SPDX-License-Identifier: MIT
"""Unit tests for the BCOS badge generator validator."""

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "validate_bcos_generator.py"


VALID_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BCOS Badge Generator</title>
<style>
:root { --term-green: #00ff00; }
.terminal-window { color: var(--term-green); }
.terminal-header { font-family: 'Courier New', monospace; }
.ascii-art { white-space: pre; }
</style>
</head>
<body>
<form id="badgeForm">
<input id="certId">
<select id="inputType"></select>
<button data-style="flat"></button>
<button data-style="flat-square"></button>
<button data-style="for-the-badge"></button>
</form>
<div id="previewArea"></div>
<textarea id="markdownCode">[![BCOS](https://badge.example/bcos.svg)](https://verify.example/cert)</textarea>
<textarea id="htmlCode"><img src="https://badge.example/bcos.svg" alt="BCOS badge"></textarea>
<script>
const BADGE_ENDPOINT = "/badge";
const VERIFY_BASE_URL = "https://verify.example";
async function generateBadge() { return true; }
function generateEmbedCodes() { return true; }
</script>
</body>
</html>
"""


def load_module():
    spec = importlib.util.spec_from_file_location("validate_bcos_generator_tool", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_html(tmp_path, content=VALID_HTML, name="index.html"):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_file_checks_report_existing_and_minimum_size(tmp_path, capsys):
    module = load_module()
    path = write_html(tmp_path)

    assert module.check_file_exists(str(path)) is True
    assert module.check_file_size(str(path), min_size=100) is True
    assert module.check_file_exists(str(tmp_path / "missing.html")) is False

    output = capsys.readouterr().out
    assert "File exists" in output
    assert "File size" in output


def test_html_structure_and_required_components_pass_for_valid_page(tmp_path):
    module = load_module()
    path = write_html(tmp_path)

    assert module.check_html_structure(str(path)) is True
    assert module.check_required_components(str(path)) is True


def test_html_structure_reports_missing_required_elements(tmp_path):
    module = load_module()
    path = write_html(tmp_path, "<html><body>No metadata</body></html>")

    assert module.check_html_structure(str(path)) is False
    assert module.check_required_components(str(path)) is False


def test_javascript_and_css_syntax_checks_detect_balance(tmp_path):
    module = load_module()
    valid_path = write_html(tmp_path)
    invalid_path = write_html(
        tmp_path,
        "<html><head><style>.broken { color: red; </style></head>"
        "<body><script>function broken( { return true; }</script></body></html>",
        name="invalid.html",
    )

    assert module.check_javascript_syntax(str(valid_path)) is True
    assert module.check_css_syntax(str(valid_path)) is True
    assert module.check_javascript_syntax(str(invalid_path)) is False
    assert module.check_css_syntax(str(invalid_path)) is False


def test_embed_and_terminal_aesthetic_checks(tmp_path):
    module = load_module()
    valid_path = write_html(tmp_path)
    plain_path = write_html(
        tmp_path,
        "<html><head><style>body { color: black; }</style></head>"
        "<body><script>const ok = true;</script></body></html>",
        name="plain.html",
    )

    assert module.check_embed_format(str(valid_path)) is True
    assert module.check_terminal_aesthetic(str(valid_path)) is True
    assert module.check_embed_format(str(plain_path)) is False
    assert module.check_terminal_aesthetic(str(plain_path)) is False
