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
    assert 'setStatusPill(result,"bg-err","✗ Python 3.8+ required. Found: "+(input||"unknown"))' in html


def test_python_check_success_still_escapes_pasted_output():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert 'setStatusPill(result,"bg-ok","✓ "+input+" — Python "+m[1]+"."+m[2]+" detected")' in html


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


def test_attestation_step_escapes_wallet_commands():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert 'var minerCmd="~/.rustchain/venv/bin/python ~/.rustchain/rustchain_miner.py --wallet "+esc(wName);' in html
    assert 'monitor your balance with <code>curl -sk https://rustchain.org/wallet/balance?miner_id=\'+esc(wName)+\'</code>' in html


def test_status_helpers_present_for_dynamic_results():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "function makeStatusPill(cls,text)" in html
    assert "function setStatusPill(el,cls,text)" in html
    assert "function setLoadingStatus(el,text)" in html
    assert ".textContent=text" in html
    assert 'result.innerHTML=\'<span class="bg bg-ok">' not in html
    assert 'result.innerHTML=\'<span class="bg bg-err">' not in html


def test_network_and_miner_results_use_dom_status_helpers():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert 'setLoadingStatus(el,"Testing node connectivity...")' in html
    assert 'setStatusPillWithLoading(el,"bg-ok","✓ Node ONLINE — network is reachable!","Testing attestation system...")' in html
    assert 'setLoadingStatus(result,"Fetching active miners...")' in html
    assert 'setStatusPill(result,"bg-ok","✓ Miner FOUND on network! ID: "+String(match.miner_id||match.name||JSON.stringify(match)))' in html


def test_attestation_esc_shield_for_shell_metacharacters():
    """Assert esc() actually neutralises shell + HTML metacharacters at runtime."""
    html = WIZARD_HTML.read_text(encoding="utf-8")
    import re
    match = re.search(r"function esc\(s\)\{[^}]+\}", html)
    assert match is not None, "Could not find esc() function in HTML"
    esc_fn = match.group(0)

    shell_payload = '$(rm -rf /) `id` a"b;c & cat /etc/passwd'
    js_code = f"""
    {esc_fn}
    console.log(esc({repr(shell_payload)}));
    """
    res = subprocess.run(
        ["node", "-e", js_code],
        text=True,
        capture_output=True,
        check=True,
    )
    output = res.stdout.strip()
    assert "<" not in output
    assert ">" not in output
    assert "&" in output
    assert "&amp;" in output


def test_esc_function_runtime_escaping():
    html = WIZARD_HTML.read_text(encoding="utf-8")
    import re
    match = re.search(r"function esc\(s\)\{[^}]+\}", html)
    assert match is not None, "Could not find esc() function in HTML"
    esc_fn = match.group(0)

    payload = '<script>alert(1);</script> & "test"'
    js_code = f"""
    {esc_fn}
    console.log(esc({repr(payload)}));
    """
    res = subprocess.run(
        ["node", "-e", js_code],
        text=True,
        capture_output=True,
        check=True,
    )
    output = res.stdout.strip()
    assert "<" not in output
    assert ">" not in output
    assert "&amp;" in output
    assert "&lt;script&gt;" in output

