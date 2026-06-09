from pathlib import Path


JS = (Path(__file__).resolve().parents[1] / "explorer" / "static" / "js" / "explorer.js").read_text(
    encoding="utf-8"
)


def test_api_version_is_escaped_in_status_bar():
    assert "${escapeHtml(state.health.version || '2.2.1')}" in JS
    assert "${state.health.version || '2.2.1'}" not in JS
