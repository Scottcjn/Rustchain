from pathlib import Path


JS = (Path(__file__).resolve().parents[1] / "site" / "beacon" / "ui.js").read_text(
    encoding="utf-8"
)


def test_escape_html_helper_exists():
    assert "ESC_HTML" in JS


def test_open_bounty_fields_escaped():
    assert "${ESC_HTML(b.title)}" in JS
    assert "${ESC_HTML(b.reward)}" in JS
    assert "${ESC_HTML(b.difficulty)}" in JS
    assert "${ESC_HTML(b.repo)}" in JS
    assert "${ESC_HTML(b.ghNum || b.id)}" in JS


def test_claimed_bounty_fields_escaped():
    assert "${ESC_HTML(b.title)}" in JS
    assert "${ESC_HTML(agent ? agent.name : b.claimant)}" in JS


def test_completed_bounty_fields_escaped():
    assert "${ESC_HTML(b.title)}" in JS


def test_leaderboard_field_escaped():
    assert 'data-leaderboard-agent="${ESC_HTML(r.agent_id)}"' in JS
    assert "${ESC_HTML(name)}" in JS


def test_raw_api_fields_not_in_inner_html():
    assert '${b.title}</span>' not in JS
    assert '${b.reward}</span>' not in JS
    assert '${b.difficulty}]</span>' not in JS
    assert '${b.claimant}</div>' not in JS
    assert '${b.completed_by}</div>' not in JS
    assert 'data-leaderboard-agent="${r.agent_id}"' not in JS
    assert '${name}</span>' not in JS


def test_safe_url_quotes_escaped():
    assert 'replace(/"/g' in JS
