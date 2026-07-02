# SPDX-License-Identifier: MIT
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "web" / "mood-indicator.js"


def test_mood_indicator_loading_state_uses_dom_nodes():
    source = SOURCE.read_text(encoding="utf-8")

    assert "function setLoadingIndicator(container)" in source
    assert "indicator.textContent = '⏳';" in source
    assert "container.innerHTML = '<span style=\"font-size: 18px; opacity: 0.5;\">⏳</span>'" not in source


def test_mood_indicator_refresh_reuses_render_helper():
    source = SOURCE.read_text(encoding="utf-8")

    assert "function renderIndicator(container, moodData)" in source
    assert "container.appendChild(createIndicatorElement(moodData));" in source
    assert "container.innerHTML = '';" not in source
