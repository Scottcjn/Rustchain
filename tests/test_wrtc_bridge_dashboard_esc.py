from pathlib import Path


JS = (Path(__file__).resolve().parents[1] / "tools" / "wrtc-bridge-dashboard" / "bridge_dashboard.js").read_text(encoding="utf-8")


def test_esc_helper_exists():
    assert "const esc = v =>" in JS or "function esc(v)" in JS


def test_wallet_and_tx_fields_escaped():
    assert "${esc(tx.wallet)}" in JS
    assert "${esc(tx.tx.slice(0, 8))}" in JS


def test_no_raw_wallet_interpolation():
    assert "${tx.wallet}</td>" not in JS
    assert "${tx.tx.slice(0, 8)}…" not in JS
