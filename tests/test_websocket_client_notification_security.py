# SPDX-License-Identifier: MIT

from pathlib import Path
import json
import subprocess


WEBSOCKET_JS = (
    Path(__file__).resolve().parents[1] / "explorer" / "static" / "js" / "websocket-client.js"
)


def source() -> str:
    return WEBSOCKET_JS.read_text(encoding="utf-8")


def test_websocket_notifications_are_built_with_text_nodes():
    js = source()

    assert "notification.innerHTML = `" not in js
    assert "titleEl.textContent = String(title ?? '');" in js
    assert "bodyEl.textContent = String(body ?? '');" in js
    assert "close.addEventListener('click', () => notification.remove());" in js
    assert "function getNotificationType(type)" in js


def test_websocket_handlers_ignore_malformed_single_events():
    js = source()

    assert "if (!block || typeof block !== 'object') return;" in js
    assert "if (!attestation || typeof attestation !== 'object') return;" in js
    assert "if (!settlement || typeof settlement !== 'object') return;" in js
    assert "shortenValue(attestation.miner_id, 16)" in js
    assert "Number.isFinite(reward) ? reward.toFixed(2) : '0.00'" in js


def test_websocket_notification_event_path_uses_text_content():
    js = source()
    probe = f"""
const vm = require('vm');
const script = {json.dumps(js)};
const handlers = {{}};
const elements = {{}};
function element(tag) {{
  return {{
    tag,
    className: '',
    type: '',
    textContent: '',
    children: [],
    parentElement: null,
    classList: {{ add() {{}} }},
    addEventListener() {{}},
    appendChild(child) {{ child.parentElement = this; this.children.push(child); }},
    remove() {{ this.removed = true; }},
    set innerHTML(value) {{ this.usedInnerHTML = value; }},
    get innerHTML() {{ return this.usedInnerHTML || ''; }},
  }};
}}
const notifications = element('div');
elements['ws-notifications'] = notifications;
const context = {{
  window: {{
    location: {{ protocol: 'https:', host: 'example.test', origin: 'https://example.test' }},
    RustChainExplorer: {{ state: {{ blocks: [] }} }},
  }},
  document: {{
    addEventListener() {{}},
    getElementById(id) {{ return elements[id] || null; }},
    createElement: element,
    head: element('head'),
  }},
  io() {{ return {{ on(event, cb) {{ handlers[event] = cb; }}, emit() {{}} }}; }},
  WebSocket: {{ OPEN: 1 }},
  setTimeout() {{ return 1; }},
  setInterval() {{ return 1; }},
  clearInterval() {{}},
  console: {{ log() {{}}, error() {{}} }},
}};
vm.createContext(context);
vm.runInContext(script, context);
context.window.RustChainWebSocket.connect();
handlers.block({{ height: '<img src=x>', miners_count: '<b>9</b>', reward: '<script>x</script>' }});
const notification = notifications.children[0];
const header = notification.children[0];
const body = notification.children[1];
console.log(JSON.stringify({{
  className: notification.className,
  usedInnerHTML: Boolean(notification.usedInnerHTML),
  title: header.children[1].textContent,
  body: body.textContent,
  storedBlocks: context.window.RustChainExplorer.state.blocks.length,
}}));
"""
    result = subprocess.run(
        ["node", "-e", probe],
        text=True,
        capture_output=True,
        check=True,
    )
    data = json.loads(result.stdout)

    assert data["className"] == "ws-notification ws-notification-block"
    assert data["usedInnerHTML"] is False
    assert data["title"] == "New Block #<img src=x>"
    assert data["body"] == "Miners: <b>9</b> | Reward: <script>x</script> RTC"
    assert data["storedBlocks"] == 1
