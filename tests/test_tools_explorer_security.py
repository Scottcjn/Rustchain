from pathlib import Path


HTML = Path(__file__).resolve().parents[1] / "tools" / "explorer" / "index.html"


def source():
    return HTML.read_text(encoding="utf-8")


def test_tools_explorer_defines_shared_text_escaping_helpers():
    html = source()

    assert "function escapeHtml(value)" in html
    assert "function safeText(value, fallback = \"-\")" in html
    assert "function setSelectOptions(select, values)" in html


def test_miner_table_escapes_api_fields_before_inner_html():
    html = source()

    assert "${safeText(m.miner)}" in html
    assert "${safeText(arch)}" in html
    assert "${safeText(formatTime(m.last_attest))}" in html
    assert "${safeText(m.hardware_type)}" in html
    assert "${m.miner || \"-\"}" not in html
    assert "${m.hardware_type || \"-\"}" not in html


def test_agent_jobs_and_reputation_escape_api_fields():
    html = source()

    assert "${safeText(job.job_id)}" in html
    assert "${safeText(job.category || \"other\")}" in html
    assert "${safeText(job.status || \"unknown\")}" in html
    assert "${safeText(job.poster_wallet)}" in html
    assert "${safeText(rep.wallet_id)}" in html
    assert "${safeText(rep.trust_level)}" in html
    assert "${safeText(rep.last_active)}" in html
    assert "${job.job_id || \"-\"}" not in html
    assert "${job.poster_wallet || \"-\"}" not in html
    assert "${rep.wallet_id || \"-\"}" not in html


def test_filter_options_are_built_with_option_nodes():
    html = source()

    assert "setSelectOptions(archFilter, [...archSet].sort());" in html
    assert "setSelectOptions(select, [...categories].sort());" in html
    assert "`<option value=\"${a}\">${a}</option>`" not in html
    assert "`<option value=\"${c}\">${c}</option>`" not in html


def test_error_card_escapes_exception_message():
    html = source()

    assert "${safeText(err.message || err)}" in html
    assert "${String(err.message || err)}" not in html
