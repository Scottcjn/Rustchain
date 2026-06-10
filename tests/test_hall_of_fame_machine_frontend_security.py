# SPDX-License-Identifier: MIT
from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "web" / "hall-of-fame" / "machine.html"


def source():
    return PAGE.read_text(encoding="utf-8")


def test_machine_profile_renders_timeline_with_text_nodes():
    html = source()

    assert "function safeInt(v)" in html
    assert "function safeScore(v)" in html
    assert "function renderTimeline(timeline,machine)" in html
    assert "function appendTextCell(row,value,colSpan)" in html
    assert "appendTextCell(row,x.date||'—');" in html
    assert "appendTextCell(row,safeInt(x.attestations??x.samples??0));" in html
    assert "appendTextCell(row,safeScore(x.rust_score??machine.rust_score??'—'));" in html
    assert "body.replaceChildren(...rows);" in html

    assert "document.getElementById('timeline').innerHTML" not in html
    assert "t.map(x=>`<tr><td>" not in html


def test_machine_profile_status_messages_use_dom_text():
    html = source()

    assert "function setStatusMessage(message,className)" in html
    assert "span.textContent=String(message||'');" in html
    assert "status.replaceChildren(span);" in html
    assert "setStatusMessage('Missing machine id. Use ?id=<fingerprint_hash>.','err');" in html
    assert "setStatusMessage('Not found or unavailable.','err');" in html
    assert "document.getElementById('status').innerHTML" not in html
