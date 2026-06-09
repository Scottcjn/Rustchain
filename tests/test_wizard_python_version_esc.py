from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "web" / "wizard" / "setup-wizard.html").read_text(encoding="utf-8")


def test_python_version_is_escaped_in_config():
    assert "esc(S.pythonVersion" in HTML


def test_esc_helper_exists():
    assert "function esc(s)" in HTML
    assert 's.replace(/&/g,"&amp;")' in HTML
