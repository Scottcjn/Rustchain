from pathlib import Path


DASHBOARD_HTML = (
    Path(__file__).resolve().parents[1]
    / "dashboards"
    / "rustchain-stats"
    / "index.html"
)


def test_rustchain_stats_dashboard_uses_normalized_miners_fallback():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert "function normalizeMinerRows(payload)" in html
    assert "payload?.miners || payload?.data || payload?.items || []" in html
    assert "const minerRows = normalizeMinerRows(miners);" in html
    assert "const enrolledMiners = Number(epoch.enrolled_miners ?? minerRows.length);" in html
    assert "updateStat('minersValue', enrolledMiners, '', previousStats?.minersCount);" in html
    assert "minersCount: enrolledMiners" in html
    assert "updateStat('minersValue', epoch.enrolled_miners || 0, '', previousStats?.epoch?.enrolled_miners);" not in html
