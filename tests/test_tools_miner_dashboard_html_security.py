from pathlib import Path


HTML = Path("tools/miner-dashboard.html").read_text(encoding="utf-8")


def test_tools_miner_dashboard_uses_text_cells_for_reward_rows():
    assert "function appendTextCell(row, text, className)" in HTML
    assert "appendTextCell(row, reward.epoch);" in HTML
    assert "appendTextCell(row, reward.amount);" in HTML
    assert "appendTextCell(row, new Date(reward.timestamp).toLocaleString());" in HTML
    assert "appendTextCell(row, '✓ Confirmed', 'status-success');" in HTML

    assert "<td>${reward.epoch}</td>" not in HTML
    assert "<td>${reward.amount}</td>" not in HTML


def test_tools_miner_dashboard_uses_text_cells_for_activity_rows():
    assert "appendTextCell(row, activity.type);" in HTML
    assert "appendTextCell(row, activity.details);" in HTML
    assert "appendTextCell(row, new Date(activity.timestamp).toLocaleString());" in HTML

    assert "<td>${activity.type}</td>" not in HTML
    assert "<td>${activity.details}</td>" not in HTML


def test_tools_miner_dashboard_empty_rows_use_text_content():
    assert "function renderEmptyRow(tbody, colSpan, message)" in HTML
    assert "cell.textContent = message;" in HTML
    assert "renderEmptyRow(rewardTable, 4, 'No rewards yet');" in HTML
    assert "renderEmptyRow(activityTable, 3, 'No recent activity');" in HTML

    assert "rewardTable.innerHTML = '<tr><td colspan=\"4\"" not in HTML
    assert "activityTable.innerHTML = '<tr><td colspan=\"3\"" not in HTML
