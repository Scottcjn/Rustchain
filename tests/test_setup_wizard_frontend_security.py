from pathlib import Path
import subprocess
from html.parser import HTMLParser


WIZARD_HTML = Path(__file__).resolve().parents[1] / "web" / "wizard" / "setup-wizard.html"


class ScriptCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self._active = False
        self._current = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag != "script":
            return
        attrs = dict(attrs)
        script_type = attrs.get("type", "").lower()
        if script_type in {"", "text/javascript", "application/javascript"}:
            self._active = True
            self._current = []

    def handle_data(self, data):
        if self._active:
            self._current.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._active:
            self.scripts.append("".join(self._current))
            self._active = False


def test_embedded_javascript_parses():
    parser = ScriptCollector()
    parser.feed(WIZARD_HTML.read_text(encoding="utf-8"))

    assert parser.scripts
    for script in parser.scripts:
        subprocess.run(
            ["node", "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"],
            input=script,
            text=True,
            check=True,
        )


def test_python_check_failure_escapes_pasted_output():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "Python 3.8+ required. Found: '+(input||'unknown')+'" not in html
    assert "Python 3.8+ required. Found: '+esc(input||'unknown')+'" in html


def test_python_check_success_still_escapes_pasted_output():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "Python '+m[1]+'.'+m[2]+' detected" in html
    assert "&#10003; '+esc(input)+'" in html


def test_setup_wizard_renders_connection_check():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "function renderTest(el)" in html
    assert "onclick=\"testConnection()\"" in html
    assert "id=\"netResult\"" in html
    assert "id=\"attResult\"" in html


def test_miner_check_accepts_paginated_miners_response():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "var miners=Array.isArray(data)?data:(data&&Array.isArray(data.miners)?data.miners:[]);" in html
    assert "for(var i=0;i<miners.length;i++)" in html
