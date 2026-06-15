from pathlib import Path


WIZARD_HTML = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "miner-setup-wizard"
    / "index.html"
)


def test_remote_node_responses_are_rendered_with_text_content():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "function renderCheckOutput(id, badgeText, badgeKind, opts = {})" in html
    assert "el.textContent = text;" in html
    assert "out.replaceChildren(...nodes);" in html
    assert "renderCheckOutput('testOut'" in html
    assert "renderCheckOutput('minerOut'" in html

    assert "document.getElementById('testOut').innerHTML" not in html
    assert "document.getElementById('minerOut').innerHTML" not in html
    assert "<pre>${r.text}</pre>" not in html
    assert "<pre>${JSON.stringify(hit,null,2)}</pre>" not in html
    assert "<pre>${String(e)}</pre>" not in html

    assert "preText: r.text" in html
    assert "preText: JSON.stringify(hit,null,2)" in html
    assert "preText: String(e)" in html


def test_generated_command_blocks_escape_display_and_copy_attribute():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "return `<pre>${cmd}</pre>" not in html
    assert 'onclick="copyText(${JSON.stringify(cmd)})"' not in html

    assert "return `<pre>${h(cmd)}</pre>" in html
    assert 'data-copy="${h(cmd)}" onclick="copyText(this.dataset.copy)"' in html
