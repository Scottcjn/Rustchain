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


def test_wallet_tracker_normalizes_miner_payload_envelopes():
    html = TRACKER_HTML.read_text(encoding="utf-8")

    assert "function normalizeMinerRows(payload)" in html
    assert "Array.isArray(payload?.miners)" in html
    assert "Array.isArray(payload?.data)" in html
    assert "Array.isArray(payload?.items)" in html
    assert "const miners = normalizeMinerRows(await minersResponse.json());" in html


def test_wallet_tracker_normalizes_miner_row_ids_before_balance_fetch():
    html = TRACKER_HTML.read_text(encoding="utf-8")

    assert "const miner = row.miner || row.miner_id || row.id;" in html
    assert "return { ...row, miner: String(miner) };" in html
    assert "}).filter(Boolean);" in html
    assert "const balance = await getBalance(miner.miner);" in html
