from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_doc(*parts):
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_bridge_initiate_markdown_docs_are_operator_assisted():
    bridge_api = read_doc("docs", "bridge-api.md")
    api_reference = read_doc("docs", "API_REFERENCE.md")
    combined = "\n".join([bridge_api, api_reference])
    normalized = " ".join(combined.split())

    assert "POST /api/bridge/initiate" in normalized
    assert "operator-assisted" in normalized
    assert "not a public self-service native RTC to wRTC/Solana" in normalized
    assert "X-Admin-Key" in normalized
    assert "RC_ADMIN_KEY" in normalized
    assert "401 unauthorized" in normalized
    assert "public payout, minting, or wallet-credit endpoint" in normalized
    assert "**Auth:** None (user-initiated)" not in api_reference


def test_bridge_initiate_openapi_exposes_admin_auth_errors():
    openapi = read_doc("docs", "api", "openapi.yaml")

    assert "/api/bridge/initiate:" in openapi
    assert "operator-assisted/admin-authenticated" in openapi
    assert "self-service native RTC to wRTC/Solana" in openapi
    assert "AdminKeyAuth" in openapi
    assert "'401':" in openapi
    assert "error: unauthorized" in openapi
    assert "'503':" in openapi
    assert "error: RC_ADMIN_KEY not configured" in openapi
