from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_JS = REPO_ROOT / "site" / "beacon" / "ui.js"


def read_ui_source() -> str:
    return UI_JS.read_text(encoding="utf-8")


def test_bounty_panel_escapes_dynamic_fields() -> None:
    source = read_ui_source()

    assert "function escapeHtml(value)" in source
    assert "${escapeHtml(b.title)}" in source
    assert "${escapeHtml(b.reward)}" in source
    assert "[${escapeHtml(b.difficulty)}]" in source
    assert "${escapeHtml(b.repo)} ${escapeHtml(b.ghNum || b.id)}" in source
    assert "Claimed by: ${escapeHtml(claimantName || 'unknown')}" in source
    assert "Completed by: ${escapeHtml(completerName || 'unknown')}" in source
    assert "data-leaderboard-agent=\"${escapeHtml(leaderboardAgentId)}\"" in source
    assert "${escapeHtml(name)}" in source


def test_bounty_links_are_limited_to_https_github_hosts() -> None:
    source = read_ui_source()

    assert "function safeGithubUrl(value)" in source
    assert "url.protocol !== 'https:'" in source
    assert "host !== 'github.com' && !host.endsWith('.github.com')" in source
    assert "const safeUrl = safeGithubUrl(b.url);" in source
    assert 'href="${escapeHtml(safeUrl)}"' in source


def test_bounty_panel_does_not_use_old_raw_interpolations() -> None:
    source = read_ui_source()

    forbidden_fragments = [
        "${b.title}",
        "${b.reward}",
        "[${b.difficulty}]",
        "${b.repo} ${b.ghNum || b.id}",
        "Claimed by: ${agent ? agent.name : b.claimant}",
        "Completed by: ${agent ? agent.name : b.completed_by}",
        "data-leaderboard-agent=\"${r.agent_id}\"",
        "${name}</span>",
        "${r.score} rep",
        "const safeUrl = (b.url || '').replace(/'/g, '%27');",
        'href="${safeUrl}"',
    ]
    for fragment in forbidden_fragments:
        assert fragment not in source
