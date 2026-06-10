# SPDX-License-Identifier: MIT
from pathlib import Path


JS_PATH = Path(__file__).resolve().parents[1] / "site" / "beacon" / "chat.js"


def test_empty_history_hint_escapes_agent_name():
    source = JS_PATH.read_text(encoding="utf-8")

    assert "Type below to hail ${escapeHtml(agentName)}..." in source
    assert "Type below to hail ${agentName}..." not in source


def test_live_chat_messages_use_dom_text_nodes():
    source = JS_PATH.read_text(encoding="utf-8")

    assert "function appendChatMessage(msgBox, className, prefix, message)" in source
    assert "document.createTextNode(String(message ?? ''))" in source
    assert "function appendTypingIndicator(msgBox)" in source
    assert "msgBox.innerHTML +=" not in source

    unsafe_patterns = [
        "${escapeHtml(text)}</div>",
        "${escapeHtml(data.response)}</div>",
        "${escapeHtml(data.error)}</div>",
        "id=\"chat-typing\"><span class=\"typing-dots\"></span> processing...</div>",
    ]
    for pattern in unsafe_patterns:
        assert pattern not in source
