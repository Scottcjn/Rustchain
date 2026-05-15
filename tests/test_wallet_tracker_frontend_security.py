from pathlib import Path


TRACKER_HTML = Path(__file__).resolve().parents[1] / "wallet-tracker" / "rtc-wallet-tracker.html"


def test_wallet_tracker_escapes_wallet_ids_and_founder_labels():
    html = TRACKER_HTML.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in html
    assert "function founderBadge(w, className = 'badge-founder')" in html
    assert 'return `<span class="${className}">${escapeHtml(w.founderLabel)}</span>`;' in html
    assert "<strong>${escapeHtml(w.id)}</strong>" in html
    assert "${escapeHtml(w.id)}" in html
    assert "${founderBadge(w)}" in html
    assert "${founderBadge(w, 'badge badge-founder')}" in html

    assert "<strong>${w.id}</strong>" not in html
    assert "${w.id}\n" not in html
    assert "+ w.founderLabel +" not in html
