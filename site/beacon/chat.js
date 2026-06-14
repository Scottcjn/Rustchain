// ============================================================
// BEACON ATLAS - Agent Chat Module
// Terminal-style comms channel for talking to agents
// ============================================================

const CHAT_API = '/beacon/api/chat';
const chatHistories = new Map(); // agentId -> [{role, content}]

let currentAgentId = null;
let sending = false;

export function initChat() {
  // Global keydown for chat input focus
  document.addEventListener('keydown', (e) => {
    const input = document.getElementById('chat-input');
    if (!input) return;
    if (e.key === 'Enter' && document.activeElement === input) {
      e.preventDefault();
      sendMessage();
    }
  });
}

export function setCurrentAgent(agentId) {
  currentAgentId = agentId;
}

export function getChatHTML(agentId, agentName) {
  const history = chatHistories.get(agentId) || [];

  let html = '<div class="t-section">-- COMMS CHANNEL --</div>';
  html += '<div id="chat-messages" class="chat-messages">';

  if (history.length === 0) {
    html += `<div class="chat-hint">Type below to hail ${escapeHtml(agentName)}...</div>`;
  } else {
    for (const msg of history) {
      if (msg.role === 'user') {
        html += `<div class="chat-msg chat-user"><span class="chat-prefix">you&gt;</span> ${escapeHtml(msg.content)}</div>`;
      } else {
        html += `<div class="chat-msg chat-agent"><span class="chat-prefix">${escapeHtml(agentName.toLowerCase())}&gt;</span> ${escapeHtml(msg.content)}</div>`;
      }
    }
  }

  html += '</div>';
  html += '<div class="chat-input-row">';
  html += '<span class="chat-dollar">&gt;</span>';
  html += '<input type="text" id="chat-input" class="chat-input" placeholder="Send transmission..." autocomplete="off" maxlength="500">';
  html += '<button id="chat-send" class="chat-send" title="Send">TX</button>';
  html += '</div>';

  return html;
}

export function bindChatEvents() {
  const sendBtn = document.getElementById('chat-send');
  if (sendBtn) {
    sendBtn.addEventListener('click', sendMessage);
  }

  // Auto-scroll to bottom
  const msgBox = document.getElementById('chat-messages');
  if (msgBox) {
    msgBox.scrollTop = msgBox.scrollHeight;
  }

  // Focus input
  const input = document.getElementById('chat-input');
  if (input) {
    setTimeout(() => input.focus(), 100);
  }
}

async function sendMessage() {
  if (sending || !currentAgentId) return;

  const input = document.getElementById('chat-input');
  const msgBox = document.getElementById('chat-messages');
  if (!input || !msgBox) return;

  const text = input.value.trim();
  if (!text) return;

  // Get or create history
  if (!chatHistories.has(currentAgentId)) {
    chatHistories.set(currentAgentId, []);
  }
  const history = chatHistories.get(currentAgentId);

  // Add user message
  history.push({ role: 'user', content: text });
  input.value = '';
  input.disabled = true;
  sending = true;

  // Remove hint if present
  const hint = msgBox.querySelector('.chat-hint');
  if (hint) hint.remove();

  // Render user message
  appendChatMessage(msgBox, 'chat-user', 'you>', text);

  // Show typing indicator
  appendTypingIndicator(msgBox);
  msgBox.scrollTop = msgBox.scrollHeight;

  try {
    const resp = await fetch(CHAT_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agent_id: currentAgentId,
        message: text,
        history: history.slice(0, -1), // exclude the message we just added
      }),
    });

    const data = await resp.json();

    // Remove typing indicator
    const typing = document.getElementById('chat-typing');
    if (typing) typing.remove();

    if (data.response) {
      history.push({ role: 'assistant', content: data.response });
      const agentName = data.agent || 'agent';
      appendChatMessage(msgBox, 'chat-agent', `${agentName.toLowerCase()}>`, data.response);
    } else if (data.error) {
      appendErrorMessage(msgBox, data.error);
    }
  } catch (err) {
    const typing = document.getElementById('chat-typing');
    if (typing) typing.remove();
    appendErrorMessage(msgBox, 'Comms channel unreachable.');
  }

  msgBox.scrollTop = msgBox.scrollHeight;
  input.disabled = false;
  input.focus();
  sending = false;
}

function appendChatMessage(msgBox, className, prefix, message) {
  const msg = document.createElement('div');
  msg.className = `chat-msg ${className}`;

  if (prefix) {
    const prefixSpan = document.createElement('span');
    prefixSpan.className = 'chat-prefix';
    prefixSpan.textContent = prefix;
    msg.appendChild(prefixSpan);
    msg.appendChild(document.createTextNode(' '));
  }

  msg.appendChild(document.createTextNode(String(message ?? '')));
  msgBox.appendChild(msg);
}

function appendErrorMessage(msgBox, message) {
  appendChatMessage(msgBox, 'chat-error', null, `[ERROR] ${String(message ?? '')}`);
}

function appendTypingIndicator(msgBox) {
  const typing = document.createElement('div');
  typing.className = 'chat-typing';
  typing.id = 'chat-typing';

  const dots = document.createElement('span');
  dots.className = 'typing-dots';
  typing.appendChild(dots);
  typing.appendChild(document.createTextNode(' processing...'));
  msgBox.appendChild(typing);
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
