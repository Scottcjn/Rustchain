# SPDX-License-Identifier: MIT

from pathlib import Path


FAUCET_SERVICE = (
    Path(__file__).resolve().parents[1] / "faucet_service" / "faucet_service.py"
)


def _source() -> str:
    return FAUCET_SERVICE.read_text(encoding="utf-8")


def test_faucet_service_result_messages_use_text_nodes():
    source = _source()

    assert "function renderResult(kind, title, message, nextAvailable)" in source
    assert "result.textContent = '';" in source
    assert "titleNode.textContent = title;" in source
    assert "appendLine(document.createTextNode(message));" in source
    assert (
        "small.textContent = 'Next available: ' + "
        "new Date(nextAvailable).toLocaleString();"
    ) in source

    assert "result.innerHTML" not in source
    assert "${data.error}" not in source
    assert "${err.message}" not in source
    assert "${wallet.substring" not in source
