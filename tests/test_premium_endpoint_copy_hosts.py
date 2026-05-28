from pathlib import Path


def test_localized_premium_endpoint_copy_uses_bottube_host():
    readme_es = Path("README_ES.md").read_text(encoding="utf-8")
    readme_ja = Path("README_JA.md").read_text(encoding="utf-8")
    wallets = Path("web/wallets.html").read_text(encoding="utf-8")

    assert "GET https://bottube.ai/api/premium/videos" in readme_es
    assert "GET https://bottube.ai/api/premium/analytics/<agent>" in readme_es
    assert "GET https://bottube.ai/api/premium/videos" in readme_ja
    assert "GET https://bottube.ai/api/premium/analytics/<agent>" in readme_ja
    assert "https://bottube.ai/api/premium/videos" in wallets
    assert "https://bottube.ai/api/premium/analytics/&lt;agent&gt;" in wallets

    assert "GET /api/premium/videos" not in readme_es
    assert "GET /api/premium/analytics/<agent>" not in readme_es
    assert "GET /api/premium/videos" not in readme_ja
    assert "GET /api/premium/analytics/<agent>" not in readme_ja
