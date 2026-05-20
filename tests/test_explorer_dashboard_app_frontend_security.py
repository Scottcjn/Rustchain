# SPDX-License-Identifier: MIT
from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "explorer" / "dashboard" / "app.py"


def test_explorer_dashboard_app_renders_rows_with_dom_text_nodes():
    source = APP.read_text(encoding="utf-8")

    safe_patterns = [
        "function asObject(v)",
        "function asArray(v)",
        "!Array.isArray(x)",
        "function firstPresent(...values)",
        "function text(v,f='-')",
        "function td(v)",
        "cell.textContent=text(v);",
        "function renderRows(tbodyId,rows,limit,mapper,emptyText)",
        "tbody.replaceChildren(...body);",
        "renderRows('minersTbl',miners,20",
        "renderRows('txTbl',transactions,30",
    ]

    for pattern in safe_patterns:
        assert pattern in source

    unsafe_patterns = [
        "document.getElementById('minersTbl').innerHTML=(d.miners||[])",
        "document.getElementById('txTbl').innerHTML=(d.transactions||[])",
        "<td>${m.miner_id||m.wallet||'-'}</td>",
        "<td>${t.from||t.sender||'-'}</td>",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in source


def test_explorer_dashboard_app_normalizes_dashboard_payloads():
    source = APP.read_text(encoding="utf-8")

    assert "const d=asObject(await j('/api/dashboard'));" in source
    assert "const miners=asArray(d.miners);" in source
    assert "const transactions=asArray(d.transactions);" in source
    assert "document.getElementById('network').textContent=text(asObject(d.health).status,'unknown');" in source
    assert "document.getElementById('epoch').textContent=text(asObject(d.epoch).epoch);" in source
    assert "document.getElementById('miners').textContent=miners.length;" in source
    assert "document.getElementById('txcount').textContent=transactions.length;" in source
    assert "firstPresent(m.score,m.attestation_score)" in source
    assert "firstPresent(m.multiplier,m.antiquity_multiplier)" in source
    assert "firstPresent(t.amount,t.value)" in source


def test_explorer_dashboard_app_preserves_zero_values_and_rejects_nested_arrays():
    source = APP.read_text(encoding="utf-8")

    assert "v!==undefined&&v!==null&&v!==''" in source
    assert "m.score||m.attestation_score" not in source
    assert "m.multiplier||m.antiquity_multiplier" not in source
    assert "t.amount||t.value" not in source
    assert "typeof x==='object'&&!Array.isArray(x)" in source
