/**
 * RustChain Web Explorer - Main JavaScript
 * Retro DOS/CRT fossipunk blockchain explorer
 */

// === Configuration ===
// Edit this to point to your RustChain node
const CONFIG = {
  NODE_URL: 'https://rustchain.org',
  SCRAPE_INTERVAL: 30000, // 30 seconds
  DEFAULT_THEME: 'amber', // 'amber' | 'green' | 'dos'
};

// === Global State ===
let state = {
  currentSection: 'home',
  connected: false,
  lastUpdate: null,
  stats: null,
  blocks: [],
  miners: [],
  badges: [],
  refreshTimer: null,
};

// === DOM Helpers ===

function $(id) {
  return document.getElementById(id);
}

function showSection(sectionName) {
  // Hide all sections
  document.querySelectorAll('.section').forEach(el => {
    el.classList.remove('active');
  });
  // Show selected section
  $(sectionName).classList.add('active');

  // Update menu active state
  document.querySelectorAll('.menu button').forEach(el => {
    if (el.dataset.section === sectionName) {
      el.classList.add('active');
    } else {
      el.classList.remove('active');
    }
  });

  state.currentSection = sectionName;
}

function setTheme(themeName) {
  document.body.classList.remove('theme-amber', 'theme-green', 'theme-dos');
  if (themeName !== 'amber') {
    document.body.classList.add(`theme-${themeName}`);
  }
  localStorage.setItem('rustchain-explorer-theme', themeName);
}

function getSavedTheme() {
  const saved = localStorage.getItem('rustchain-explorer-theme');
  return saved || CONFIG.DEFAULT_THEME;
}

// === API Client ===

async function apiGet(path) {
  const url = `${CONFIG.NODE_URL}${path}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }
  return await response.json();
}

async function apiPost(path, body) {
  const url = `${CONFIG.NODE_URL}${path}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
  }
  return await response.json();
}

// === Render Functions ===

function updateStatusBar() {
  const connectedEl = $('status-connected');
  const lastUpdateEl = $('status-lastupdate');

  if (state.connected) {
    connectedEl.textContent = 'CONNECTED';
  } else {
    connectedEl.textContent = 'DISCONNECTED';
  }

  if (state.lastUpdate) {
    lastUpdateEl.textContent = new Date(state.lastUpdate).toLocaleString();
  } else {
    lastUpdateEl.textContent = 'NEVER';
  }
}

function renderHome() {
  if (!state.stats) return;

  const el = $('home-content');
  el.innerHTML = `
    <div class="stats-grid">
      <div class="stat-box">
        <div class="label">Current Epoch</div>
        <div class="value">${state.stats.epoch || 0}</div>
      </div>
      <div class="stat-box">
        <div class="label">Active Miners</div>
        <div class="value">${state.stats.activeMiners || 0}</div>
      </div>
      <div class="stat-box">
        <div class="label">Total Supply</div>
        <div class="value">${(state.stats.totalSupply || 0).toFixed(0)} RTC</div>
      </div>
      <div class="stat-box">
        <div class="label">Epoch Pot</div>
        <div class="value">${(state.stats.epochPot || 0).toFixed(2)} RTC</div>
      </div>
    </div>
    ${state.latestBlock ? `
    <div class="panel">
      <h2>Latest Block</h2>
      <div class="block-detail">
        <div class="detail-row">
          <span class="detail-label">Height:</span>
          <span>${state.latestBlock.height}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Miner:</span>
          <span>${state.latestBlock.miner || 'Unknown'}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Timestamp:</span>
          <span>${new Date(state.latestBlock.timestamp * 1000).toLocaleString()}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Transactions:</span>
          <span>${state.latestBlock.transactions ? state.latestBlock.transactions.length : 0}</span>
        </div>
      </div>
    </div>
    ` : ''}
  `;
}

function renderBlocks() {
  const el = $('blocks-content');

  if (state.blocks.length === 0) {
    el.innerHTML = '<div class="loading blinking"></div>';
    return;
  }

  let html = `
    <table class="block-list">
      <thead>
        <tr>
          <th>Height</th>
          <th>Miner</th>
          <th>Txs</th>
          <th>Time</th>
        </tr>
      </thead>
      <tbody>
  `;

  state.blocks.slice(0, 20).forEach(block => {
    const time = new Date(block.timestamp * 1000).toLocaleTimeString();
    const miner = block.miner || 'Unknown';
    const txCount = block.transactions ? block.transactions.length : 0;
    html += `
      <tr onclick="showBlockDetail(${block.height})" style="cursor: pointer;">
        <td>${block.height}</td>
        <td>${miner.split('').slice(0, 10).join('')}...</td>
        <td>${txCount}</td>
        <td>${time}</td>
      </tr>
    `;
  });

  html += `
      </tbody>
    </table>
  `;

  el.innerHTML = html;
}

function showBlockDetail(height) {
  // Open modal or navigate to detail view
  const el = $('block-detail-content');
  const block = state.blocks.find(b => b.height === height);

  if (!block) {
    el.innerHTML = `<div class="error">Block ${height} not found</div>`;
    $('block-detail').classList.add('active');
    $('block-detail').scrollIntoView();
    return;
  }

  let html = `
    <div class="block-detail">
      <div class="detail-row">
        <span class="detail-label">Height:</span>
        <span>${block.height}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Hash:</span>
        <span>${block.hash || 'N/A'}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Previous Hash:</span>
        <span>${block.previousHash || 'N/A'}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Miner:</span>
        <span>${block.miner || 'Unknown'}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Timestamp:</span>
        <span>${new Date(block.timestamp * 1000).toLocaleString()}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">Difficulty:</span>
        <span>${block.difficulty || 'N/A'}</span>
      </div>
    </div>
  `;

  if (block.transactions && block.transactions.length > 0) {
    html += `<div class="tx-list"><h3>Transactions (${block.transactions.length})</h3>`;
    block.transactions.forEach((tx, i) => {
      html += `<div class="tx-item">#${i}: ${typeof tx === 'string' ? tx : JSON.stringify(tx)}</div>`;
    });
    html += `</div>`;
  }

  html += `<br><button onclick="hideBlockDetail()">Back</button>`;

  el.innerHTML = html;
  $('block-detail').classList.add('active');
  $('block-detail').scrollIntoView();
}

function hideBlockDetail() {
  $('block-detail').classList.remove('active');
  $('blocks').scrollIntoView();
}

function renderMiners() {
  const el = $('miners-content');

  if (state.miners.length === 0) {
    el.innerHTML = '<div class="loading blinking"></div>';
    return;
  }

  let html = '';
  state.miners.forEach(miner => {
    if (!miner.isActive) return;
    html += `
      <div class="miner-card">
        <div class="header">
          <span class="miner-id">${miner.minerId || miner.id || 'Unknown'}</span>
          <span class="multiplier">${(miner.antiquityMultiplier || 1.0).toFixed(2)}×</span>
        </div>
        <div class="details">
          <div>Hardware: ${miner.hardwareType || 'Unknown'}</div>
          <div>Architecture: ${miner.deviceArch || miner.arch || 'Unknown'}</div>
          <div>Active: ${miner.isActive ? 'YES' : 'NO'}</div>
          ${miner.lastAttestation ? `<div>Last Seen: ${new Date(miner.lastAttestation * 1000).toLocaleString()}</div>` : ''}
        </div>
      </div>
    `;
  });

  if (html === '') {
    html = '<div class="error">No active miners found</div>';
  }

  el.innerHTML = html;
}

function renderBadges() {
  const el = $('badges-content');

  // Predefined legacy hardware badges
  const defaultBadges = [
    { id: 'intel-486', name: 'Intel 486', icon: '💾', desc: '32-bit legacy CPU', era: '1990s' },
    { id: 'pentium-mmx', name: 'Pentium MMX', icon: '⚙️', desc: 'Multimedia extension', era: '1997' },
    { id: 'powerpc-g4', name: 'PowerPC G4', icon: '🍎', desc: 'RISC architecture', era: '2000s' },
    { id: 'amd-k6', name: 'AMD K6-2', icon: '🔥', desc: '3DNow! pioneer', era: '1998' },
    { id: 'mips-r4k', name: 'MIPS R4000', icon: '🪨', desc: 'Classic RISC', era: '1990s' },
    { id: 'arm-strongarm', name: 'StrongARM', icon: '🔋', desc: 'Low power pioneer', era: '1996' },
    { id: 'cray-ymp', name: 'Cray Y-MP', icon: '🚀', desc: 'Supercomputing legend', era: '1988' },
    { id: 'vacuum-101', name: 'Vacuum Tube', icon: '⚡', desc: 'First generation', era: '1940s' },
  ];

  const badges = state.badges.length > 0 ? state.badges : defaultBadges;

  let html = '<div class="badge-grid">';
  badges.forEach(badge => {
    html += `
      <div class="badge-card">
        <div class="badge-icon">${badge.icon || '🏆'}</div>
        <div class="badge-name">${badge.name}</div>
        <div class="badge-desc">${badge.desc} (${badge.era})</div>
      </div>
    `;
  });
  html += '</div>';

  el.innerHTML = html;
}

// === Faucet Functions ===

function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function(e) {
    try {
      const proof = JSON.parse(e.target.result);
      $('faucet-proof-json').value = JSON.stringify(proof, null, 2);
      updateFaucetPreview(proof);
    } catch (err) {
      showFaucetError(`Invalid JSON: ${err.message}`);
    }
  };
  reader.readAsText(file);
}

function updateFaucetPreview(proof) {
  const preview = $('faucet-preview');
  if (!proof) {
    preview.innerHTML = '';
    return;
  }

  let html = '<h4>Proof Loaded:</h4>';
  html += `<ul>
    <li>CPU: ${proof.cpu_model || 'Unknown'}</li>
    <li>Architecture: ${proof.architecture || 'Unknown'}</li>
    <li>Year: ${proof.year || 'Unknown'}</li>
    <li>Antiquity Score: ${proof.score || 0}</li>
  </ul>`;

  preview.innerHTML = html;
}

async function submitFaucetClaim() {
  const statusEl = $('faucet-status');
  const walletAddr = $('faucet-wallet').value.trim();
  const proofJson = $('faucet-proof-json').value.trim();

  if (!walletAddr) {
    showFaucetError('Please enter your wallet address');
    return;
  }

  if (!proofJson) {
    showFaucetError('Please upload or paste proof_of_antiquity.json');
    return;
  }

  let proof;
  try {
    proof = JSON.parse(proofJson);
  } catch (err) {
    showFaucetError(`Invalid JSON: ${err.message}`);
    return;
  }

  statusEl.innerHTML = '<div class="loading blinking">Submitting claim</div>';

  try {
    const result = await apiPost('/faucet/claim', {
      wallet: walletAddr,
      proof: proof,
    });

    if (result.success) {
      statusEl.innerHTML = `
        <div class="success">
          <strong>✅ Claim Successful!</strong>
          <pre>${JSON.stringify(result, null, 2)}</pre>
          <p>Reward: ${result.reward || 0} RTC will be sent to your wallet</p>
        </div>
      `;
    } else {
      statusEl.innerHTML = `
        <div class="error">
          <strong>❌ Claim Failed</strong>
          <pre>${JSON.stringify(result, null, 2)}</pre>
        </div>
      `;
    }
  } catch (err) {
    showFaucetError(`Request failed: ${err.message}`);
  }
}

function showFaucetError(message) {
  const statusEl = $('faucet-status');
  statusEl.innerHTML = `<div class="error">${message}</div>`;
}

// === Data Fetching ===

async function fetchAllData() {
  try {
    // Fetch node health
    const health = await apiGet('/health');
    state.connected = true;

    // Fetch epoch info
    const epoch = await apiGet('/epoch');
    state.stats = {
      epoch: epoch.epoch || 0,
      epochPot: epoch.epoch_pot || 0,
      activeMiners: epoch.enrolled_miners || 0,
      totalSupply: epoch.total_supply_rtc || 0,
      blocksPerEpoch: epoch.blocks_per_epoch || 0,
    };

    // Fetch miners
    state.miners = await apiGet('/api/miners');

    // Try to fetch latest blocks
    try {
      const blocks = await apiGet('/blocks?limit=20');
      if (Array.isArray(blocks)) {
        state.blocks = blocks;
        if (blocks.length > 0) {
          state.latestBlock = blocks[blocks.length - 1];
        }
      }
    } catch (e) {
      // Some nodes might not expose this endpoint, that's OK
      console.warn('Could not fetch blocks', e);
    }

    state.lastUpdate = Date.now();

    // Re-render everything
    updateStatusBar();
    renderHome();
    renderBlocks();
    renderMiners();
    renderBadges();

  } catch (err) {
    console.error('Fetch error', err);
    state.connected = false;
    updateStatusBar();
    const homeContent = $('home-content');
    homeContent.innerHTML = `<div class="error">Failed to connect to node: ${err.message}<br><br>Check CONFIG.NODE_URL and try refreshing.</div>`;
  }
}

function startAutoRefresh() {
  if (state.refreshTimer) {
    clearInterval(state.refreshTimer);
  }
  state.refreshTimer = setInterval(fetchAllData, CONFIG.SCRAPE_INTERVAL);
}

// === Theme Switching ===

function initTheme() {
  const saved = getSavedTheme();
  setTheme(saved);

  // Update menu checkboxes
  document.querySelectorAll('[data-theme]').forEach(btn => {
    if (btn.dataset.theme === saved) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
}

function switchTheme(themeName) {
  setTheme(themeName);
  initTheme();
}

// === Initialization ===

function initExplorer() {
  // Bind menu clicks
  document.querySelectorAll('[data-section]').forEach(btn => {
    btn.addEventListener('click', () => {
      showSection(btn.dataset.section);
    });
  });

  // Bind theme clicks
  document.querySelectorAll('[data-theme]').forEach(btn => {
    btn.addEventListener('click', () => {
      switchTheme(btn.dataset.theme);
    });
  });

  // Bind file upload
  $('faucet-file').addEventListener('change', handleFileUpload);

  // Bind faucet submit
  $('faucet-submit').addEventListener('click', submitFaucetClaim);

  // Bind manual refresh
  $('btn-refresh').addEventListener('click', fetchAllData);

  // Initialize
  initTheme();
  showSection('home');
  fetchAllData();
  startAutoRefresh();
}

// === Initialize on load ===
document.addEventListener('DOMContentLoaded', initExplorer);
