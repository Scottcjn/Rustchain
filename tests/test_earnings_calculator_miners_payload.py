from pathlib import Path


HTML = Path("tools/earnings_calculator.html").read_text(encoding="utf-8")


def test_earnings_calculator_normalizes_miner_payload_envelopes():
    assert "function normalizeMinerRows(payload)" in HTML
    assert "Array.isArray(payload?.miners)" in HTML
    assert "Array.isArray(payload?.data)" in HTML
    assert "Array.isArray(payload?.items)" in HTML
    assert "const miners = normalizeMinerRows(await res.json());" in HTML


def test_earnings_calculator_ignores_malformed_multiplier_rows():
    assert "rows.filter(row => row && typeof row === 'object')" in HTML
    assert "acc + (Number(m.antiquity_multiplier) || 0)" in HTML
    assert "const liveNetworkSum = miners.reduce((acc, m) =>" in HTML
    assert "if (liveNetworkSum > 0) networkSum = liveNetworkSum;" in HTML
