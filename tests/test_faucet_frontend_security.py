from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "faucet_service" / "faucet_service.py").read_text(
    encoding="utf-8"
)


def test_faucet_result_uses_text_nodes_for_dynamic_messages():
    assert "function renderFaucetResult(data, wallet)" in SOURCE
    assert "function renderFaucetError(err)" in SOURCE
    assert "line.textContent = text;" in SOURCE
    assert "result.replaceChildren();" in SOURCE


def test_faucet_result_does_not_interpolate_dynamic_values_into_inner_html():
    assert "${data.error}" not in SOURCE
    assert "${err.message}" not in SOURCE
    assert "result.innerHTML" not in SOURCE
    assert "result.innerHTML = `<strong>❌ Error:</strong> ${err.message}`;" not in SOURCE
