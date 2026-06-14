import re
from pathlib import Path


WIZARD_HTML = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "miner-setup-wizard"
    / "index.html"
)


def test_remote_node_results_use_text_dom_rendering():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "document.getElementById('testOut').innerHTML = r.ok" not in html
    assert "document.getElementById('minerOut').innerHTML = hit" not in html
    assert "document.getElementById('minerOut').innerHTML = `<span class='pill bad'>" not in html
    assert not re.search(r"(?:testOut|minerOut)['\"]\)\.innerHTML\s*=", html)

    assert "function renderStatusResult(target, statusClass, label, bodyText, helpText)" in html
    assert "target.replaceChildren(...children);" in html
    assert "el.textContent = String(text);" in html
    assert "renderStatusResult(out, 'ok', 'Reachable', r.text);" in html
    assert "renderStatusResult(out, 'ok', 'Found', JSON.stringify(hit, null, 2));" in html
    assert "renderStatusResult(document.getElementById('minerOut'), 'bad', 'Check failed', String(e));" in html


def test_generated_command_blocks_escape_display_and_copy_attribute():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "return `<pre>${cmd}</pre>" not in html
    assert 'onclick="copyText(${JSON.stringify(cmd)})"' not in html

    assert "return `<pre>${h(cmd)}</pre>" in html
    assert 'data-copy="${h(cmd)}" onclick="copyText(this.dataset.copy)"' in html
