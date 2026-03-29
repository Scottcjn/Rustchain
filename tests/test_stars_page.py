from pathlib import Path


def test_stars_page_contains_campaign_content():
    page = Path("stars.html").read_text(encoding="utf-8")

    assert "5,000 Stars Drive" in page
    assert "Social Amplifier Bonus" in page
    assert 'const TARGET_STARS = 5000;' in page
    assert 'const ALL_REPOS_TARGET = 86;' in page
    assert 'https://api.github.com/users/${OWNER}/repos' in page
