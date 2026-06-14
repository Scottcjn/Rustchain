# SPDX-License-Identifier: MIT
from pathlib import Path


JS_PATH = Path(__file__).resolve().parents[1] / "site" / "beacon" / "ui.js"


def test_panel_path_uses_dom_text_nodes():
    source = JS_PATH.read_text(encoding="utf-8")

    assert "function setPanelPath(path)" in source
    assert "prompt.textContent = 'beacon@atlas:~';" in source
    assert "panelPath.replaceChildren(prompt, document.createTextNode(String(path ?? '')));" in source
    assert "setPanelPath(`/agent/${agent.id}`);" in source
    assert "setPanelPath(`/city/${city.id}`);" in source
    assert "setPanelPath('/contracts/new');" in source
    assert "setPanelPath('/bounties');" in source


def test_panel_path_avoids_inner_html_parser_sink():
    source = JS_PATH.read_text(encoding="utf-8")

    assert "panelPath.innerHTML" not in source
    assert '<span class="prompt">beacon@atlas:~</span>/agent/${agent.id}' not in source
    assert '<span class="prompt">beacon@atlas:~</span>/city/${city.id}' not in source
