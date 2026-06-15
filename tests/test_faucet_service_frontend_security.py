# SPDX-License-Identifier: MIT
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_faucet_service_result_rendering_uses_text_nodes():
    source = (ROOT / "faucet_service" / "faucet_service.py").read_text(
        encoding="utf-8"
    )

    assert "function showResult(ok, title, message, nextAvailable)" in source
    assert "titleNode.textContent = title;" in source
    assert "document.createTextNode(message)" in source
    assert "small.textContent = 'Next available: ' +" in source
    assert "result.replaceChildren" in source
    assert "result.innerHTML" not in source
    assert "Sent ${data.amount} RTC to" not in source
    assert "<strong>❌ Error:</strong> ${err.message}" not in source
