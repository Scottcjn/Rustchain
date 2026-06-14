# SPDX-License-Identifier: MIT
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_JS = ROOT / "site" / "beacon" / "ui.js"
CHAT_JS = ROOT / "site" / "beacon" / "chat.js"


def test_beacon_agent_panel_encodes_external_values_before_inner_html():
    js = UI_JS.read_text(encoding="utf-8")
    assert "function escapeHtml(value)" in js
    safe_patterns = [
        "${escapeHtml(agent.name)}",
        "${escapeHtml(agent.role)}",
        "agent.capabilities.map(c => `[${escapeHtml(c)}]`)",
        "${escapeHtml(other ? other.name : '?')}",
        "${escapeHtml(c.amount)} ${escapeHtml(c.currency)}",
        "state-${escapeHtml(c.state)}",
        "${escapeHtml(b.label)}",
        "${encodeURIComponent(agent.bottube)}",
        "data-from=\"${escapeHtml(agentId)}\"",
        "const beatCount = safeNumber(agent.beat_count)",
        "${renderBar(score, maxScore, gradeColor)} ${score}/${maxScore}",
        "${videos} videos | ${totalViews.toLocaleString()} views",
        "${antiquityMultiplier}x antiquity",
    ]
    for pattern in safe_patterns:
        assert pattern in js
    unsafe_patterns = [
        "${agent.name}</span></div>",
        "${agent.role}</span></div>",
        "agent.capabilities.map(c => `[${c}]`)",
        "${other ? other.name : '?'}  ${c.amount} ${c.currency}",
        "state-${c.state}\">${c.state}</span>",
        "https://bottube.ai/agent/${agent.bottube}",
        "data-from=\"${agentId}\"",
        "${agent.beat_count}</span></div>",
        "renderBar(agent.score, agent.maxScore, gradeColor)",
        "${agent.videos} videos",
        "${agent.antiquity_multiplier}x antiquity",
    ]
    for pattern in unsafe_patterns:
        assert pattern not in js


def test_beacon_chat_hint_encodes_stored_agent_name():
    js = CHAT_JS.read_text(encoding="utf-8")
    assert "Type below to hail ${escapeHtml(agentName)}..." in js
    assert "Type below to hail ${agentName}..." not in js

def test_beacon_bar_clamps_numeric_inputs():
    js = UI_JS.read_text(encoding="utf-8")
    assert "function safeNumber(value, fallback = 0, min = 0, max = Number.MAX_SAFE_INTEGER)" in js
    assert "if (!Number.isFinite(number)) return fallback" in js
    assert "const safeMax = safeNumber(max, 1, 1)" in js
    assert "const safeValue = safeNumber(value, 0, 0, safeMax)" in js
    assert "Math.min(100, Math.max(0, Math.round((safeValue / safeMax) * 100)))" in js