from pathlib import Path


UI_JS = Path(__file__).resolve().parents[1] / "site" / "beacon" / "ui.js"


def test_beacon_panel_path_uses_text_nodes_for_dynamic_ids():
    js = UI_JS.read_text(encoding="utf-8")

    assert "function setPanelPath(path)" in js
    assert "prompt.textContent = 'beacon@atlas:~';" in js
    assert "panelPath.replaceChildren(prompt, path);" in js

    assert 'panelPath.innerHTML = `<span class="prompt">beacon@atlas:~</span>/agent/${agent.id}`;' not in js
    assert 'panelPath.innerHTML = `<span class="prompt">beacon@atlas:~</span>/city/${city.id}`;' not in js
    assert 'panelPath.innerHTML = `<span class="prompt">beacon@atlas:~</span>/contracts/new`;' not in js
    assert 'panelPath.innerHTML = `<span class="prompt">beacon@atlas:~</span>/bounties`;' not in js

    assert "setPanelPath(`/agent/${agent.id}`);" in js
    assert "setPanelPath(`/city/${city.id}`);" in js
    assert "setPanelPath('/contracts/new');" in js
    assert "setPanelPath('/bounties');" in js
