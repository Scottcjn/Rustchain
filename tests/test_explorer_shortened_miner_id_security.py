from pathlib import Path


JS = (Path(__file__).resolve().parents[1] / "explorer" / "static" / "js" / "explorer.js").read_text(
    encoding="utf-8"
)


def test_visible_shortened_miner_ids_are_escaped_before_inner_html_rendering():
    assert "${escapeHtml(shortenAddress(minerId))}" in JS
    assert "${escapeHtml(shortenAddress(miner.miner_id || 'unknown'))}" in JS

    assert ">${shortenAddress(minerId)}</td>" not in JS
    assert ">${shortenAddress(miner.miner_id || 'unknown')}</td>" not in JS
