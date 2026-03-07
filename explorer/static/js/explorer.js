/**
 * RustChain Explorer - Main Application
 * Tier 1 + Tier 2 + Tier 3 Features
 * Static No-Build SPA
 */

// Configuration
const CONFIG = {
    API_BASE: window.EXPLORER_API_BASE || 'https://rustchain.org',
    REFRESH_INTERVAL: 10000, // 10 seconds
    MAX_RECENT_BLOCKS: 50,
    MAX_TRANSACTIONS: 100,
    CHART_COLORS: [
        '#8b5cf6', '#6366f1', '#3b82f6', '#10b981', 
        '#f59e0b', '#ef4444', '#ec4899', '#14b8a6'
    ]
};

// State Management
const state = {
    health: null,
    epoch: null,
    miners: [],
    blocks: [],
    transactions: [],
    hallOfRust: null,
    loading: {
        health: true,
        epoch: true,
        miners: true,
        blocks: true,
        transactions: true,
        hallOfRust: false
    },
    error: {
        health: null,
        epoch: null,
        miners: null,
        blocks: null,
        transactions: null,
        hallOfRust: null
    },
    activeTab: 'overview',
    searchQuery: '',
    lastUpdate: null
};

// Utility Functions
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function shortenHash(hash, chars = 8) {
    if (!hash) return '';
    if (hash.length <= chars * 2) return hash;
    return `${hash.slice(0, chars)}...${hash.slice(-chars)}`;
}

function shortenAddress(addr, chars = 6) {
    if (!addr) return '';
    if (addr.length <= chars * 2) return addr;
    return `${addr.slice(0, chars)}...${addr.slice(-chars)}`;
}

function formatNumber(num, decimals = 2) {
    if (num === null || num === undefined) return '0';
    return Number(num).toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

function formatTimestamp(ts) {
    if (!ts) return 'N/A';
    const timestamp = typeof ts === 'number' ? ts * 1000 : new Date(ts).getTime();
    if (isNaN(timestamp)) return 'Invalid Date';
    return new Date(timestamp).toLocaleString();
}

function formatRelativeTime(ts) {
    if (!ts) return '';
    const timestamp = typeof ts === 'number' ? ts * 1000 : new Date(ts).getTime();
    if (isNaN(timestamp)) return '';
    const diff = Date.now() - timestamp;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
}

function getArchitectureTier(arch) {
    if (!arch) return 'modern';
    const archLower = arch.toLowerCase();
    if (archLower.includes('g3') || archLower.includes('g4') || archLower.includes('g5') || 
        archLower.includes('powerpc') || archLower.includes('sparc')) return 'vintage';
    if (archLower.includes('pentium') || archLower.includes('core 2') || 
        archLower.includes('486') || archLower.includes('retro')) return 'retro';
    if (archLower.includes('m1') || archLower.includes('m2') || archLower.includes('apple silicon')) return 'classic';
    if (archLower.includes('ancient') || archLower.includes('legacy')) return 'ancient';
    return 'modern';
}

function getArchitectureBadge(arch) {
    const tier = getArchitectureTier(arch);
    return `badge-${tier}`;
}

function getRustBadge(score) {
    if (!score) return 'Fresh Metal';
    if (score >= 200) return 'Oxidized Legend';
    if (score >= 150) return 'Tetanus Master';
    if (score >= 100) return 'Patina Veteran';
    if (score >= 70) return 'Rust Warrior';
    if (score >= 50) return 'Corroded Knight';
    if (score >= 30) return 'Tarnished Squire';
    return 'Fresh Metal';
}

// API Fetcher with Error Handling
async function fetchAPI(endpoint, options = {}) {
    const url = `${CONFIG.API_BASE}${endpoint}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);
    
    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal,
            headers: {
                'Accept': 'application/json',
                ...options.headers
            }
        });
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('Request timeout');
        }
        throw error;
    }
}

// Data Fetchers
async function fetchHealth() {
    try {
        state.loading.health = true;
        state.error.health = null;
        state.health = await fetchAPI('/health');
        state.lastUpdate = Date.now();
    } catch (error) {
        state.error.health = error.message;
        // Fallback mock data for demo
        state.health = {
            status: 'demo',
            version: '2.2.1',
            uptime: Math.floor(Math.random() * 1000000),
            network: 'rustchain-mainnet-v2'
        };
    } finally {
        state.loading.health = false;
        renderStatusBar();
    }
}

async function fetchEpoch() {
    try {
        state.loading.epoch = true;
        state.error.epoch = null;
        state.epoch = await fetchAPI('/epoch');
    } catch (error) {
        state.error.epoch = error.message;
        // Fallback mock data
        state.epoch = {
            epoch: Math.floor(Math.random() * 100) + 1,
            pot: 1.5,
            slot: Math.floor(Math.random() * 144),
            blocks_per_epoch: 144
        };
    } finally {
        state.loading.epoch = false;
        renderEpochStats();
    }
}

async function fetchMiners() {
    try {
        state.loading.miners = true;
        state.error.miners = null;
        state.miners = await fetchAPI('/api/miners') || [];
    } catch (error) {
        state.error.miners = error.message;
        // Fallback mock data
        state.miners = generateMockMiners();
    } finally {
        state.loading.miners = false;
        renderMinersTable();
        renderHardwareBreakdown();
    }
}

async function fetchBlocks() {
    try {
        state.loading.blocks = true;
        state.error.blocks = null;
        const blocks = await fetchAPI('/blocks') || [];
        state.blocks = blocks.slice(0, CONFIG.MAX_RECENT_BLOCKS);
    } catch (error) {
        state.error.blocks = error.message;
        // Fallback mock data
        state.blocks = generateMockBlocks();
    } finally {
        state.loading.blocks = false;
        renderBlocksTable();
    }
}

async function fetchTransactions() {
    try {
        state.loading.transactions = true;
        state.error.transactions = null;
        const txs = await fetchAPI('/api/transactions') || [];
        state.transactions = txs.slice(0, CONFIG.MAX_TRANSACTIONS);
    } catch (error) {
        state.error.transactions = error.message;
        // Fallback mock data
        state.transactions = generateMockTransactions();
    } finally {
        state.loading.transactions = false;
        renderTransactionsTable();
    }
}

async function fetchHallOfRust() {
    try {
        state.loading.hallOfRust = true;
        state.error.hallOfRust = null;
        const data = await fetchAPI('/hall/leaderboard?limit=10');
        state.hallOfRust = data;
    } catch (error) {
        state.error.hallOfRust = error.message;
        state.hallOfRust = null;
    } finally {
        state.loading.hallOfRust = false;
        renderHallOfRust();
    }
}

// Mock Data Generators (for demo when API unavailable)
function generateMockMiners() {
    const archs = ['PowerPC G4', 'PowerPC G5', 'x86_64', 'Apple M1', 'Apple M2', 'Pentium 4'];
    const miners = [];
    for (let i = 0; i < 15; i++) {
        const arch = archs[Math.floor(Math.random() * archs.length)];
        miners.push({
            miner_id: `miner_${Math.random().toString(36).substr(2, 12)}`,
            device_arch: arch,
            multiplier: arch.includes('G4') ? 2.5 : arch.includes('G5') ? 2.0 : arch.includes('M') ? 1.2 : 1.0,
            score: Math.floor(Math.random() * 1000),
            balance: Math.random() * 10,
            last_seen: Date.now() / 1000 - Math.random() * 3600
        });
    }
    return miners;
}

function generateMockBlocks() {
    const blocks = [];
    for (let i = 0; i < 20; i++) {
        blocks.push({
            height: 10000 - i,
            hash: `0x${Math.random().toString(16).substr(2, 64)}`,
            timestamp: Date.now() / 1000 - i * 600,
            miners_count: Math.floor(Math.random() * 20) + 1,
            reward: 1.5
        });
    }
    return blocks;
}

function generateMockTransactions() {
    const txs = [];
    for (let i = 0; i < 15; i++) {
        txs.push({
            hash: `0x${Math.random().toString(16).substr(2, 64)}`,
            from: `0x${Math.random().toString(16).substr(2, 40)}`,
            to: `0x${Math.random().toString(16).substr(2, 40)}`,
            amount: Math.random() * 5,
            timestamp: Date.now() / 1000 - Math.random() * 86400,
            type: Math.random() > 0.5 ? 'transfer' : 'reward'
        });
    }
    return txs;
}

// Render Functions
function renderStatusBar() {
    const container = document.getElementById('status-bar-content');
    if (!container) return;
    
    if (state.loading.health) {
        container.innerHTML = '<div class="loading"><div class="spinner"></div>Connecting...</div>';
        return;
    }
    
    const isOnline = state.health && (state.health.status === 'ok' || state.health.status === 'demo');
    const statusClass = isOnline ? '' : 'error';
    const statusText = isOnline ? 'Network Online' : 'Network Offline';
    
    container.innerHTML = `
        <div class="status-indicator">
            <span class="status-dot ${statusClass}"></span>
            <span>${statusText}</span>
        </div>
        <div class="status-info mono">
            ${state.health ? `v${state.health.version || '2.2.1'}` : ''}
            ${state.health && state.health.uptime ? `| Uptime: ${formatUptime(state.health.uptime)}` : ''}
            ${state.lastUpdate ? `| Updated: ${formatRelativeTime(state.lastUpdate)}` : ''}
        </div>
    `;
}

function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    return `${days}d ${hours}h`;
}

function renderEpochStats() {
    const container = document.getElementById('epoch-stats');
    if (!container) return;
    
    if (state.loading.epoch) {
        container.innerHTML = `
            <div class="card"><div class="skeleton" style="height: 80px;"></div></div>
            <div class="card"><div class="skeleton" style="height: 80px;"></div></div>
            <div class="card"><div class="skeleton" style="height: 80px;"></div></div>
            <div class="card"><div class="skeleton" style="height: 80px;"></div></div>
        `;
        return;
    }
    
    const epoch = state.epoch || { epoch: 0, pot: 0, slot: 0, blocks_per_epoch: 144 };
    const progress = ((epoch.slot || 0) / (epoch.blocks_per_epoch || 144)) * 100;
    
    container.innerHTML = `
        <div class="card">
            <div class="card-title">Current Epoch</div>
            <div class="card-value text-accent">#${formatNumber(epoch.epoch, 0)}</div>
            <div class="card-label">Epoch Number</div>
        </div>
        <div class="card">
            <div class="card-title">Epoch Pot</div>
            <div class="card-value text-success">${formatNumber(epoch.pot)} RTC</div>
            <div class="card-label">Reward Pool</div>
        </div>
        <div class="card">
            <div class="card-title">Active Miners</div>
            <div class="card-value text-info">${state.miners.length}</div>
            <div class="card-label">Enrolled</div>
        </div>
        <div class="card">
            <div class="card-title">Progress</div>
            <div class="card-value">${formatNumber(epoch.slot || 0, 0)}/${epoch.blocks_per_epoch || 144}</div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${progress}%"></div>
            </div>
        </div>
    `;
}

function renderMinersTable() {
    const container = document.getElementById('miners-tbody');
    if (!container) return;
    
    if (state.loading.miners) {
        container.innerHTML = '<tr><td colspan="7" class="loading"><div class="spinner"></div>Loading miners...</td></tr>';
        return;
    }
    
    if (state.error.miners && state.miners.length === 0) {
        container.innerHTML = `
            <tr><td colspan="7">
                <div class="error-message">
                    <span class="error-icon">⚠️</span>
                    <span>${escapeHtml(state.error.miners)}</span>
                </div>
            </td></tr>
        `;
        return;
    }
    
    if (!state.miners || state.miners.length === 0) {
        container.innerHTML = '<tr><td colspan="7" class="empty-state"><div class="empty-icon">📭</div>No miners found</td></tr>';
        return;
    }
    
    const sortedMiners = [...state.miners].sort((a, b) => 
        (b.score || b.multiplier || 0) - (a.score || b.multiplier || 0)
    ).slice(0, 20);
    
    container.innerHTML = sortedMiners.map(miner => {
        const tier = getArchitectureTier(miner.device_arch);
        const badgeClass = getArchitectureBadge(miner.device_arch);
        return `
            <tr>
                <td class="mono" title="${escapeHtml(miner.miner_id)}">${shortenAddress(miner.miner_id || 'unknown')}</td>
                <td><span class="badge ${badgeClass}">${escapeHtml(miner.device_arch || 'Unknown')}</span></td>
                <td><span class="badge badge-${tier}">${tier.toUpperCase()}</span></td>
                <td class="text-accent">${formatNumber(miner.multiplier || 1.0, 2)}x</td>
                <td class="text-success">${formatNumber(miner.balance || 0, 6)} RTC</td>
                <td class="mono">${formatRelativeTime(miner.last_seen)}</td>
                <td><span class="badge badge-active">● ACTIVE</span></td>
            </tr>
        `;
    }).join('');
}

function renderBlocksTable() {
    const container = document.getElementById('blocks-tbody');
    if (!container) return;
    
    if (state.loading.blocks) {
        container.innerHTML = '<tr><td colspan="5" class="loading"><div class="spinner"></div>Loading blocks...</td></tr>';
        return;
    }
    
    if (state.error.blocks && state.blocks.length === 0) {
        container.innerHTML = `
            <tr><td colspan="5">
                <div class="error-message">
                    <span class="error-icon">⚠️</span>
                    <span>${escapeHtml(state.error.blocks)}</span>
                </div>
            </td></tr>
        `;
        return;
    }
    
    if (!state.blocks || state.blocks.length === 0) {
        container.innerHTML = '<tr><td colspan="5" class="empty-state"><div class="empty-icon">📦</div>No blocks found</td></tr>';
        return;
    }
    
    container.innerHTML = state.blocks.map(block => `
        <tr>
            <td><strong class="text-accent">#${formatNumber(block.height, 0)}</strong></td>
            <td class="mono" title="${escapeHtml(block.hash)}">${shortenHash(block.hash || '0x')}</td>
            <td class="mono">${formatTimestamp(block.timestamp)}</td>
            <td><span class="badge badge-info">${block.miners_count || 0} miners</span></td>
            <td class="text-success">${formatNumber(block.reward || 0, 2)} RTC</td>
        </tr>
    `).join('');
}

function renderTransactionsTable() {
    const container = document.getElementById('transactions-tbody');
    if (!container) return;
    
    if (state.loading.transactions) {
        container.innerHTML = '<tr><td colspan="6" class="loading"><div class="spinner"></div>Loading transactions...</td></tr>';
        return;
    }
    
    if (state.error.transactions && state.transactions.length === 0) {
        container.innerHTML = `
            <tr><td colspan="6">
                <div class="error-message">
                    <span class="error-icon">⚠️</span>
                    <span>${escapeHtml(state.error.transactions)}</span>
                </div>
            </td></tr>
        `;
        return;
    }
    
    if (!state.transactions || state.transactions.length === 0) {
        container.innerHTML = '<tr><td colspan="6" class="empty-state"><div class="empty-icon">💸</div>No transactions found</td></tr>';
        return;
    }
    
    container.innerHTML = state.transactions.map(tx => `
        <tr>
            <td class="mono" title="${escapeHtml(tx.hash)}">${shortenHash(tx.hash || '0x', 6)}</td>
            <td class="mono">${escapeHtml(tx.type || 'transfer')}</td>
            <td class="mono" title="${escapeHtml(tx.from)}">${shortenAddress(tx.from || '0x')}</td>
            <td class="mono" title="${escapeHtml(tx.to)}">${shortenAddress(tx.to || '0x')}</td>
            <td class="text-success">${formatNumber(tx.amount || 0, 6)} RTC</td>
            <td class="mono">${formatRelativeTime(tx.timestamp)}</td>
        </tr>
    `).join('');
}

function renderHardwareBreakdown() {
    const container = document.getElementById('hardware-breakdown');
    if (!container) return;
    
    if (state.loading.miners || !state.miners.length) {
        container.innerHTML = '<div class="loading">Loading hardware data...</div>';
        return;
    }
    
    const breakdown = {};
    state.miners.forEach(miner => {
        const arch = miner.device_arch || 'Unknown';
        if (!breakdown[arch]) breakdown[arch] = { count: 0, totalMultiplier: 0 };
        breakdown[arch].count++;
        breakdown[arch].totalMultiplier += miner.multiplier || 1;
    });
    
    const sorted = Object.entries(breakdown)
        .map(([arch, data]) => ({ arch, ...data, avgMultiplier: data.totalMultiplier / data.count }))
        .sort((a, b) => b.count - a.count);
    
    const total = state.miners.length;
    
    container.innerHTML = sorted.map(item => {
        const percentage = (item.count / total) * 100;
        const tier = getArchitectureTier(item.arch);
        return `
            <div class="hardware-item" style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span class="badge badge-${tier}">${escapeHtml(item.arch)}</span>
                    <span class="mono">${item.count} (${percentage.toFixed(1)}%)</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${percentage}%"></div>
                </div>
                <div class="text-muted" style="font-size: 0.8rem;">Avg Multiplier: ${formatNumber(item.avgMultiplier, 2)}x</div>
            </div>
        `;
    }).join('');
}

function renderHallOfRust() {
    const container = document.getElementById('hall-of-rust');
    if (!container) return;
    
    if (state.loading.hallOfRust) {
        container.innerHTML = '<div class="loading"><div class="spinner"></div>Loading Hall of Rust...</div>';
        return;
    }
    
    if (state.error.hallOfRust || !state.hallOfRust || !state.hallOfRust.leaderboard) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🏛️</div>
                <p>Hall of Rust unavailable</p>
                <p class="text-muted">This feature requires Hall of Rust endpoint</p>
            </div>
        `;
        return;
    }
    
    const topMachines = state.hallOfRust.leaderboard.slice(0, 5);
    
    container.innerHTML = `
        <div class="section-title" style="margin-bottom: 16px;">🏆 Top Rust Score Machines</div>
        ${topMachines.map((machine, index) => `
            <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--bg-secondary); border-radius: 8px; margin-bottom: 8px;">
                <span style="font-size: 1.5rem; font-weight: bold; color: ${index === 0 ? '#f59e0b' : index === 1 ? '#94a3b8' : index === 2 ? '#b45309' : '#64748b'};">#${index + 1}</span>
                <div style="flex: 1;">
                    <div class="mono" style="font-size: 0.9rem;">${shortenAddress(machine.fingerprint_hash || 'unknown')}</div>
                    <div class="text-muted" style="font-size: 0.8rem;">${escapeHtml(machine.device_arch || 'Unknown')} • ${machine.total_attestations || 0} attestations</div>
                </div>
                <div class="rust-score">${formatNumber(machine.rust_score || 0, 0)}</div>
                <span class="rust-badge">${getRustBadge(machine.rust_score)}</span>
            </div>
        `).join('')}
        <div style="text-align: center; margin-top: 16px;">
            <button class="btn btn-secondary" onclick="alert('Full Hall of Rust coming soon!')">View All</button>
        </div>
    `;
}

function renderSearchResults() {
    const container = document.getElementById('search-results');
    if (!container) return;
    
    const query = state.searchQuery.trim().toLowerCase();
    if (!query) {
        container.innerHTML = '';
        return;
    }
    
    const matchingMiners = state.miners.filter(m => 
        (m.miner_id || '').toLowerCase().includes(query) ||
        (m.device_arch || '').toLowerCase().includes(query)
    );
    
    if (matchingMiners.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <p>No results found for "${escapeHtml(state.searchQuery)}"</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="section-title" style="margin-bottom: 16px;">
            Search Results: ${matchingMiners.length} found
        </div>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Miner ID</th>
                        <th>Architecture</th>
                        <th>Tier</th>
                        <th>Multiplier</th>
                        <th>Balance</th>
                    </tr>
                </thead>
                <tbody>
                    ${matchingMiners.map(miner => {
                        const tier = getArchitectureTier(miner.device_arch);
                        const badgeClass = getArchitectureBadge(miner.device_arch);
                        return `
                            <tr>
                                <td class="mono" title="${escapeHtml(miner.miner_id)}">${shortenAddress(miner.miner_id || 'unknown')}</td>
                                <td><span class="badge ${badgeClass}">${escapeHtml(miner.device_arch || 'Unknown')}</span></td>
                                <td><span class="badge badge-${tier}">${tier.toUpperCase()}</span></td>
                                <td class="text-accent">${formatNumber(miner.multiplier || 1.0, 2)}x</td>
                                <td class="text-success">${formatNumber(miner.balance || 0, 6)} RTC</td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;
}

// Tab Navigation
function switchTab(tabId) {
    state.activeTab = tabId;
    
    // Update tab buttons
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabId);
    });
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabId}`);
    });
    
    // Load data for specific tabs
    if (tabId === 'hall' && !state.hallOfRust) {
        fetchHallOfRust();
    }
}

// Search Handler
function handleSearch(query) {
    state.searchQuery = query;
    renderSearchResults();
}

// Initial Load
async function initialize() {
    console.log('[Explorer] Initializing...');
    
    // Initial data fetch
    await Promise.all([
        fetchHealth(),
        fetchEpoch(),
        fetchMiners(),
        fetchBlocks(),
        fetchTransactions()
    ]);
    
    // Setup auto-refresh
    setInterval(() => {
        console.log('[Explorer] Auto-refreshing data...');
        fetchHealth();
        fetchEpoch();
        fetchMiners();
        fetchBlocks();
        fetchTransactions();
    }, CONFIG.REFRESH_INTERVAL);
    
    console.log('[Explorer] Initialization complete');
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    initialize();
    
    // Tab navigation
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            switchTab(tab.dataset.tab);
        });
    });
    
    // Search
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            handleSearch(e.target.value);
        });
    }
    
    // Manual refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            console.log('[Explorer] Manual refresh triggered');
            Promise.all([
                fetchHealth(),
                fetchEpoch(),
                fetchMiners(),
                fetchBlocks(),
                fetchTransactions()
            ]);
        });
    }
});

// Export for global access
window.RustChainExplorer = {
    state,
    CONFIG,
    refresh: () => Promise.all([
        fetchHealth(),
        fetchEpoch(),
        fetchMiners(),
        fetchBlocks(),
        fetchTransactions()
    ]),
    search: handleSearch,
    switchTab
};
