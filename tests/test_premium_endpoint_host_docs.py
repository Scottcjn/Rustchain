from pathlib import Path


def test_premium_videos_and_analytics_are_not_listed_under_main_base_url():
    readme = Path("docs/api/README.md").read_text(encoding="utf-8")
    openapi = Path("docs/api/openapi.yaml").read_text(encoding="utf-8")
    postman = Path("docs/postman/RustChain.postman_collection.json").read_text(encoding="utf-8")
    api_reference = Path("docs/api-reference.md").read_text(encoding="utf-8")
    zh_readme = Path("docs/zh-CN/README.md").read_text(encoding="utf-8")

    assert "/api/premium/videos" not in readme
    assert "/api/premium/analytics/{agent}" not in readme
    assert "/api/premium/videos:" not in openapi
    assert "/api/premium/analytics/{agent}:" not in openapi
    assert "{{base_url}}/api/premium/videos" not in postman
    assert "{{base_url}}/api/premium/analytics/{{agent}}" not in postman

    assert "https://bottube.ai/api/premium/videos" in api_reference
    assert "https://bottube.ai/api/premium/analytics/scott" in api_reference
    assert "https://bottube.ai/api/premium/videos" in zh_readme
    assert "https://bottube.ai/api/premium/analytics/<agent>" in zh_readme
