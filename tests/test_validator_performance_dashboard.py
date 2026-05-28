# SPDX-License-Identifier: MIT

from pathlib import Path

DASHBOARD_HTML = (
    Path(__file__).resolve().parents[1]
    / "dashboards"
    / "validator-performance"
    / "index.html"
)


def test_validator_performance_dashboard_includes_required_metrics():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert "RustChain Validator Performance" in html
    assert 'id="activeValidators"' in html
    assert 'id="avgAttestations"' in html
    assert 'id="avgLatency"' in html
    assert 'id="topValidator"' in html
    assert 'id="historyBody"' in html


def test_validator_performance_dashboard_normalizes_miner_payloads():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert "function normalizeMinerRows(payload)" in html
    assert "payload?.miners || payload?.data || payload?.items || []" in html
    assert "const minerRows = normalizeMinerRows(payload);" in html


def test_validator_performance_dashboard_computes_metrics_from_miner_fields():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert "function computeValidatorMetrics(minerRows)" in html
    assert "const activeRows = minerRows.filter(isActiveValidator);" in html
    assert '["attestations", "attestation_count", "total_attestations", "attest_count"]' in html
    assert '["latency_ms", "avg_latency_ms", "response_time_ms", "last_latency_ms"]' in html
    assert "MAX_HISTORY_SAMPLES = 20" in html


def test_validator_performance_dashboard_renders_api_values_with_text_nodes():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert "function appendTextCell(row, text)" in html
    assert "cell.textContent = text;" in html
    assert "document.getElementById(id).textContent = text;" in html
    assert "innerHTML" not in html
