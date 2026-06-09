from pathlib import Path


PY = (Path(__file__).resolve().parents[1] / "tools" / "bcos_badge_generator.py").read_text(encoding="utf-8")


def test_esc_helper_exists():
    assert "function esc(v)" in PY


def test_safe_svg_helper_exists():
    assert "function safeSvg(svgString)" in PY
    assert "DOMParser" in PY
    assert "querySelectorAll('script')" in PY


def test_svg_innerhtml_replaced():
    assert "badgePreview.innerHTML = data.svg" not in PY
    assert "safeSvg(data.svg)" in PY


def test_verify_fields_escaped():
    assert "esc(data.data.repo_name)" in PY
    assert "esc(data.data.tier)" in PY
    assert "esc(data.data.reviewer)" in PY


def test_no_raw_verify_interpolation():
    assert "data.data.repo_name}<br>" not in PY
    assert "data.data.tier}<br>" not in PY
