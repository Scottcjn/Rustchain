from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    ROOT / "docs" / "api" / "README.md",
    ROOT / "docs" / "api" / "EXAMPLES.md",
    ROOT / "docs" / "api" / "openapi.yaml",
    ROOT / "docs" / "postman" / "README.md",
    ROOT / "docs" / "postman" / "RustChain_API.postman_collection.json",
]


def test_hall_of_fame_docs_use_leaderboard_api_path():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in DOCS)

    assert "/api/hall_of_fame/leaderboard" in combined
    assert "const API_LEADERBOARD = '/api/hall_of_fame/leaderboard'" in (
        ROOT / "web" / "hall-of-fame" / "index.html"
    ).read_text(encoding="utf-8")

    stale_patterns = [
        "https://rustchain.org/api/hall_of_fame | jq",
        "BASE_URL/api/hall_of_fame\"",
        "base_url}/api/hall_of_fame\"",
        "base_url}}/api/hall_of_fame\"",
        "request('/api/hall_of_fame')",
        "  /api/hall_of_fame:",
        "| GET | `/api/hall_of_fame` |",
        "\"path\": [\"api\", \"hall_of_fame\"]",
    ]
    for pattern in stale_patterns:
        assert pattern not in combined
