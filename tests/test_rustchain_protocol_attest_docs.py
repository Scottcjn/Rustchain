from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rustchain_protocol_documents_attest_submit_route():
    text = (ROOT / "docs" / "RUSTCHAIN_PROTOCOL.md").read_text(encoding="utf-8")

    assert "| `/attest/submit` | POST | Submit hardware fingerprint |" in text
    assert "### POST /attest/submit" in text
    assert "curl -sk -X POST https://rustchain.org/attest/submit" in text
    assert "| `/attest` | POST | Submit hardware fingerprint |" not in text
    assert "### POST /attest\n" not in text
    assert "curl -sk -X POST https://rustchain.org/attest \\" not in text
