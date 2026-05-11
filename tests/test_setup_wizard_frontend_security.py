from pathlib import Path


WIZARD_HTML = Path(__file__).resolve().parents[1] / "web" / "wizard" / "setup-wizard.html"


def test_python_check_failure_escapes_pasted_output():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "Python 3.8+ required. Found: '+(input||'unknown')+'" not in html
    assert "Python 3.8+ required. Found: '+esc(input||'unknown')+'" in html


def test_python_check_success_still_escapes_pasted_output():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "Python '+m[1]+'.'+m[2]+' detected" in html
    assert "&#10003; '+esc(input)+'" in html
