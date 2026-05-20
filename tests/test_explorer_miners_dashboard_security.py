# SPDX-License-Identifier: MIT

from pathlib import Path


MINERS_HTML = (
    Path(__file__).resolve().parents[1] / "explorer" / "dashboard" / "miners.html"
)


def _source() -> str:
    return MINERS_HTML.read_text(encoding="utf-8")


def test_miner_rows_escape_api_fields_before_inner_html_rendering():
    source = _source()

    assert "function escapeHtml(value)" in source
    assert "${escapeHtml(id)}" in source
    assert "${escapeHtml(archLabels[arch] || arch)}" in source
    assert "${escapeHtml(multiplier)}x" in source
    assert "${escapeHtml(lastAttestation)}" in source
    assert "${escapeHtml(weight.toLocaleString())}" in source

    assert "<strong>${miner.id}</strong>" not in source
    assert "${archLabels[miner.arch] || miner.arch}" not in source
    assert "${miner.multiplier}x" not in source
    assert "${miner.lastAttestation}" not in source


def test_miner_dashboard_uses_safe_class_tokens_and_current_api_fields():
    source = _source()

    assert "function archClass(arch)" in source
    assert "function minerStatus(miner)" in source
    assert 'class="arch-badge ${archClass(arch)}"' in source
    assert 'class="status-badge ${status}"' in source
    assert "miner.miner_id || miner.miner || miner.wallet" in source
    assert "miner.device_arch || miner.device_family" in source
    assert "miner.multiplier ?? miner.antiquity_multiplier" in source
    assert "miner.lastAttestation ?? miner.last_attestation ?? miner.last_seen ?? miner.last_attest" in source

    assert "miner.arch.toLowerCase().replace(' ', '-')" not in source
    assert 'class="status-badge ${miner.status}"' not in source
