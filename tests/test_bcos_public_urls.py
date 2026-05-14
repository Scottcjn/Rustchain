from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BCOS_ROUTES = ROOT / "node" / "bcos_routes.py"


def _source() -> str:
    return BCOS_ROUTES.read_text(encoding="utf-8")


def test_bcos_routes_use_certificate_valid_public_base_url():
    source = _source()
    assert (
        'BCOS_PUBLIC_BASE_URL = os.environ.get("BCOS_PUBLIC_BASE_URL", '
        '"https://rustchain.org").rstrip("/")'
    ) in source
    assert "def _bcos_url(path: str) -> str:" in source
    assert "https://50.28.86.131/bcos" not in source


def test_bcos_response_links_use_shared_url_helper():
    source = _source()
    assert '"verify_url": _bcos_url(f"/bcos/verify/{cert_id}")' in source
    assert '"badge_url": _bcos_url(f"/bcos/badge/{cert_id}.svg")' in source
    assert '"pdf_url": _bcos_url(f"/bcos/cert/{cert_id}.pdf")' in source
    assert '"verify_url": _bcos_url(f"/bcos/verify/{row[\'cert_id\']}")' in source
    assert '"badge_url": _bcos_url(f"/bcos/badge/{row[\'cert_id\']}.svg")' in source

