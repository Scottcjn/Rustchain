# SPDX-License-Identifier: MIT
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "mining-simulator.html"


def test_mining_simulator_uses_dom_helpers_for_status_messages():
    html = SOURCE.read_text(encoding="utf-8")

    assert "function setStatusMessage(container, color, icon, message)" in html
    assert "paragraph.textContent = `${icon} ${message}`;" in html
    assert 'result.innerHTML = `<p style="color: #3fb950;' not in html
    assert "result.innerHTML = hw.real" not in html
    assert "document.getElementById('epoch-result').innerHTML" not in html


def test_mining_simulator_renders_comparison_cards_without_inner_html():
    html = SOURCE.read_text(encoding="utf-8")

    assert "function renderComparisonCards(container, compareData, baseReward)" in html
    assert "container.replaceChildren();" in html
    assert "card.append(icon, name, multiplier, earnings);" in html
    assert "comp.innerHTML = compareData.map" not in html
