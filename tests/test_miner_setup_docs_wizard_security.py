from pathlib import Path


WIZARD_HTML = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "miner-setup-wizard"
    / "index.html"
)


def test_remote_node_responses_render_with_dom_text_nodes():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "<pre>${r.text}</pre>" not in html
    assert "<pre>${JSON.stringify(hit,null,2)}</pre>" not in html
    assert "<pre>${String(e)}</pre>" not in html

    assert "function statusPill(label, type)" in html
    assert "status.textContent = label;" in html
    assert "function preText(text)" in html
    assert "pre.textContent = String(text ?? '');" in html
    assert "function renderHealthResult(el, result, url)" in html
    assert "function renderMinerResult(el, hit, error = null)" in html
    assert "renderHealthResult(document.getElementById('testOut'), r, url);" in html
    assert "renderMinerResult(document.getElementById('minerOut'), hit);" in html
    assert "renderMinerResult(document.getElementById('minerOut'), null, e);" in html
    assert "document.getElementById('testOut').innerHTML" not in html
    assert "document.getElementById('minerOut').innerHTML" not in html


def test_generated_command_blocks_escape_display_and_copy_attribute():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "return `<pre>${cmd}</pre>" not in html
    assert 'onclick="copyText(${JSON.stringify(cmd)})"' not in html

    assert "return `<pre>${h(cmd)}</pre>" in html
    assert 'data-copy="${h(cmd)}" onclick="copyText(this.dataset.copy)"' in html
