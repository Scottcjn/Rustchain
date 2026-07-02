# SPDX-License-Identifier: MIT
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "tools" / "browser-extension" / "popup.js"


def test_browser_extension_popup_uses_spinner_helper():
    source = SOURCE.read_text(encoding="utf-8")

    assert 'function setSpinner(target)' in source
    assert 'spinner.className = "spinner";' in source
    assert "target.appendChild(spinner);" in source
    assert 'balanceValue.innerHTML = \'<span class="spinner"></span>\';' not in source
