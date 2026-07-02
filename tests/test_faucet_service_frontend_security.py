# SPDX-License-Identifier: MIT
from pathlib import Path


def test_faucet_service_result_rendering_uses_dom_nodes():
    page = Path(__file__).resolve().parents[1] / "faucet_service" / "faucet_service.py"
    html = page.read_text(encoding="utf-8")

    assert "result.innerHTML = `" not in html
    assert "result.innerHTML = `<strong>❌ Error:</strong>" not in html
    assert "result.innerHTML = ''" not in html
    assert "result.replaceChildren()" in html
    assert "document.createTextNode" in html
    assert "document.createElement" in html
