from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FAUCET_SERVICE = REPO_ROOT / "faucet_service" / "faucet_service.py"


def test_faucet_result_rendering_uses_dom_text_nodes():
    source = FAUCET_SERVICE.read_text(encoding="utf-8")

    assert "result.innerHTML" not in source
    assert "function setResultMessage(type, title, lines = [], nextAvailable = null)" in source
    assert "result.replaceChildren();" in source
    assert "document.createTextNode(String(text ?? ''))" in source
    assert "strong.textContent = String(title ?? '');" in source
    assert (
        "small.textContent = `Next available: ${new Date(nextAvailable).toLocaleString()}`;"
        in source
    )
    assert "'success'," in source
    assert "setResultMessage('error'," in source
