from pathlib import Path


WIZARD_HTML = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "miner-setup-wizard"
    / "index.html"
)


def test_remote_node_responses_are_escaped_before_inner_html_rendering():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "<pre>${r.text}</pre>" not in html
    assert "<pre>${JSON.stringify(hit,null,2)}</pre>" not in html
    assert "<pre>${String(e)}</pre>" not in html

    assert "<pre>${h(r.text)}</pre>" in html
    assert "<pre>${h(JSON.stringify(hit,null,2))}</pre>" in html
    assert "<pre>${h(String(e))}</pre>" in html


def test_generated_command_blocks_escape_display_and_copy_attribute():
    html = WIZARD_HTML.read_text(encoding="utf-8")

    assert "return `<pre>${cmd}</pre>" not in html
    assert 'onclick="copyText(${JSON.stringify(cmd)})"' not in html

    assert "return `<pre>${h(cmd)}</pre>" in html
    assert 'data-copy="${h(cmd)}" onclick="copyText(this.dataset.copy)"' in html
