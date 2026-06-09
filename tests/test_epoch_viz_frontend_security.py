from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "integrations" / "epoch-viz" / "index.html").read_text(
    encoding="utf-8"
)


def test_epoch_viz_escapes_api_miner_text_before_inner_html_rendering():
    assert "function escapeHtml(value)" in HTML
    assert '<div class="miner-name">${escapeHtml(minerName)}</div>' in HTML
    assert '<div class="miner-arch">${escapeHtml(archShort)}</div>' in HTML

    assert "${miner.miner?.substring(0, 20) || 'Unknown'}" not in HTML
    assert '<div class="miner-arch">${archShort}</div>' not in HTML
