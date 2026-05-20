from pathlib import Path


JS = Path("site/beacon/data.js").read_text(encoding="utf-8")


def test_beacon_site_normalizes_miner_payload_envelopes():
    assert "function normalizeMinerRows(payload)" in JS
    assert "Array.isArray(payload?.miners)" in JS
    assert "Array.isArray(payload?.data)" in JS
    assert "Array.isArray(payload?.items)" in JS
    assert "const minerList = normalizeMinerRows(await resp.json());" in JS


def test_beacon_site_normalizes_miner_row_ids_before_rendering():
    assert "const miner = row.miner || row.miner_id || row.id;" in JS
    assert "return { ...row, miner: String(miner) };" in JS
    assert "}).filter(Boolean);" in JS
    assert "runtime.__rustchain = { miners: minerList, count: minerList.length };" in JS
