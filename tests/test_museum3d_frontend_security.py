from pathlib import Path


def test_museum3d_detail_panel_uses_text_nodes_for_miner_fields():
    script_path = Path(__file__).resolve().parents[1] / "web" / "museum" / "museum3d.js"
    script = script_path.read_text(encoding="utf-8")

    assert "key.textContent = k;" in script
    assert "value.textContent = String(v || '');" in script
    assert "kv.appendChild(key);" in script
    assert "kv.appendChild(value);" in script
    assert 'kv.innerHTML = `<div class="k">${k}</div><div class="v">${String(v || \'\')}</div>`;' not in script
