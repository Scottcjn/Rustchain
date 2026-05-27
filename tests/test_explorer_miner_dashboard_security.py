from pathlib import Path
import json
import re
import subprocess


HTML = Path(__file__).resolve().parents[1] / "explorer" / "miner-dashboard.html"


def source():
    return HTML.read_text(encoding="utf-8")


def test_share_link_is_built_with_dom_text_nodes():
    html = source()

    assert "shareLink.textContent = 'Share this dashboard: ';" in html
    assert "shareAnchor.textContent = url.href;" in html
    assert 'href="${url.href}">${url.href}</a>' not in html


def test_reward_rows_escape_api_fields_before_inner_html():
    html = source()

    assert "${safeText(r.epoch ?? r.block)}" in html
    assert "${safeText(r.amount ?? r.reward ?? r.value, '?')} RTC" in html
    assert "${safeText(timeAgo(r.timestamp || r.time || r.created_at))}" in html
    assert "${r.amount ?? r.reward ?? r.value ?? '?'} RTC" not in html
    assert "${timeAgo(r.timestamp || r.time || r.created_at)}" not in html


def test_empty_reward_and_activity_rows_escape_api_fields():
    html = source()

    assert "const epochSummary = epoch.number ?? epoch.id ?? JSON.stringify(epoch).substring(0, 50);" in html
    assert "Current epoch: ${safeText(epochSummary)}" in html
    assert "Block ${safeText(activityData.height ?? activityData.block_height)}" in html
    assert "${safeText(timeAgo(activityData.timestamp))}" in html
    assert "Current epoch: ${epoch.number ?? epoch.id ?? JSON.stringify(epoch).substring(0, 50)}" not in html
    assert "Block ${activityData.height ?? activityData.block_height ?? '--'}" not in html


def test_withdrawal_rows_escape_amounts_and_timestamps():
    html = source()

    assert html.count("${safeText(w.amount, '?')} RTC") == 1
    assert html.count("${safeText(timeAgo(w.requested_at || w.created_at || w.timestamp))}") == 1
    assert "${w.amount ?? '?'} RTC" not in html
    assert "${timeAgo(w.requested_at || w.created_at || w.timestamp)}" not in html


def test_withdrawal_history_normalizes_array_envelopes():
    html = source()

    assert "function normalizeWithdrawals(payload)" in html
    assert "const withdrawals = normalizeWithdrawals(historyData);" in html
    assert "historyData.withdrawals.slice(0, 10).map" not in html


def test_withdrawal_normalization_rejects_malformed_rows():
    script = re.search(r"<script>(?P<script>.*?)</script>", source(), flags=re.DOTALL).group(
        "script"
    )
    probe = f"""
const vm = require('vm');
const script = {json.dumps(script)};
const payload = {json.dumps({"withdrawals": [None, "bad", {"id": "ok"}, {"id": "<bad>"}]})};
const context = {{
  console: {{ warn() {{}} }},
  window: {{ location: {{ origin: 'https://example.test', search: '' }} }},
  URLSearchParams,
  setInterval() {{}},
  document: {{
    createElement() {{ return {{ textContent: '', get innerHTML() {{ return this.textContent; }} }}; }},
    getElementById() {{ return {{ value: '', style: {{}}, textContent: '', appendChild() {{}} }}; }},
  }},
}};
context.payload = payload;
vm.createContext(context);
vm.runInContext(script, context);
const rows = vm.runInContext('normalizeWithdrawals(payload)', context);
console.log(JSON.stringify(rows));
"""
    result = subprocess.run(
        ["node", "-e", probe],
        text=True,
        capture_output=True,
        check=True,
    )

    assert json.loads(result.stdout) == [{"id": "ok"}, {"id": "<bad>"}]
