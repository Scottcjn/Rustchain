from pathlib import Path


def test_beacon_bounty_panel_escapes_api_and_github_fields():
    ui_js = Path(__file__).resolve().parents[1] / "site" / "beacon" / "ui.js"
    source = ui_js.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in source
    assert "function safeGithubUrl(value)" in source
    assert "url.protocol !== 'https:'" in source
    assert "url.hostname !== 'github.com' && !url.hostname.endsWith('.github.com')" in source
    assert "const safeUrl = safeGithubUrl(b.url);" in source

    safe_patterns = [
        "const title = escapeHtml(b.title);",
        "const reward = escapeHtml(b.reward);",
        "const difficulty = escapeHtml(b.difficulty);",
        "const repo = escapeHtml(b.repo);",
        "const ghRef = escapeHtml(b.ghNum || b.id);",
        "const claimant = escapeHtml(agent ? agent.name : b.claimant);",
        "const completedBy = escapeHtml(agent ? agent.name : b.completed_by);",
        "const agentId = escapeHtml(r.agent_id);",
        "const displayName = escapeHtml(name);",
        'href="${safeUrl}"',
    ]
    for pattern in safe_patterns:
        assert pattern in source

    unsafe_patterns = [
        "${b.title}",
        "${b.reward}",
        "[${b.difficulty}]",
        "${b.repo} ${b.ghNum || b.id}",
        "${agent ? agent.name : b.claimant}",
        "${agent ? agent.name : b.completed_by}",
        'data-leaderboard-agent="${r.agent_id}"',
        "${name}</span>",
        "const safeUrl = (b.url || '').replace(/'/g, '%27');",
    ]
    for pattern in unsafe_patterns:
        assert pattern not in source
