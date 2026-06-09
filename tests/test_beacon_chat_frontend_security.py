from pathlib import Path


CHAT_JS = Path(__file__).resolve().parents[1] / "site" / "beacon" / "chat.js"


def test_beacon_chat_hint_escapes_agent_name():
    js = CHAT_JS.read_text(encoding="utf-8")

    assert "Type below to hail ${agentName}..." not in js
    assert "Type below to hail ${escapeHtml(agentName)}..." in js


def test_beacon_chat_live_messages_use_dom_text_nodes():
    js = CHAT_JS.read_text(encoding="utf-8")

    assert "msgBox.innerHTML +=" not in js
    assert "function createChatMessage(role, prefix, content)" in js
    assert "el.append(document.createTextNode(content));" in js
    assert "msgBox.appendChild(createChatMessage('user', 'you>', text));" in js
    assert "msgBox.appendChild(createTypingIndicator());" in js
    assert "msgBox.appendChild(createChatMessage('agent', `${agentName.toLowerCase()}>`, data.response));" in js
    assert "msgBox.appendChild(createChatMessage('error', '', `[ERROR] ${data.error}`));" in js
