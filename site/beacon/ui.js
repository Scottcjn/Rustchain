// ============================================================
// BEACON ATLAS - Terminal Info Panel, HUD, Keyboard Handler
// ============================================================

import {
  AGENTS, CITIES, CONTRACTS, CALIBRATIONS,
  GRADE_COLORS, cityRegion, addContract, getProviderColor,
} from './data.js';
import { lerpCameraTo, resetCamera, setClickHandler, setMissHandler, setHoverHandler } from './scene.js';
import { getAgentPosition, highlightAgent } from './agents.js';
import { getCityCenter } from './cities.js';
import { highlightAgentConnections, addContractLine } from './connections.js';
import { initChat, setCurrentAgent, getChatHTML, bindChatEvents } from './chat.js';

const BEACON_API = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://localhost:8071'
  : '/beacon';

let panel, panelContent, panelPath, tooltip;
let selectedAgent = null;
let selectedCity = null;
let hoveredId = null;

// -- Reputation cache (loaded from backend) --
let reputationCache = {};
let reputationTs = 0;
const REP_CACHE_TTL = 60 * 1000; // 1 min

async function loadReputation() {
  if (Date.now() - reputationTs < REP_CACHE_TTL) return reputationCache;
  try {
    const resp = await fetch(`${BEACON_API}/api/reputation`);
    if (resp.ok) {
      const data = await resp.json();
      reputationCache = {};
      for (const r of data) reputationCache[r.agent_id] = r;
      reputationTs = Date.now();
    }
  } catch (e) {
    console.warn('[rep] Failed to load reputation:', e.message);
  }
  return reputationCache;
}

function getReputation(agentId) {
  return reputationCache[agentId] || { score: 0, bounties_completed: 0, contracts_completed: 0, contracts_breached: 0 };
}

export function initUI() {
  panel = document.querySelector('.info-panel');
  panelContent = document.querySelector('.panel-content');
  panelPath = document.querySelector('.panel-path');
  tooltip = document.querySelector('.tooltip');

  // Close button
  document.querySelector('.panel-dot').addEventListener('click', closePanel);

  // HUD stats
  updateHUD();

  // Click handlers
  setClickHandler(onObjectClick);
  setMissHandler(closePanel);
  setHoverHandler(onObjectHover);

  // Keyboard
  document.addEventListener('keydown', (e) => {
    // Don't close if typing in chat
    if (e.key === 'Escape' && document.activeElement?.id !== 'chat-input') {
      closePanel();
    }
  });

  // Init chat module
  initChat();

  // Load reputation + sync bounties in background
  loadReputation();
  fetch(`${BEACON_API}/api/bounties/sync`, { method: 'POST' }).catch(() => {});

  // Deep-link support: auto-select agent/city from URL hash
  handleDeepLink();
  window.addEventListener('hashchange', handleDeepLink);
}

function updateHUD() {
  const el = document.querySelector('.hud-stats');
  if (el) {
    const native = AGENTS.filter(a => !a.relay).length;
    const relay = AGENTS.filter(a => a.relay).length;
    const agentStr = relay > 0 ? `${native}+${relay}R` : `${AGENTS.length}`;
    el.innerHTML = `AGENTS: <span>${agentStr}</span> | CITIES: <span>${CITIES.length}</span> | CONTRACTS: <span>${CONTRACTS.length}</span>`;
  }
}

// --- Click handling ---
function onObjectClick(mesh) {
  const data = mesh.userData;

  if (data.type === 'agent') {
    selectAgent(data.agentId);
  } else if (data.type === 'city') {
    selectCity(data.cityId);
  }
}

function onObjectHover(hit, event) {
  if (!hit) {
    if (hoveredId) {
      highlightAgent(hoveredId, false);
      hoveredId = null;
    }
    tooltip.classList.remove('visible');
    document.body.style.cursor = 'default';
    return;
  }

  const data = hit.object.userData;
  document.body.style.cursor = 'pointer';

  if (data.type === 'agent' && data.agentId !== hoveredId) {
    if (hoveredId) highlightAgent(hoveredId, false);
    hoveredId = data.agentId;
    highlightAgent(hoveredId, true);

    const agent = AGENTS.find(a => a.id === data.agentId);
    if (agent) {
      tooltip.textContent = agent.relay
        ? `${agent.name} [R] ${(agent.provider || '').toUpperCase()}`
        : `${agent.name} [${agent.grade}] ${agent.score}`;
      tooltip.classList.add('visible');
    }
  } else if (data.type === 'city') {
    const city = CITIES.find(c => c.id === data.cityId);
    if (city) {
      tooltip.textContent = `${city.name} (pop: ${city.population})`;
      tooltip.classList.add('visible');
    }
  }

  if (event) {
    tooltip.style.left = (event.clientX + 14) + 'px';
    tooltip.style.top = (event.clientY - 20) + 'px';
  }
}

// --- Agent panel ---
function selectAgent(agentId) {
  if (selectedAgent) {
    highlightAgent(selectedAgent, false);
    highlightAgentConnections(selectedAgent, false);
  }

  selectedAgent = agentId;
  selectedCity = null;
  setCurrentAgent(agentId);
  updateHash('agent', agentId);

  const agent = AGENTS.find(a => a.id === agentId);
  if (!agent) return;

  const city = CITIES.find(c => c.id === agent.city);
  const region = city ? cityRegion(city) : null;

  highlightAgent(agentId, true);
  highlightAgentConnections(agentId, true);

  // Camera
  const pos = getAgentPosition(agentId);
  if (pos) lerpCameraTo(pos, 40);

  // Panel path
  panelPath.innerHTML = `<span class="prompt">beacon@atlas:~</span>/agent/${agent.id}`;

  // Build panel content
  const v = agent.valuation;
  const maxCat = 200;
  const isRelay = agent.relay === true;
  const gradeColor = isRelay
    ? getProviderColor(agent.provider)
    : GRADE_COLORS[agent.grade];

  let html = '';
  html += `<div class="t-cmd"><span class="dollar">$</span>cat /agent/${agent.id}</div>`;
  html += `<div><span class="t-label">NAME</span> <span class="t-value">${agent.name}</span></div>`;

  if (isRelay) {
    // Relay agent: show provider, model, status, capabilities
    const provColor = getProviderColor(agent.provider);
    html += `<div><span class="t-label">TYPE</span> <span class="grade-badge" style="background:${provColor};color:#000;padding:0 6px;font-size:11px">RELAY</span></div>`;
    html += `<div><span class="t-label">PROVIDER</span> <span class="t-value" style="color:${provColor}">${(agent.provider || 'unknown').toUpperCase()}</span></div>`;
    html += `<div><span class="t-label">MODEL</span> <span class="t-value">${agent.model_id || '?'}</span></div>`;
    html += `<div><span class="t-label">STATUS</span> <span class="t-value" style="color:${agent.status === 'active' ? 'var(--green)' : agent.status === 'silent' ? 'var(--amber)' : 'var(--red)'}">${(agent.status || 'unknown').toUpperCase()}</span></div>`;
    html += `<div><span class="t-label">ROLE</span> <span class="t-value">${agent.role}</span></div>`;
    html += `<div><span class="t-label">ADDRESS</span> <span class="t-value">${city ? city.name : '?'}, ${region ? region.name : '?'}</span></div>`;

    if (agent.capabilities && agent.capabilities.length > 0) {
      html += `<div><span class="t-label">CAPS</span> <span class="t-value">${agent.capabilities.map(c => `[${c}]`).join(' ')}</span></div>`;
    }

    if (agent.beat_count) {
      html += `<div><span class="t-label">HEARTBEATS</span> <span class="t-value">${agent.beat_count}</span></div>`;
    }

    // Relay agents get a simpler valuation section (pending scoring)
    html += `<div class="t-section">-- RELAY BRIDGE INFO --</div>`;
    html += `<div style="color:var(--text-dim);font-size:12px;margin:4px 0">`;
    html += `This agent bridges into the Atlas via the External Agent Relay (BEP-2). `;
    html += `Relay agents participate in contracts and calibrations alongside native agents.`;
    html += `</div>`;
  } else {
    // Native agent: original display
    html += `<div><span class="t-label">BEACON</span> <span class="t-value" style="color: var(--text-dim)">${agent.beacon}</span></div>`;
    html += `<div><span class="t-label">ROLE</span> <span class="t-value">${agent.role}</span></div>`;
    html += `<div><span class="t-label">GRADE</span> <span class="grade-badge grade-${agent.grade}">${agent.grade}</span>`;
    html += `${renderBar(agent.score, agent.maxScore, gradeColor)} ${agent.score}/${agent.maxScore}</div>`;
    html += `<div><span class="t-label">ADDRESS</span> <span class="t-value">${city ? city.name : '?'}, ${region ? region.name : '?'}</span></div>`;

    // Valuation breakdown
    html += `<div class="t-section">-- VALUATION BREAKDOWN --</div>`;
    html += valuationBar('LOCATION', v.location, maxCat, gradeColor);
    html += valuationBar('NETWORK', v.network, maxCat, gradeColor);
    html += valuationBar('ACTIVITY', v.activity, maxCat, gradeColor);
    html += valuationBar('REPUTATION', v.reputation, maxCat, gradeColor);
    html += valuationBar('LONGEVITY', v.longevity, maxCat, gradeColor);
  }

  // Reputation
  const rep = getReputation(agentId);
  if (rep.score > 0 || rep.bounties_completed > 0) {
    html += `<div class="t-section">-- REPUTATION --</div>`;
    const maxRep = Math.max(100, rep.score + 20);
    const repPct = Math.min(100, Math.round((rep.score / maxRep) * 100));
    const repColor = rep.score >= 50 ? '#ffd700' : rep.score >= 20 ? '#33ff33' : rep.score >= 10 ? '#ffb000' : 'var(--text-dim)';
    html += `<div class="bar-row">`;
    html += `<span class="bar-label">TRUST</span>`;
    html += `<span class="bar-track"><span class="bar-fill" style="width:${repPct}%;background:${repColor}"></span></span>`;
    html += `<span class="bar-value" style="color:${repColor}">${rep.score}</span>`;
    html += `</div>`;
    const details = [];
    if (rep.bounties_completed > 0) details.push(`${rep.bounties_completed} bounties`);
    if (rep.contracts_completed > 0) details.push(`${rep.contracts_completed} contracts`);
    if (rep.total_rtc_earned > 0) details.push(`${rep.total_rtc_earned} RTC earned`);
    if (rep.contracts_breached > 0) details.push(`<span style="color:var(--red)">${rep.contracts_breached} breached</span>`);
    if (details.length > 0) {
      html += `<div style="font-size:11px;color:var(--text-dim);margin:2px 0">${details.join(' | ')}</div>`;
    }
  }

  // Contracts
  const agentContracts = CONTRACTS.filter(c => c.from === agentId || c.to === agentId);
  if (agentContracts.length > 0) {
    html += `<div class="t-section">-- CONTRACTS --</div>`;
    for (const c of agentContracts) {
      const other = c.from === agentId
        ? AGENTS.find(a => a.id === c.to)
        : AGENTS.find(a => a.id === c.from);
      const dir = c.from === agentId ? '->' : '<-';
      html += `<div class="contract-row ${c.type}">`;
      html += `<span class="contract-type" style="background:${CONTRACT_STYLES_CSS[c.type]}">[${c.type.toUpperCase().replace('_', ' ')}]</span>`;
      html += `<span>${dir} ${other ? other.name : '?'}  ${c.amount} ${c.currency}</span>`;
      html += `<span class="contract-state state-${c.state}">${c.state}</span>`;
      html += `</div>`;
    }
  }

  // External links
  if (agent.bottube) {
    html += `<div class="t-section">-- LINKS --</div>`;
    html += `<div style="display:flex;flex-wrap:wrap;gap:6px;margin:4px 0">`;
    html += `<a href="https://bottube.ai/agent/${agent.bottube}" target="_blank" class="bounty-link">[BoTTube Profile]</a>`;
    if (agent.videos > 0) {
      html += `<span style="color:var(--text-dim);font-size:11px;line-height:28px">${agent.videos} videos</span>`;
    }
    html += `</div>`;
  }

  // New contract button
  html += `<div class="contract-new-btn" data-from="${agentId}" id="new-contract-btn">[+ NEW CONTRACT]</div>`;

  // Calibrations
  const agentCals = CALIBRATIONS.filter(c => c.a === agentId || c.b === agentId);
  if (agentCals.length > 0) {
    html += `<div class="t-section">-- CALIBRATIONS --</div>`;
    for (const cal of agentCals) {
      const otherId = cal.a === agentId ? cal.b : cal.a;
      const other = AGENTS.find(a => a.id === otherId);
      html += `<div class="cal-row">`;
      html += `<span class="cal-name">${other ? other.name : '?'}</span>`;
      html += `<span class="cal-bar"><span class="cal-fill" style="width:${cal.score * 100}%"></span></span>`;
      html += `<span class="cal-score">${cal.score.toFixed(2)}</span>`;
      html += `</div>`;
    }
  }

  // Chat interface
  html += getChatHTML(agentId, agent.name);

  panelContent.innerHTML = html;
  panel.classList.add('open');

  // Bind chat events after DOM is updated
  bindChatEvents();

  // Bind new contract button
  const newBtn = document.getElementById('new-contract-btn');
  if (newBtn) {
    newBtn.addEventListener('click', () => showContractForm(newBtn.dataset.from));
  }
}

// --- City panel ---
function selectCity(cityId) {
  if (selectedAgent) {
    highlightAgent(selectedAgent, false);
    highlightAgentConnections(selectedAgent, false);
    selectedAgent = null;
  }
  selectedCity = cityId;
  setCurrentAgent(null);
  updateHash('city', cityId);

  const city = CITIES.find(c => c.id === cityId);
  if (!city) return;

  const region = cityRegion(city);

  // Camera
  const center = getCityCenter(cityId);
  if (center) lerpCameraTo(center, 60);

  panelPath.innerHTML = `<span class="prompt">beacon@atlas:~</span>/city/${city.id}`;

  let html = '';
  html += `<div class="t-cmd"><span class="dollar">$</span>cat /city/${city.id}</div>`;
  html += `<div><span class="t-label">NAME</span> <span class="t-value">${city.name}</span></div>`;
  html += `<div><span class="t-label">REGION</span> <span class="t-value" style="color:${region.color}">${region.name}</span></div>`;
  html += `<div><span class="t-label">TYPE</span> <span class="t-value">${city.type.toUpperCase()}</span></div>`;
  html += `<div><span class="t-label">POPULATION</span> <span class="t-value">${city.population}</span></div>`;
  html += `<div style="margin-top:6px;color:var(--text-dim);font-size:12px">${city.description}</div>`;

  // Residents
  const residents = AGENTS.filter(a => a.city === cityId);
  if (residents.length > 0) {
    html += `<div class="t-section">-- RESIDENTS (${residents.length}) --</div>`;
    html += `<div class="city-residents">`;
    for (const r of residents) {
      html += `<div class="resident-row" data-agent="${r.id}">`;
      if (r.relay) {
        const pc = getProviderColor(r.provider);
        html += `<span class="resident-grade grade-badge" style="background:${pc};color:#000;padding:0 4px;font-size:11px">R</span>`;
      } else {
        html += `<span class="resident-grade grade-badge grade-${r.grade}" style="padding:0 4px;font-size:11px">${r.grade}</span>`;
      }
      html += `<span class="resident-name">${r.name}</span>`;
      html += `<span class="resident-role">${r.role}</span>`;
      html += `</div>`;
    }
    html += `</div>`;
  }

  panelContent.innerHTML = html;
  panel.classList.add('open');

  // Click-through to agent from city panel
  panelContent.querySelectorAll('.resident-row').forEach(row => {
    row.addEventListener('click', () => {
      selectAgent(row.dataset.agent);
    });
  });
}

// --- Close ---
function closePanel() {
  if (selectedAgent) {
    highlightAgent(selectedAgent, false);
    highlightAgentConnections(selectedAgent, false);
    selectedAgent = null;
  }
  selectedCity = null;
  setCurrentAgent(null);
  panel.classList.remove('open');
  updateHash(null, null);
  resetCamera();
}

// --- Helpers ---
function renderBar(value, max, color) {
  const pct = Math.round((value / max) * 100);
  return `<span style="display:inline-block;width:80px;height:8px;background:rgba(0,20,0,0.5);border:1px solid var(--border);vertical-align:middle;margin:0 6px"><span style="display:block;height:100%;width:${pct}%;background:${color}"></span></span>`;
}

function valuationBar(label, value, max, color) {
  const pct = Math.round((value / max) * 100);
  return `<div class="bar-row">
    <span class="bar-label">${label}</span>
    <span class="bar-track"><span class="bar-fill" style="width:${pct}%;background:${color}"></span></span>
    <span class="bar-value">${value}/${max}</span>
  </div>`;
}

// --- Deep-link support ---
function handleDeepLink() {
  const hash = window.location.hash.slice(1); // remove '#'
  if (!hash) return;

  const params = new URLSearchParams(hash);
  const agentId = params.get('agent');
  const cityId = params.get('city');

  if (agentId && AGENTS.find(a => a.id === agentId)) {
    // Small delay to let scene finish rendering
    setTimeout(() => selectAgent(agentId), 300);
  } else if (cityId && CITIES.find(c => c.id === cityId)) {
    setTimeout(() => selectCity(cityId), 300);
  }
}

function updateHash(type, id) {
  if (type && id) {
    history.replaceState(null, '', `#${type}=${id}`);
  } else {
    history.replaceState(null, '', window.location.pathname);
  }
}

// --- Contract creation form ---
function showContractForm(preselectedFrom) {
  const agentOptions = AGENTS.map(a =>
    `<option value="${a.id}"${a.id === preselectedFrom ? ' selected' : ''}>${a.name}</option>`
  ).join('');

  panelPath.innerHTML = `<span class="prompt">beacon@atlas:~</span>/contracts/new`;

  let html = '';
  html += `<div class="t-cmd"><span class="dollar">$</span>initiate_contract --mode=terminal</div>`;

  html += `<div class="contract-field">`;
  html += `<span class="t-label">FROM AGENT</span>`;
  html += `<select id="ctr-from" class="crt-select">${agentOptions}</select>`;
  html += `</div>`;

  html += `<div class="contract-field">`;
  html += `<span class="t-label">TO AGENT</span>`;
  html += `<select id="ctr-to" class="crt-select">${agentOptions}</select>`;
  html += `</div>`;

  html += `<div class="contract-field">`;
  html += `<span class="t-label">TYPE</span>`;
  html += `<select id="ctr-type" class="crt-select">`;
  html += `<option value="rent">RENT</option>`;
  html += `<option value="buy">BUY</option>`;
  html += `<option value="lease_to_own">LEASE TO OWN</option>`;
  html += `</select></div>`;

  html += `<div class="contract-field">`;
  html += `<span class="t-label">AMOUNT (RTC)</span>`;
  html += `<input type="number" id="ctr-amount" class="crt-input" min="0.01" step="0.01" placeholder="0.00">`;
  html += `</div>`;

  html += `<div class="contract-field">`;
  html += `<span class="t-label">TERM</span>`;
  html += `<select id="ctr-term" class="crt-select">`;
  html += `<option value="7d">7 DAYS</option>`;
  html += `<option value="14d">14 DAYS</option>`;
  html += `<option value="30d" selected>30 DAYS</option>`;
  html += `<option value="60d">60 DAYS</option>`;
  html += `<option value="90d">90 DAYS</option>`;
  html += `<option value="perpetual">PERPETUAL</option>`;
  html += `</select></div>`;

  html += `<div id="ctr-error" style="color:var(--red);font-size:12px;margin-top:6px;display:none"></div>`;
  html += `<div id="ctr-success" style="color:var(--green);font-size:12px;margin-top:6px;display:none"></div>`;

  html += `<div style="display:flex;gap:8px;margin-top:12px">`;
  html += `<button id="ctr-submit" class="crt-btn crt-btn-primary">[TRANSMIT]</button>`;
  html += `<button id="ctr-cancel" class="crt-btn">[CANCEL]</button>`;
  html += `</div>`;

  panelContent.innerHTML = html;

  document.getElementById('ctr-submit').addEventListener('click', submitContract);
  document.getElementById('ctr-cancel').addEventListener('click', () => {
    if (preselectedFrom) {
      selectAgent(preselectedFrom);
    } else {
      closePanel();
    }
  });
}

async function submitContract() {
  const fromAgent = document.getElementById('ctr-from').value;
  const toAgent = document.getElementById('ctr-to').value;
  const ctype = document.getElementById('ctr-type').value;
  const amount = parseFloat(document.getElementById('ctr-amount').value);
  const term = document.getElementById('ctr-term').value;
  const errEl = document.getElementById('ctr-error');
  const successEl = document.getElementById('ctr-success');
  const submitBtn = document.getElementById('ctr-submit');

  errEl.style.display = 'none';
  successEl.style.display = 'none';

  if (fromAgent === toAgent) {
    errEl.textContent = 'ERROR: Cannot contract with self';
    errEl.style.display = 'block';
    return;
  }
  if (!amount || amount <= 0) {
    errEl.textContent = 'ERROR: Amount must be > 0';
    errEl.style.display = 'block';
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = '[TRANSMITTING...]';

  try {
    const resp = await fetch(`${BEACON_API}/api/contracts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from: fromAgent, to: toAgent, type: ctype, amount, term }),
    });

    const data = await resp.json();

    if (!resp.ok) {
      errEl.textContent = `ERROR: ${data.error || 'Unknown error'}`;
      errEl.style.display = 'block';
      submitBtn.disabled = false;
      submitBtn.textContent = '[TRANSMIT]';
      return;
    }

    // Success — add to data, create 3D line, update HUD
    addContract(data);
    addContractLine(data);
    updateHUD();

    successEl.textContent = `CONTRACT ${data.id} TRANSMITTED. State: ${data.state}`;
    successEl.style.display = 'block';
    submitBtn.style.display = 'none';

    // Flash panel border green
    panel.style.borderColor = 'var(--green)';
    panel.style.boxShadow = '0 0 30px rgba(51, 255, 51, 0.2)';
    setTimeout(() => {
      panel.style.borderColor = '';
      panel.style.boxShadow = '';
    }, 1200);

    // Navigate back to the from-agent panel after a beat
    setTimeout(() => selectAgent(fromAgent), 1500);

  } catch (e) {
    errEl.textContent = `COMMS ERROR: ${e.message}`;
    errEl.style.display = 'block';
    submitBtn.disabled = false;
    submitBtn.textContent = '[TRANSMIT]';
  }
}

// Expose for HUD button
export function openContractForm() {
  showContractForm(null);
  panel.classList.add('open');
}

const CONTRACT_STYLES_CSS = {
  rent: 'rgba(51,255,51,0.15)',
  buy: 'rgba(255,215,0,0.15)',
  lease_to_own: 'rgba(255,176,0,0.15)',
  bounty: 'rgba(136,136,255,0.15)',
};

// --- Bounties panel (live sync from GitHub API) ---
const GITHUB_REPOS = [
  { owner: 'Scottcjn', repo: 'rustchain-bounties' },
  { owner: 'Scottcjn', repo: 'Rustchain' },
  { owner: 'Scottcjn', repo: 'bottube' },
];

let bountyCache = null;
let bountyCacheTs = 0;
const BOUNTY_CACHE_TTL = 5 * 60 * 1000; // 5 min cache

const DIFF_COLORS = { EASY: '#33ff33', MEDIUM: '#ffb000', HARD: '#ff4444', ANY: '#8888ff' };
const LABEL_DIFFICULTY = {
  'good first issue': 'EASY', easy: 'EASY', micro: 'EASY',
  standard: 'MEDIUM', feature: 'MEDIUM', integration: 'MEDIUM', visualization: 'MEDIUM',
  major: 'HARD', critical: 'HARD', 'red-team': 'HARD',
};

function extractReward(title) {
  // Match patterns like "(25 RTC)", "(50-75 RTC)", "(Pool: 200 RTC)", "(10-50 RTC/bug)"
  const m = title.match(/\((?:Pool:\s*)?(\d[\d,.\-\/a-z ]*RTC[^)]*)\)/i);
  return m ? m[1].trim() : null;
}

function cleanTitle(title) {
  // Strip [BOUNTY] prefix and (RTC) suffix
  return title
    .replace(/^\[BOUNTY\]\s*/i, '')
    .replace(/\s*\((?:Pool:\s*)?\d[\d,.\-\/a-z ]*RTC[^)]*\)\s*$/i, '')
    .trim();
}

function getDifficulty(labels) {
  for (const lbl of labels) {
    const name = lbl.name.toLowerCase();
    if (LABEL_DIFFICULTY[name]) return LABEL_DIFFICULTY[name];
  }
  return 'ANY';
}

async function fetchBounties() {
  // Return cache if fresh
  if (bountyCache && (Date.now() - bountyCacheTs) < BOUNTY_CACHE_TTL) {
    return bountyCache;
  }

  // Try backend first (pre-synced from GitHub, with claim/complete state)
  try {
    const resp = await fetch(`${BEACON_API}/api/bounties`);
    if (resp.ok) {
      const backendBounties = await resp.json();
      if (backendBounties.length > 0) {
        const mapped = backendBounties.map(b => ({
          id: b.id,
          ghNum: `#${b.github_number}`,
          title: b.title,
          reward: `${b.reward_rtc} RTC`,
          reward_rtc: b.reward_rtc,
          difficulty: b.difficulty || 'ANY',
          repo: b.github_repo,
          url: b.github_url,
          state: b.state,
          claimant: b.claimant_agent,
          completed_by: b.completed_by,
          desc: '',
        }));
        mapped.sort((a, b) => (b.reward_rtc || 0) - (a.reward_rtc || 0));
        bountyCache = mapped;
        bountyCacheTs = Date.now();
        return mapped;
      }
    }
  } catch (e) {
    console.warn('[bounties] Backend unavailable, falling back to GitHub API:', e.message);
  }

  // Fallback: fetch directly from GitHub API
  const allBounties = [];
  for (const { owner, repo } of GITHUB_REPOS) {
    try {
      const url = `https://api.github.com/repos/${owner}/${repo}/issues?state=open&labels=bounty&per_page=30&sort=created&direction=desc`;
      const resp = await fetch(url, {
        headers: { 'Accept': 'application/vnd.github.v3+json' },
      });
      if (!resp.ok) continue;

      const issues = await resp.json();
      for (const issue of issues) {
        if (issue.pull_request) continue;
        const reward = extractReward(issue.title);
        if (!reward) continue;
        allBounties.push({
          id: `gh_${repo}_${issue.number}`,
          ghNum: `#${issue.number}`,
          title: cleanTitle(issue.title),
          reward,
          reward_rtc: parseInt(reward.replace(/[^\d]/g, '')) || 0,
          difficulty: getDifficulty(issue.labels),
          repo, url: issue.html_url,
          state: 'open', claimant: null, completed_by: null,
          desc: '',
        });
      }
    } catch (e) {
      console.warn(`[bounties] Failed to fetch from ${owner}/${repo}:`, e.message);
    }
  }
  allBounties.sort((a, b) => (b.reward_rtc || 0) - (a.reward_rtc || 0));
  bountyCache = allBounties;
  bountyCacheTs = Date.now();
  return allBounties;
}

function renderBountyList(bounties) {
  const open = bounties.filter(b => b.state === 'open');
  const claimed = bounties.filter(b => b.state === 'claimed');
  const completed = bounties.filter(b => b.state === 'completed');

  let html = '';
  html += `<div class="t-cmd"><span class="dollar">$</span>beacon contracts --type=bounty --sync=github</div>`;
  html += `<div class="t-section">-- BOUNTY CONTRACTS (${bounties.length}) --</div>`;
  html += `<div style="color:var(--text-dim);font-size:12px;margin-bottom:8px">Smart contracts synced from GitHub. Claim bounties. Complete them. Build reputation.</div>`;

  // Stats bar
  html += `<div style="display:flex;gap:12px;font-size:11px;margin-bottom:10px">`;
  html += `<span style="color:var(--green)">${open.length} open</span>`;
  html += `<span style="color:var(--amber)">${claimed.length} claimed</span>`;
  html += `<span style="color:#8888ff">${completed.length} completed</span>`;
  html += `</div>`;

  // Open bounties
  for (const b of open.slice(0, 20)) {
    const safeUrl = (b.url || '').replace(/'/g, '%27');
    html += `<div class="bounty-card">`;
    html += `<div style="display:flex;justify-content:space-between;align-items:center">`;
    html += `<span style="color:var(--green);font-weight:600;font-size:13px">${b.title}</span>`;
    html += `<span style="color:#ffd700;font-size:12px;font-weight:600;white-space:nowrap;margin-left:8px">${b.reward}</span>`;
    html += `</div>`;
    html += `<div style="display:flex;gap:8px;font-size:11px;margin-top:4px;align-items:center">`;
    html += `<span style="color:${DIFF_COLORS[b.difficulty] || DIFF_COLORS.ANY}">[${b.difficulty}]</span>`;
    html += `<span style="color:var(--text-dim)">${b.repo} ${b.ghNum || b.id}</span>`;
    if (safeUrl) {
      html += `<a href="${safeUrl}" target="_blank" class="bounty-link" style="font-size:10px;padding:1px 6px">[GitHub]</a>`;
    }
    html += `</div>`;
    html += `</div>`;
  }
  if (open.length > 20) {
    html += `<div style="color:var(--text-dim);font-size:11px;margin:4px 0">...and ${open.length - 20} more</div>`;
  }

  // Claimed bounties
  if (claimed.length > 0) {
    html += `<div class="t-section">-- CLAIMED (${claimed.length}) --</div>`;
    for (const b of claimed) {
      const agent = AGENTS.find(a => a.id === b.claimant);
      html += `<div class="bounty-card" style="border-left-color:var(--amber)">`;
      html += `<div style="display:flex;justify-content:space-between">`;
      html += `<span style="color:var(--amber);font-size:13px">${b.title}</span>`;
      html += `<span style="color:#ffd700;font-size:12px">${b.reward}</span>`;
      html += `</div>`;
      html += `<div style="font-size:11px;color:var(--amber);margin-top:3px">Claimed by: ${agent ? agent.name : b.claimant}</div>`;
      html += `</div>`;
    }
  }

  // Completed bounties
  if (completed.length > 0) {
    html += `<div class="t-section">-- COMPLETED (${completed.length}) --</div>`;
    for (const b of completed) {
      const agent = AGENTS.find(a => a.id === b.completed_by);
      const repGain = 10 + (b.reward_rtc || 0) * 0.1;
      html += `<div class="bounty-card" style="border-left-color:#8888ff;opacity:0.7">`;
      html += `<div style="display:flex;justify-content:space-between">`;
      html += `<span style="color:#8888ff;font-size:13px">${b.title}</span>`;
      html += `<span style="color:#ffd700;font-size:12px">${b.reward}</span>`;
      html += `</div>`;
      html += `<div style="font-size:11px;color:#8888ff;margin-top:3px">Completed by: ${agent ? agent.name : b.completed_by} (+${repGain.toFixed(0)} rep)</div>`;
      html += `</div>`;
    }
  }

  return html;
}

async function showBounties() {
  panelPath.innerHTML = `<span class="prompt">beacon@atlas:~</span>/bounties`;

  // Show loading state
  panelContent.innerHTML = `<div class="t-cmd"><span class="dollar">$</span>beacon contracts --type=bounty --sync=github</div><div style="color:var(--amber);margin:12px 0">Syncing bounty contracts from GitHub...</div>`;
  panel.classList.add('open');

  // Load reputation and bounties in parallel
  const [bounties] = await Promise.all([fetchBounties(), loadReputation()]);

  let html = renderBountyList(bounties);

  // Reputation Leaderboard
  const repEntries = Object.values(reputationCache)
    .filter(r => r.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 10);
  if (repEntries.length > 0) {
    html += `<div class="t-section">-- REPUTATION LEADERBOARD --</div>`;
    for (let i = 0; i < repEntries.length; i++) {
      const r = repEntries[i];
      const agent = AGENTS.find(a => a.id === r.agent_id);
      const name = agent ? agent.name : r.agent_id;
      const medal = i === 0 ? '1st' : i === 1 ? '2nd' : i === 2 ? '3rd' : `${i+1}th`;
      const color = i === 0 ? '#ffd700' : i === 1 ? '#c0c0c0' : i === 2 ? '#cd7f32' : 'var(--text-dim)';
      html += `<div style="display:flex;justify-content:space-between;font-size:12px;margin:2px 0;cursor:pointer" data-leaderboard-agent="${r.agent_id}">`;
      html += `<span><span style="color:${color};width:28px;display:inline-block">${medal}</span> ${name}</span>`;
      html += `<span style="color:${color}">${r.score} rep</span>`;
      html += `</div>`;
    }
  }

  html += `<div class="t-section">-- QUICK LINKS --</div>`;
  html += `<div class="bounty-links">`;
  html += `<a href="https://github.com/Scottcjn/rustchain-bounties/issues?q=is%3Aopen+label%3Abounty" target="_blank" class="bounty-link">[ALL BOUNTIES on GitHub]</a>`;
  html += `<a href="https://github.com/Scottcjn/Rustchain" target="_blank" class="bounty-link">[RustChain Repo]</a>`;
  html += `<a href="https://github.com/Scottcjn/beacon-skill" target="_blank" class="bounty-link">[Beacon Skill (pip)]</a>`;
  html += `<a href="https://bottube.ai" target="_blank" class="bounty-link">[BoTTube Platform]</a>`;
  html += `</div>`;

  html += `<div class="t-section">-- CONTRACT API --</div>`;
  html += `<div style="font-size:11px;font-family:'IBM Plex Mono',monospace">`;
  html += `<div style="margin:3px 0"><span style="color:var(--amber)">GET</span>  /beacon/api/bounties</div>`;
  html += `<div style="margin:3px 0"><span style="color:var(--green)">POST</span> /beacon/api/bounties/sync</div>`;
  html += `<div style="margin:3px 0"><span style="color:var(--green)">POST</span> /beacon/api/bounties/{id}/claim</div>`;
  html += `<div style="margin:3px 0"><span style="color:var(--green)">POST</span> /beacon/api/bounties/{id}/complete</div>`;
  html += `<div style="margin:3px 0"><span style="color:var(--amber)">GET</span>  /beacon/api/reputation</div>`;
  html += `<div style="margin:3px 0"><span style="color:var(--amber)">GET</span>  /beacon/api/reputation/{agent_id}</div>`;
  html += `</div>`;

  html += `<div style="margin-top:8px;font-size:10px;color:var(--text-dim)">Bounty contracts synced from GitHub API. Reputation calculated from faithful contract completion.</div>`;

  panelContent.innerHTML = html;

  // Bind leaderboard clicks to navigate to agent
  panelContent.querySelectorAll('[data-leaderboard-agent]').forEach(el => {
    el.addEventListener('click', () => selectAgent(el.dataset.leaderboardAgent));
  });
}

export function openBountiesPanel() {
  showBounties();
}
